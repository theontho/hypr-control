from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


WINDOWS_CURVE_STEP = 0.3431164009
WINDOWS_CURVE_POINTS = (
    0.000,
    0.258,
    0.514,
    0.900,
    1.286,
    1.672,
    2.092,
    2.678,
    3.264,
    3.850,
    4.438,
    5.024,
    5.610,
    6.196,
    6.782,
    7.370,
    7.956,
    8.542,
    9.128,
    10.340,
)
MACOS_CURVE_STEP = 0.5
# Common libinput approximation of macOS's unpublished acceleration curve.
MACOS_CURVE_POINTS = tuple(
    round(0.1 * speed + 0.01 * speed**2 + 0.005 * speed**3, 3)
    for speed in (index * MACOS_CURVE_STEP for index in range(20))
)
PROFILES = ("adaptive", "flat", "windows", "macos", "custom")
IGNORED_POINTER_FRAGMENTS = ("consumer-control", "system-control", "keyboard")


class HyprControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class PointerDevice:
    name: str
    current_speed: float


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


class HyprBackend:
    def __init__(
        self,
        *,
        home: Path | None = None,
        runner: Runner = run_command,
    ) -> None:
        self.home = home or Path.home()
        self.runner = runner
        self.state_path = self.home / ".config/hypr-control/settings.json"
        self.lua_path = self.home / ".config/hypr/hypr_control.lua"
        self.input_path = self.home / ".config/hypr/input.lua"

    def list_pointer_devices(self) -> list[PointerDevice]:
        result = self.runner(["hyprctl", "devices", "-j"])
        if result.returncode != 0:
            raise HyprControlError(self._command_error("Could not query Hyprland devices", result))

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise HyprControlError(f"Hyprland returned invalid device data: {error}") from error

        devices = []
        for item in payload.get("mice", []):
            name = item.get("name")
            if not isinstance(name, str) or not name:
                continue
            if any(fragment in name for fragment in IGNORED_POINTER_FRAGMENTS):
                continue
            devices.append(
                PointerDevice(
                    name=name,
                    current_speed=float(item.get("defaultSpeed", 0.0)),
                )
            )

        return sorted(devices, key=lambda device: device.name)

    def load_state(self) -> dict:
        if not self.state_path.exists():
            return {"version": 1, "devices": {}}

        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HyprControlError(f"Could not read {self.state_path}: {error}") from error

        if state.get("version") != 1 or not isinstance(state.get("devices"), dict):
            raise HyprControlError(f"{self.state_path} has an unsupported format")

        for name, settings in state["devices"].items():
            if not isinstance(name, str) or not isinstance(settings, dict):
                raise HyprControlError(f"{self.state_path} contains an invalid device entry")
            self._validate_settings(settings)

        keyboard = state.get("keyboard")
        if keyboard is not None:
            self._validate_keyboard(keyboard)

        return state

    def device_settings(self, name: str) -> dict:
        state = self.load_state()
        settings = state["devices"].get(name)
        if settings is None:
            return {
                "profile": "adaptive",
                "sensitivity": 0.0,
                "curve_scale": 0.4,
                "curve_step": WINDOWS_CURVE_STEP,
                "curve_points": self._scaled_windows_points(0.4),
            }
        result = settings.copy()
        result.setdefault("curve_step", WINDOWS_CURVE_STEP)
        result.setdefault("curve_gain", 1.0)
        if result["profile"] == "windows":
            result["curve_points"] = self._scaled_windows_points(result["curve_scale"])
        elif result["profile"] == "macos":
            result["curve_step"] = MACOS_CURVE_STEP
            result["curve_points"] = self._scaled_macos_points(result["curve_gain"])
        else:
            result.setdefault("curve_points", self._scaled_windows_points(0.4))
        return result

    def apply_device(
        self,
        name: str,
        *,
        profile: str,
        sensitivity: float,
        curve_scale: float,
        curve_gain: float = 1.0,
        curve_step: float = WINDOWS_CURVE_STEP,
        curve_points: list[float] | None = None,
    ) -> None:
        settings = {
            "profile": profile,
            "sensitivity": round(float(sensitivity), 2),
            "curve_scale": round(float(curve_scale), 2),
            "curve_gain": round(float(curve_gain), 2),
            "curve_step": float(curve_step),
        }
        if profile == "custom":
            settings["curve_points"] = [round(float(point), 3) for point in (curve_points or [])]
        self._validate_settings(settings)

        state = self.load_state()
        state["devices"][name] = settings
        self._commit(state)

    def reset_device(self, name: str) -> None:
        state = self.load_state()
        state["devices"].pop(name, None)
        self._commit(state)

    def apply_keyboard(
        self,
        *,
        layout: str,
        variant: str,
        options: str,
        repeat_rate: int,
        repeat_delay: int,
        numlock: bool,
    ) -> None:
        keyboard = {
            "layout": layout.strip(),
            "variant": variant.strip(),
            "options": options.strip(),
            "repeat_rate": int(repeat_rate),
            "repeat_delay": int(repeat_delay),
            "numlock": bool(numlock),
        }
        self._validate_keyboard(keyboard)
        state = self.load_state()
        state["keyboard"] = keyboard
        self._commit(state)

    def render_lua(self, state: dict) -> str:
        lines = [
            "-- Generated by Hypr Control. Edit settings through the app.",
            "-- Source project: ~/Work/hypr-control",
            "",
        ]

        keyboard = state.get("keyboard")
        if keyboard:
            self._validate_keyboard(keyboard)
            lines.extend(
                [
                    "hl.config({",
                    "  input = {",
                    f"    kb_layout = {json.dumps(keyboard['layout'])},",
                    f"    kb_variant = {json.dumps(keyboard['variant'])},",
                    f"    kb_options = {json.dumps(keyboard['options'])},",
                    f"    repeat_rate = {keyboard['repeat_rate']},",
                    f"    repeat_delay = {keyboard['repeat_delay']},",
                    f"    numlock_by_default = {str(keyboard['numlock']).lower()},",
                    "  },",
                    "})",
                    "",
                ]
            )

        for name in sorted(state["devices"]):
            settings = state["devices"][name]
            self._validate_settings(settings)
            lines.extend(
                [
                    "hl.device({",
                    f"  name = {json.dumps(name)},",
                ]
            )

            if settings["profile"] == "windows":
                lines.append(
                    f"  accel_profile = {json.dumps(self._windows_curve(settings['curve_scale']))},"
                )
            elif settings["profile"] == "macos":
                lines.append(
                    "  accel_profile = "
                    f"{json.dumps(self._custom_curve(MACOS_CURVE_STEP, self._scaled_macos_points(settings.get('curve_gain', 1.0))))},"
                )
            elif settings["profile"] == "custom":
                lines.append(
                    "  accel_profile = "
                    f"{json.dumps(self._custom_curve(settings['curve_step'], self._scaled_curve_points(settings['curve_points'], settings.get('curve_gain', 1.0))))},"
                )
            else:
                lines.extend(
                    [
                        f"  accel_profile = {json.dumps(settings['profile'])},",
                        f"  sensitivity = {settings['sensitivity']:.2f},",
                    ]
                )

            lines.extend(["})", ""])

        return "\n".join(lines)

    def _commit(self, state: dict) -> None:
        self._require_integration()
        previous_state = self._read_optional(self.state_path)
        previous_lua = self._read_optional(self.lua_path)

        try:
            self._write_atomic(
                self.state_path,
                json.dumps(state, indent=2, sort_keys=True) + "\n",
            )
            self._write_atomic(self.lua_path, self.render_lua(state))
            self._reload_and_validate()
        except Exception as error:
            rollback_errors = []
            for path, content in (
                (self.state_path, previous_state),
                (self.lua_path, previous_lua),
            ):
                try:
                    self._restore(path, content)
                except OSError as rollback_error:
                    rollback_errors.append(f"{path}: {rollback_error}")

            reload_result = self.runner(["hyprctl", "reload"])
            if reload_result.returncode != 0:
                rollback_errors.append(self._command_error("Rollback reload failed", reload_result))

            detail = f"Settings were rolled back: {error}"
            if rollback_errors:
                detail += "\nRollback problems: " + "; ".join(rollback_errors)
            raise HyprControlError(detail) from error

    def _require_integration(self) -> None:
        try:
            input_config = self.input_path.read_text(encoding="utf-8")
        except OSError as error:
            raise HyprControlError(f"Could not read {self.input_path}: {error}") from error

        if 'require("hypr.hypr_control")' not in input_config:
            raise HyprControlError(
                "Hypr Control is not loaded by Hyprland. Run the project's install.sh again."
            )

    def _reload_and_validate(self) -> None:
        reload_result = self.runner(["hyprctl", "reload"])
        if reload_result.returncode != 0:
            raise HyprControlError(self._command_error("Hyprland reload failed", reload_result))

        errors_result = self.runner(["hyprctl", "configerrors"])
        if errors_result.returncode != 0:
            raise HyprControlError(self._command_error("Could not validate Hyprland config", errors_result))
        if errors_result.stdout.strip():
            raise HyprControlError(f"Hyprland rejected the generated config:\n{errors_result.stdout.strip()}")

    @staticmethod
    def _validate_settings(settings: dict) -> None:
        profile = settings.get("profile")
        if profile not in PROFILES:
            raise HyprControlError(f"Unsupported acceleration profile: {profile!r}")

        try:
            sensitivity = float(settings.get("sensitivity", 0.0))
            curve_scale = float(settings.get("curve_scale", 0.4))
            curve_gain = float(settings.get("curve_gain", 1.0))
        except (TypeError, ValueError) as error:
            raise HyprControlError("Sensitivity and curve speeds must be numbers") from error

        if not -1.0 <= sensitivity <= 1.0:
            raise HyprControlError("Sensitivity must be between -1.0 and 1.0")
        if not 0.1 <= curve_scale <= 1.0:
            raise HyprControlError("Windows curve scale must be between 0.1 and 1.0")
        if not 0.1 <= curve_gain <= 1.5:
            raise HyprControlError("Curve speed must be between 0.1 and 1.5")
        if profile == "custom":
            try:
                curve_step = float(settings.get("curve_step", WINDOWS_CURVE_STEP))
                curve_points = [float(point) for point in settings.get("curve_points", [])]
            except (TypeError, ValueError) as error:
                raise HyprControlError("Custom curve values must be numbers") from error
            if not 0.01 <= curve_step <= 5:
                raise HyprControlError("Custom curve step must be between 0.01 and 5")
            if not 2 <= len(curve_points) <= 64:
                raise HyprControlError("Custom curves need between 2 and 64 points")
            if curve_points[0] < 0 or any(
                curve_points[index] < curve_points[index - 1]
                for index in range(1, len(curve_points))
            ):
                raise HyprControlError("Custom curve points must be non-negative and non-decreasing")
            if curve_points[-1] > 100:
                raise HyprControlError("Custom curve output cannot exceed 100")
            if curve_points[-1] * curve_gain > 100:
                raise HyprControlError("Scaled custom curve output cannot exceed 100")

    @staticmethod
    def _validate_keyboard(settings: dict) -> None:
        layout = settings.get("layout")
        if not isinstance(layout, str) or not layout.strip() or len(layout) > 100:
            raise HyprControlError("Keyboard layout must be a non-empty string")
        for key in ("variant", "options"):
            value = settings.get(key)
            if not isinstance(value, str) or len(value) > 300:
                raise HyprControlError(f"Keyboard {key} must be a string")
        repeat_rate = settings.get("repeat_rate")
        repeat_delay = settings.get("repeat_delay")
        if not isinstance(repeat_rate, int) or not 1 <= repeat_rate <= 100:
            raise HyprControlError("Keyboard repeat rate must be between 1 and 100")
        if not isinstance(repeat_delay, int) or not 100 <= repeat_delay <= 2000:
            raise HyprControlError("Keyboard repeat delay must be between 100 and 2000 ms")
        if not isinstance(settings.get("numlock"), bool):
            raise HyprControlError("Num Lock setting must be true or false")

    @staticmethod
    def _windows_curve(scale: float) -> str:
        points = " ".join(f"{point:.3f}" for point in HyprBackend._scaled_windows_points(scale))
        return f"custom {WINDOWS_CURVE_STEP:.10f} {points}"

    @staticmethod
    def _scaled_windows_points(scale: float) -> list[float]:
        return [round(point * scale, 3) for point in WINDOWS_CURVE_POINTS]

    @staticmethod
    def _scaled_macos_points(gain: float) -> list[float]:
        return [round(point * gain, 3) for point in MACOS_CURVE_POINTS]

    @staticmethod
    def _scaled_curve_points(points: list[float], gain: float) -> list[float]:
        return [round(float(point) * gain, 3) for point in points]

    @staticmethod
    def _custom_curve(step: float, points: list[float]) -> str:
        rendered = " ".join(f"{float(point):.3f}" for point in points)
        return f"custom {float(step):.10f} {rendered}"

    @staticmethod
    def _command_error(message: str, result: subprocess.CompletedProcess[str]) -> str:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        return f"{message}: {detail}"

    @staticmethod
    def _read_optional(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    @staticmethod
    def _write_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _restore(self, path: Path, content: str | None) -> None:
        if content is None:
            path.unlink(missing_ok=True)
        else:
            self._write_atomic(path, content)
