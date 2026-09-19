from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .backend import HyprBackend, HyprControlError, run_command


class SystemBackend:
    def __init__(self, *, home: Path | None = None) -> None:
        self.home = home or Path.home()
        self.hypr = HyprBackend(home=self.home)

    def snapshot(self) -> dict:
        return {
            "input": self._input_snapshot(),
            "keyboard": self._keyboard_snapshot(),
            "network": self._network_snapshot(),
            "tailscale": self._tailscale_snapshot(),
            "bluetooth": self._bluetooth_snapshot(),
            "audio": self._audio_snapshot(),
            "displays": self._display_snapshot(),
            "graphics": self._graphics_snapshot(),
            "appearance": self._appearance_snapshot(),
            "power": self._power_snapshot(),
            "storage": self._storage_snapshot(),
            "dateTime": self._date_time_snapshot(),
            "security": self._security_snapshot(),
            "nightLight": self._night_light_snapshot(),
            "updates": self._updates_snapshot(),
            "system": self._system_snapshot(),
        }

    def set_wifi_power(self, enabled: bool) -> None:
        self._required(["nmcli", "radio", "wifi", "on" if enabled else "off"])

    def set_bluetooth_power(self, enabled: bool) -> None:
        self._required(["bluetoothctl", "power", "on" if enabled else "off"])

    def bluetooth_device(self, address: str, action: str) -> None:
        if not re.fullmatch(r"[0-9A-Fa-f:]{17}", address):
            raise HyprControlError("Invalid Bluetooth device address")
        if action not in {"connect", "disconnect"}:
            raise HyprControlError("Unsupported Bluetooth action")
        self._required(["bluetoothctl", action, address])

    def set_audio_volume(self, percent: int) -> None:
        if not 0 <= percent <= 150:
            raise HyprControlError("Volume must be between 0 and 150 percent")
        self._required(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"])

    def toggle_audio_mute(self) -> None:
        self._required(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])

    def set_audio_default(self, kind: str, node_id: int, name: str) -> None:
        if kind not in {"sink", "source"}:
            raise HyprControlError("Audio device kind must be sink or source")
        if node_id < 0 or not name or len(name) > 300:
            raise HyprControlError("Invalid audio device")
        helper = (
            "omarchy-audio-output-set-default"
            if kind == "sink"
            else "omarchy-audio-input-set-default"
        )
        self._required([helper, str(node_id), name])

    def set_display_scale(self, monitor: str, scale: float) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", monitor):
            raise HyprControlError("Invalid monitor name")
        if not 1 <= scale <= 4:
            raise HyprControlError("Display scale must be between 1 and 4")
        self._required(
            ["hyprctl", "eval", f'hl.dispatch(hl.dsp.focus({{ monitor = "{monitor}" }}))']
        )
        self._required(["omarchy-hyprland-monitor-scaling", f"{scale:g}"])

    def set_power_profile(self, profile: str) -> None:
        if profile not in {"power-saver", "balanced", "performance"}:
            raise HyprControlError("Unsupported power profile")
        self._required(["powerprofilesctl", "set", profile])

    def set_theme(self, theme: str) -> None:
        available = self._appearance_snapshot()["themes"]
        if theme not in available:
            raise HyprControlError("Unknown Omarchy theme")
        self._required(["omarchy", "theme", "set", theme])

    def set_idle(self, *, screensaver_seconds: int, lock_seconds: int) -> None:
        if not 0 <= screensaver_seconds <= 86400 or not 0 <= lock_seconds <= 86400:
            raise HyprControlError("Idle timers must be between 0 and 86400 seconds")
        if lock_seconds and screensaver_seconds and lock_seconds < screensaver_seconds:
            raise HyprControlError("Lock time cannot be shorter than the screensaver time")

        shell_path = self.home / ".config/omarchy/shell.json"
        try:
            shell = json.loads(shell_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HyprControlError(f"Could not read {shell_path}: {error}") from error
        shell.setdefault("idle", {})
        shell["idle"]["screensaver"] = screensaver_seconds
        shell["idle"]["lock"] = lock_seconds
        self._write_json_atomic(shell_path, shell)

    def set_night_light_temperature(self, temperature: int) -> None:
        if not 1000 <= temperature <= 5500:
            raise HyprControlError("Night-light temperature must be between 1000K and 5500K")

        night_mode_path = self.home / ".config/omarchy/night-mode.json"
        hyprsunset_path = self.home / ".config/hypr/hyprsunset.conf"
        original_night_mode = self._read_optional(night_mode_path)
        original_hyprsunset = self._read_optional(hyprsunset_path)
        if original_hyprsunset is None:
            raise HyprControlError(f"Could not read {hyprsunset_path}")

        updated_hyprsunset, replacements = re.subn(
            r"(^\s*temperature\s*=\s*)\d+",
            rf"\g<1>{temperature}",
            original_hyprsunset,
            count=1,
            flags=re.MULTILINE,
        )
        if replacements != 1:
            raise HyprControlError(f"Could not find a night-light temperature in {hyprsunset_path}")

        night_mode = {}
        if original_night_mode is not None:
            try:
                night_mode = json.loads(original_night_mode)
            except json.JSONDecodeError as error:
                raise HyprControlError(f"Could not parse {night_mode_path}: {error}") from error
        night_mode["temperature"] = temperature
        was_enabled = self._current_night_light_temperature() < 6000

        try:
            self._write_json_atomic(night_mode_path, night_mode)
            self._write_text_atomic(hyprsunset_path, updated_hyprsunset)
            if was_enabled:
                self._apply_night_light_temperature(temperature)
            keyboard_sync = shutil.which("razer-kelvin-sync")
            if keyboard_sync:
                self._required([keyboard_sync])
        except Exception as error:
            rollback_errors = []
            for path, content in (
                (night_mode_path, original_night_mode),
                (hyprsunset_path, original_hyprsunset),
            ):
                try:
                    self._restore_optional(path, content)
                except OSError as rollback_error:
                    rollback_errors.append(f"{path}: {rollback_error}")
            if was_enabled:
                previous_temperature = self._temperature_from_night_mode(original_night_mode)
                try:
                    self._apply_night_light_temperature(previous_temperature)
                except HyprControlError as rollback_error:
                    rollback_errors.append(str(rollback_error))
            detail = f"Night-light settings were rolled back: {error}"
            if rollback_errors:
                detail += "\nRollback problems: " + "; ".join(rollback_errors)
            raise HyprControlError(detail) from error

    def toggle_night_light(self) -> None:
        command = shutil.which("streamdeck-night-mode")
        if command:
            self._required([command])
        else:
            self._required(["omarchy", "toggle", "nightlight"])

    def set_tailscale_enabled(self, enabled: bool) -> None:
        if shutil.which("tailscale") is None:
            raise HyprControlError("Tailscale is not installed")
        self._required(["tailscale", "up" if enabled else "down"])

    def launch_tool(self, tool: str) -> None:
        if tool == "themes":
            command = shutil.which("omarchy-theme-switcher")
            if command is None:
                raise HyprControlError("Required Omarchy command is unavailable: omarchy-theme-switcher")
            selected_theme = self._required([command]).strip()
            if selected_theme:
                self.set_theme(selected_theme)
            return

        commands = {
            "timezone": [
                "omarchy-launch-floating-terminal-with-presentation",
                "omarchy-menu-timezone",
            ],
            "updates": [
                "omarchy-launch-floating-terminal-with-presentation",
                "omarchy-update",
            ],
        }
        command = commands.get(tool)
        if command is None:
            raise HyprControlError("Unsupported settings tool")
        missing = [executable for executable in command if shutil.which(executable) is None]
        if missing:
            raise HyprControlError(f"Required Omarchy command is unavailable: {missing[0]}")
        launch_command = " ".join(command)
        self._required(
            [
                "hyprctl",
                "eval",
                f"hl.dispatch(hl.dsp.exec_cmd({json.dumps(launch_command)}))",
            ]
        )

    def _input_snapshot(self) -> dict:
        devices = []
        for device in self.hypr.list_pointer_devices():
            devices.append(
                {
                    "name": device.name,
                    "currentSpeed": device.current_speed,
                    "settings": self.hypr.device_settings(device.name),
                }
            )
        return {"devices": devices}

    def _keyboard_snapshot(self) -> dict:
        state = self.hypr.load_state()
        saved = state.get("keyboard")
        if saved:
            return saved.copy()
        return {
            "layout": self._hypr_string("input:kb_layout", "us"),
            "variant": self._hypr_string("input:kb_variant", ""),
            "options": self._hypr_string("input:kb_options", ""),
            "repeat_rate": self._hypr_number("input:repeat_rate", 40),
            "repeat_delay": self._hypr_number("input:repeat_delay", 250),
            "numlock": self._hypr_bool("input:numlock_by_default", True),
        }

    def _network_snapshot(self) -> dict:
        rows = []
        result = self._optional(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
        for line in result.splitlines():
            parts = line.split(":", 3)
            if len(parts) != 4:
                continue
            device, device_type, state, connection = parts
            address = ""
            if state.startswith("connected") and device:
                address = self._optional(["nmcli", "-g", "IP4.ADDRESS", "device", "show", device]).splitlines()[0:1]
                address = address[0] if address else ""
            rows.append(
                {
                    "device": device,
                    "type": device_type,
                    "state": state,
                    "connection": connection,
                    "address": address,
                }
            )
        wifi_present = any(row["type"] == "wifi" for row in rows)
        return {
            "wifiPresent": wifi_present,
            "wifiEnabled": self._optional(["nmcli", "radio", "wifi"]).strip() == "enabled",
            "devices": rows,
        }

    def _bluetooth_snapshot(self) -> dict:
        show = self._optional(["bluetoothctl", "show"])
        powered = bool(re.search(r"^\s*Powered:\s+yes\s*$", show, re.MULTILINE))
        paired = self._bluetooth_devices(["bluetoothctl", "devices", "Paired"])
        connected_addresses = {
            device["address"]
            for device in self._bluetooth_devices(["bluetoothctl", "devices", "Connected"])
        }
        for device in paired:
            device["connected"] = device["address"] in connected_addresses
        return {"available": "Controller " in show, "powered": powered, "devices": paired}

    def _tailscale_snapshot(self) -> dict:
        installed = shutil.which("tailscale") is not None
        if not installed:
            return {"installed": False, "active": False, "state": "", "addresses": [], "peers": []}
        raw = self._optional(["tailscale", "status", "--json"])
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        state = str(payload.get("BackendState", ""))
        peers = []
        for peer in payload.get("Peer", {}).values():
            addresses = peer.get("TailscaleIPs") or []
            peers.append(
                {
                    "name": str(peer.get("HostName") or peer.get("DNSName") or "Unknown"),
                    "address": str(addresses[0]) if addresses else "",
                    "online": bool(peer.get("Online", False)),
                    "active": bool(peer.get("Active", False)),
                }
            )
        peers.sort(key=lambda peer: (not peer["online"], peer["name"].lower()))
        return {
            "installed": True,
            "active": state == "Running",
            "state": state,
            "addresses": payload.get("TailscaleIPs") or [],
            "peers": peers,
        }

    def _audio_snapshot(self) -> dict:
        volume_output = self._optional(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        mute_output = self._optional(["pactl", "get-sink-mute", "@DEFAULT_SINK@"])
        match = re.search(r"/\s*(\d+)%", volume_output)
        default_sink = self._optional(["pactl", "get-default-sink"]).strip()
        return {
            "available": bool(match),
            "volume": int(match.group(1)) if match else 0,
            "muted": "yes" in mute_output.lower(),
            "defaultSink": default_sink,
            "sinks": self._pactl_nodes("sinks"),
            "sources": self._pactl_nodes("sources"),
        }

    def _display_snapshot(self) -> dict:
        raw = self._optional(["hyprctl", "monitors", "all", "-j"])
        try:
            monitors = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            monitors = []
        return {
            "monitors": [
                {
                    "name": monitor.get("name", ""),
                    "description": monitor.get("description", ""),
                    "width": monitor.get("width", 0),
                    "height": monitor.get("height", 0),
                    "refreshRate": monitor.get("refreshRate", 0),
                    "scale": monitor.get("scale", 1),
                    "focused": monitor.get("focused", False),
                    "disabled": monitor.get("disabled", False),
                }
                for monitor in monitors
            ]
        }

    def _graphics_snapshot(self) -> dict:
        devices = []
        for line in self._optional(["lspci", "-mm"]).splitlines():
            if not re.search(r'"(?:VGA compatible controller|3D controller|Display controller)"', line):
                continue
            quoted = re.findall(r'"([^"]*)"', line)
            if len(quoted) >= 3:
                devices.append({"class": quoted[0], "vendor": quoted[1], "model": quoted[2]})
        cameras = []
        video_root = Path("/sys/class/video4linux")
        if video_root.exists():
            for path in sorted(video_root.iterdir()):
                name = self._read_sysfs(path / "name")
                cameras.append({"device": f"/dev/{path.name}", "name": name or path.name})
        return {"devices": devices, "cameras": cameras}

    def _appearance_snapshot(self) -> dict:
        theme = self._optional(["omarchy", "theme", "current"]).strip() or "Unknown"
        themes = [
            line.strip()
            for line in self._optional(["omarchy", "theme", "list"]).splitlines()
            if line.strip()
        ]
        return {"theme": theme, "themes": themes}

    def _power_snapshot(self) -> dict:
        output = self._optional(["powerprofilesctl", "list"])
        active = ""
        profiles = []
        for line in output.splitlines():
            match = re.match(r"\s*(\*)?\s*(power-saver|balanced|performance):", line)
            if match:
                profiles.append(match.group(2))
                if match.group(1):
                    active = match.group(2)
        return {
            "available": bool(profiles),
            "active": active,
            "profiles": profiles,
            "batteries": self._battery_snapshot(),
        }

    @staticmethod
    def _battery_snapshot() -> list[dict]:
        batteries = []
        power_root = Path("/sys/class/power_supply")
        if not power_root.exists():
            return batteries
        for path in sorted(power_root.iterdir()):
            if SystemBackend._read_sysfs(path / "type") != "Battery":
                continue
            energy_full = SystemBackend._read_sysfs_number(path / "energy_full")
            energy_design = SystemBackend._read_sysfs_number(path / "energy_full_design")
            if energy_full is None:
                energy_full = SystemBackend._read_sysfs_number(path / "charge_full")
                energy_design = SystemBackend._read_sysfs_number(path / "charge_full_design")
            health = None
            if energy_full is not None and energy_design:
                health = round(energy_full / energy_design * 100)
            batteries.append(
                {
                    "name": path.name,
                    "capacity": SystemBackend._read_sysfs_number(path / "capacity"),
                    "status": SystemBackend._read_sysfs(path / "status"),
                    "health": health,
                    "cycleCount": SystemBackend._read_sysfs_number(path / "cycle_count"),
                }
            )
        return batteries

    @staticmethod
    def _storage_snapshot() -> dict:
        usage = shutil.disk_usage("/")
        return {
            "root": {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
            }
        }

    def _date_time_snapshot(self) -> dict:
        output = self._optional(["timedatectl", "show", "--property=Timezone", "--property=NTPSynchronized"])
        values = self._key_values(output)
        return {
            "timezone": values.get("Timezone", ""),
            "ntpSynchronized": values.get("NTPSynchronized", "no") == "yes",
        }

    def _security_snapshot(self) -> dict:
        shell_path = self.home / ".config/omarchy/shell.json"
        try:
            shell = json.loads(shell_path.read_text(encoding="utf-8"))
            idle = shell.get("idle", {})
        except (OSError, json.JSONDecodeError):
            idle = {}
        return {
            "lockSeconds": int(idle.get("lock", 0)),
            "screensaverSeconds": int(idle.get("screensaver", 0)),
        }

    def _night_light_snapshot(self) -> dict:
        night_mode_path = self.home / ".config/omarchy/night-mode.json"
        configured_temperature = self._temperature_from_night_mode(
            self._read_optional(night_mode_path)
        )

        current_temperature = self._current_night_light_temperature()
        return {
            "available": shutil.which("hyprsunset") is not None,
            "enabled": current_temperature < 6000,
            "currentTemperature": current_temperature,
            "configuredTemperature": configured_temperature,
        }

    def _current_night_light_temperature(self) -> int:
        output = self._optional(["hyprctl", "hyprsunset", "temperature"])
        match = re.search(r"\d+", output)
        return int(match.group(0)) if match else 6500

    def _apply_night_light_temperature(self, temperature: int) -> None:
        command = ["hyprctl", "hyprsunset", "temperature", str(temperature)]
        for _ in range(10):
            result = run_command(command)
            if result.returncode == 0:
                time.sleep(0.2)
                if self._current_night_light_temperature() == temperature:
                    return
            else:
                time.sleep(0.2)
        raise HyprControlError(f"Could not apply night-light temperature {temperature}K")

    @staticmethod
    def _temperature_from_night_mode(content: str | None) -> int:
        try:
            temperature = int(json.loads(content or "{}").get("temperature", 1800))
        except (ValueError, TypeError, json.JSONDecodeError):
            return 1800
        return temperature if 1000 <= temperature <= 5500 else 1800

    def _updates_snapshot(self) -> dict:
        log_path = Path("/var/log/pacman.log")
        last_update = ""
        try:
            for line in reversed(log_path.read_text(encoding="utf-8", errors="replace").splitlines()):
                if "[ALPM] upgraded " in line:
                    last_update = line.split("]", 1)[0].lstrip("[")
                    break
        except OSError:
            pass
        return {"lastUpdate": last_update}

    def _system_snapshot(self) -> dict:
        try:
            os_release = self._key_values(Path("/etc/os-release").read_text(encoding="utf-8"))
        except OSError:
            os_release = {}
        host = self._optional(["hostname"]).strip()
        cpu = ""
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
        memory_total = 0
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    memory_total = int(line.split()[1]) * 1024
                    break
        except (OSError, ValueError):
            pass
        return {
            "hostname": host,
            "os": os_release.get("PRETTY_NAME", "Linux").strip('"'),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "cpu": cpu,
            "memoryTotal": memory_total,
        }

    def _hypr_option(self, option: str) -> dict:
        raw = self._optional(["hyprctl", "getoption", option, "-j"])
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _hypr_string(self, option: str, fallback: str) -> str:
        return str(self._hypr_option(option).get("str", fallback))

    def _hypr_number(self, option: str, fallback: int) -> int:
        payload = self._hypr_option(option)
        return int(payload.get("int", payload.get("float", fallback)))

    def _hypr_bool(self, option: str, fallback: bool) -> bool:
        return bool(self._hypr_option(option).get("bool", fallback))

    def _bluetooth_devices(self, command: list[str]) -> list[dict]:
        devices = []
        for line in self._optional(command).splitlines():
            match = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)", line)
            if match:
                devices.append({"address": match.group(1), "name": match.group(2)})
        return devices

    def _pactl_nodes(self, node_type: str) -> list[dict]:
        output = self._optional(["pactl", "-f", "json", "list", node_type])
        nodes = []
        try:
            payload = json.loads(output) if output else []
        except json.JSONDecodeError:
            payload = []
        default_name = self._optional(
            ["pactl", "get-default-sink" if node_type == "sinks" else "get-default-source"]
        ).strip()
        for node in payload:
            name = str(node.get("name", ""))
            description = str(node.get("description", name))
            nodes.append(
                {
                    "id": int(node.get("index", 0)),
                    "name": name,
                    "description": description,
                    "default": name == default_name,
                }
            )
        return nodes

    @staticmethod
    def _key_values(output: str) -> dict[str, str]:
        values = {}
        for line in output.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        return values

    @staticmethod
    def _read_sysfs(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @staticmethod
    def _read_sysfs_number(path: Path) -> int | None:
        value = SystemBackend._read_sysfs(path)
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict) -> None:
        SystemBackend._write_text_atomic(path, json.dumps(payload, indent=2) + "\n")

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _read_optional(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    @staticmethod
    def _restore_optional(path: Path, content: str | None) -> None:
        if content is None:
            path.unlink(missing_ok=True)
        else:
            SystemBackend._write_text_atomic(path, content)

    @staticmethod
    def _optional(command: list[str]) -> str:
        try:
            result = run_command(command)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout if result.returncode == 0 else ""

    @staticmethod
    def _required(command: list[str]) -> str:
        try:
            result = run_command(command)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise HyprControlError(f"Could not run {command[0]}: {error}") from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            raise HyprControlError(f"{command[0]} failed: {detail}")
        return result.stdout
