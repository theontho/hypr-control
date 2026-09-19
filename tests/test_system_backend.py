import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hyprcontrol.backend import HyprControlError
from hyprcontrol.system_backend import SystemBackend


def completed(command, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class SystemBackendTests(unittest.TestCase):
    def test_mutating_actions_run_expected_commands(self):
        calls = []

        def runner(command):
            calls.append(command)
            return completed(command)

        backend = SystemBackend()
        with (
            patch("hyprcontrol.system_backend.run_command", side_effect=runner),
            patch("hyprcontrol.system_backend.shutil.which", return_value="/usr/bin/tool"),
        ):
            backend.set_wifi_power(True)
            backend.set_bluetooth_power(False)
            backend.bluetooth_device("AA:BB:CC:DD:EE:FF", "connect")
            backend.set_audio_volume(60)
            backend.toggle_audio_mute()
            backend.set_audio_default("sink", 7, "sink.default")
            backend.set_tailscale_enabled(True)
            backend.set_display_scale("DP-2", 2)
            backend.set_power_profile("performance")

        self.assertEqual(
            calls,
            [
                ["nmcli", "radio", "wifi", "on"],
                ["bluetoothctl", "power", "off"],
                ["bluetoothctl", "connect", "AA:BB:CC:DD:EE:FF"],
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "60%"],
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
                ["omarchy-audio-output-set-default", "7", "sink.default"],
                ["tailscale", "up"],
                [
                    "hyprctl",
                    "eval",
                    'hl.dispatch(hl.dsp.focus({ monitor = "DP-2" }))',
                ],
                ["omarchy-hyprland-monitor-scaling", "2"],
                ["powerprofilesctl", "set", "performance"],
            ],
        )

    def test_action_validation_rejects_invalid_values(self):
        backend = SystemBackend()
        invalid_calls = (
            lambda: backend.bluetooth_device("not-an-address", "connect"),
            lambda: backend.bluetooth_device("AA:BB:CC:DD:EE:FF", "pair"),
            lambda: backend.set_audio_volume(151),
            lambda: backend.set_audio_default("stream", 1, "test"),
            lambda: backend.set_audio_default("sink", -1, "test"),
            lambda: backend.set_display_scale("../DP-2", 2),
            lambda: backend.set_display_scale("DP-2", 0.5),
            lambda: backend.set_power_profile("turbo"),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(HyprControlError):
                call()

    def test_idle_settings_are_atomic_and_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            shell_path = home / ".config/omarchy/shell.json"
            shell_path.parent.mkdir(parents=True)
            shell_path.write_text(
                json.dumps({"idle": {"screensaver": 60, "lock": 120}, "other": True}),
                encoding="utf-8",
            )
            backend = SystemBackend(home=home)

            backend.set_idle(screensaver_seconds=150, lock_seconds=300)
            saved = json.loads(shell_path.read_text(encoding="utf-8"))

            self.assertEqual(saved["idle"], {"screensaver": 150, "lock": 300})
            self.assertTrue(saved["other"])
            with self.assertRaises(HyprControlError):
                backend.set_idle(screensaver_seconds=600, lock_seconds=300)

    def test_launch_tools_use_available_current_omarchy_commands(self):
        calls = []

        def runner(command):
            calls.append(command)
            return completed(command)

        backend = SystemBackend()
        with (
            patch("hyprcontrol.system_backend.run_command", side_effect=runner),
            patch("hyprcontrol.system_backend.shutil.which", return_value="/usr/bin/tool"),
        ):
            backend.launch_tool("timezone")
            backend.launch_tool("updates")
            backend.launch_tool("themes")

        self.assertEqual(
            calls,
            [
                [
                    "hyprctl",
                    "eval",
                    'hl.dispatch(hl.dsp.exec_cmd("omarchy-launch-floating-terminal-with-presentation omarchy-menu-timezone"))',
                ],
                [
                    "hyprctl",
                    "eval",
                    'hl.dispatch(hl.dsp.exec_cmd("omarchy-launch-floating-terminal-with-presentation omarchy-update"))',
                ],
                [
                    "/usr/bin/tool",
                ],
            ],
        )

    def test_visual_theme_picker_applies_selected_theme(self):
        calls = []

        def runner(command):
            calls.append(command)
            if command == ["/usr/bin/omarchy-theme-switcher"]:
                return completed(command, stdout="Tokyo Night\n")
            if command == ["omarchy", "theme", "current"]:
                return completed(command, stdout="Everforest\n")
            if command == ["omarchy", "theme", "list"]:
                return completed(command, stdout="Everforest\nTokyo Night\n")
            return completed(command)

        backend = SystemBackend()
        with (
            patch("hyprcontrol.system_backend.run_command", side_effect=runner),
            patch(
                "hyprcontrol.system_backend.shutil.which",
                side_effect=lambda command: (
                    "/usr/bin/omarchy-theme-switcher"
                    if command == "omarchy-theme-switcher"
                    else "/usr/bin/tool"
                ),
            ),
        ):
            backend.launch_tool("themes")

        self.assertEqual(
            calls,
            [
                ["/usr/bin/omarchy-theme-switcher"],
                ["omarchy", "theme", "current"],
                ["omarchy", "theme", "list"],
                ["omarchy", "theme", "set", "Tokyo Night"],
            ],
        )

    def test_launch_tool_reports_missing_command(self):
        backend = SystemBackend()
        with patch("hyprcontrol.system_backend.shutil.which", return_value=None):
            with self.assertRaisesRegex(HyprControlError, "unavailable"):
                backend.launch_tool("timezone")

    def test_night_light_temperature_updates_shared_configs(self):
        calls = []

        def runner(command):
            calls.append(command)
            if command == ["hyprctl", "hyprsunset", "temperature"]:
                requested = next(
                    (
                        call[-1]
                        for call in reversed(calls)
                        if call[:3] == ["hyprctl", "hyprsunset", "temperature"]
                        and len(call) == 4
                    ),
                    "4000",
                )
                return completed(command, stdout=f"{requested}\n")
            return completed(command)

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            night_mode_path = home / ".config/omarchy/night-mode.json"
            hyprsunset_path = home / ".config/hypr/hyprsunset.conf"
            night_mode_path.parent.mkdir(parents=True)
            hyprsunset_path.parent.mkdir(parents=True)
            night_mode_path.write_text('{"temperature": 4000, "other": true}\n', encoding="utf-8")
            hyprsunset_path.write_text(
                "profile {\n    time = 20:00\n    temperature = 1800\n}\n",
                encoding="utf-8",
            )
            backend = SystemBackend(home=home)

            with (
                patch("hyprcontrol.system_backend.run_command", side_effect=runner),
                patch("hyprcontrol.system_backend.time.sleep"),
                patch(
                    "hyprcontrol.system_backend.shutil.which",
                    side_effect=lambda name: f"/usr/bin/{name}" if name == "razer-kelvin-sync" else None,
                ),
            ):
                backend.set_night_light_temperature(3200)

            self.assertEqual(
                json.loads(night_mode_path.read_text(encoding="utf-8")),
                {"temperature": 3200, "other": True},
            )
            self.assertIn("temperature = 3200", hyprsunset_path.read_text(encoding="utf-8"))

        self.assertNotIn(["omarchy", "restart", "hyprsunset"], calls)
        self.assertIn(["hyprctl", "hyprsunset", "temperature", "3200"], calls)
        self.assertIn(["/usr/bin/razer-kelvin-sync"], calls)

    def test_night_light_validation_and_toggle(self):
        backend = SystemBackend()
        with self.assertRaises(HyprControlError):
            backend.set_night_light_temperature(6500)

        calls = []
        with (
            patch(
                "hyprcontrol.system_backend.run_command",
                side_effect=lambda command: calls.append(command) or completed(command),
            ),
            patch(
                "hyprcontrol.system_backend.shutil.which",
                return_value="/home/test/.local/bin/streamdeck-night-mode",
            ),
        ):
            backend.toggle_night_light()

        self.assertEqual(calls, [["/home/test/.local/bin/streamdeck-night-mode"]])

    def test_night_light_snapshot_reads_stream_deck_temperature(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            night_mode_path = home / ".config/omarchy/night-mode.json"
            night_mode_path.parent.mkdir(parents=True)
            night_mode_path.write_text('{"temperature": 3000}\n', encoding="utf-8")
            backend = SystemBackend(home=home)

            with (
                patch(
                    "hyprcontrol.system_backend.run_command",
                    return_value=completed([], stdout="Temperature: 3000K\n"),
                ),
                patch("hyprcontrol.system_backend.shutil.which", return_value="/usr/bin/hyprsunset"),
            ):
                snapshot = backend._night_light_snapshot()

        self.assertTrue(snapshot["available"])
        self.assertTrue(snapshot["enabled"])
        self.assertEqual(snapshot["currentTemperature"], 3000)
        self.assertEqual(snapshot["configuredTemperature"], 3000)

    def test_tailscale_snapshot_lists_online_peers_first(self):
        payload = {
            "BackendState": "Running",
            "TailscaleIPs": ["100.64.0.1"],
            "Peer": {
                "offline": {
                    "HostName": "zeta",
                    "TailscaleIPs": ["100.64.0.3"],
                    "Online": False,
                },
                "online": {
                    "HostName": "alpha",
                    "TailscaleIPs": ["100.64.0.2"],
                    "Online": True,
                    "Active": True,
                },
            },
        }
        backend = SystemBackend()
        with (
            patch("hyprcontrol.system_backend.shutil.which", return_value="/usr/bin/tailscale"),
            patch(
                "hyprcontrol.system_backend.run_command",
                return_value=completed([], stdout=json.dumps(payload)),
            ),
        ):
            snapshot = backend._tailscale_snapshot()

        self.assertTrue(snapshot["installed"])
        self.assertTrue(snapshot["active"])
        self.assertEqual(snapshot["addresses"], ["100.64.0.1"])
        self.assertEqual([peer["name"] for peer in snapshot["peers"]], ["alpha", "zeta"])

    def test_optional_commands_tolerate_timeouts(self):
        backend = SystemBackend()
        with patch(
            "hyprcontrol.system_backend.run_command",
            side_effect=subprocess.TimeoutExpired(["slow"], 10),
        ):
            self.assertEqual(backend._optional(["slow"]), "")
            with self.assertRaisesRegex(HyprControlError, "Could not run slow"):
                backend._required(["slow"])

    def test_snapshot_parsers_cover_hardware_categories(self):
        outputs = {
            ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"):
                "eno1:ethernet:connected:Wired\n",
            ("nmcli", "-g", "IP4.ADDRESS", "device", "show", "eno1"): "192.0.2.2/24\n",
            ("nmcli", "radio", "wifi"): "disabled\n",
            ("bluetoothctl", "show"): "Controller 00:11:22:33:44:55\n\tPowered: yes\n",
            ("bluetoothctl", "devices", "Paired"): "Device AA:BB:CC:DD:EE:FF Mouse\n",
            ("bluetoothctl", "devices", "Connected"): "Device AA:BB:CC:DD:EE:FF Mouse\n",
            ("pactl", "get-sink-volume", "@DEFAULT_SINK@"): "Volume: front-left: 39322 / 60% /\n",
            ("pactl", "get-sink-mute", "@DEFAULT_SINK@"): "Mute: no\n",
            ("pactl", "get-default-sink"): "sink.default\n",
            ("pactl", "get-default-source"): "source.default\n",
            ("pactl", "-f", "json", "list", "sinks"): json.dumps(
                [{"index": 1, "name": "sink.default", "description": "Speakers"}]
            ),
            ("pactl", "-f", "json", "list", "sources"): json.dumps(
                [{"index": 2, "name": "source.default", "description": "Microphone"}]
            ),
            ("hyprctl", "monitors", "all", "-j"): json.dumps(
                [{"name": "DP-2", "width": 3840, "height": 2160, "scale": 2}]
            ),
            ("lspci", "-mm"): '00:00.0 "VGA compatible controller" "NVIDIA" "RTX 3090"\n',
            ("omarchy", "theme", "current"): "Tokyo Night\n",
            ("omarchy", "theme", "list"): "Tokyo Night\nCatppuccin\n",
            ("powerprofilesctl", "list"): "* performance:\n  balanced:\n  power-saver:\n",
            ("timedatectl", "show", "--property=Timezone", "--property=NTPSynchronized"):
                "Timezone=America/Los_Angeles\nNTPSynchronized=yes\n",
            ("hostname",): "test-host\n",
        }

        def runner(command):
            return completed(command, stdout=outputs.get(tuple(command), ""))

        backend = SystemBackend()
        with patch("hyprcontrol.system_backend.run_command", side_effect=runner):
            self.assertEqual(backend._network_snapshot()["devices"][0]["address"], "192.0.2.2/24")
            self.assertTrue(backend._bluetooth_snapshot()["devices"][0]["connected"])
            self.assertEqual(backend._audio_snapshot()["volume"], 60)
            self.assertEqual(backend._audio_snapshot()["sinks"][0]["description"], "Speakers")
            self.assertEqual(backend._display_snapshot()["monitors"][0]["name"], "DP-2")
            self.assertEqual(backend._graphics_snapshot()["devices"][0]["model"], "RTX 3090")
            self.assertEqual(backend._appearance_snapshot()["theme"], "Tokyo Night")
            self.assertEqual(backend._power_snapshot()["active"], "performance")
            self.assertEqual(backend._date_time_snapshot()["timezone"], "America/Los_Angeles")


if __name__ == "__main__":
    unittest.main()
