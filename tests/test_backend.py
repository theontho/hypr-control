import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from hyprcontrol.backend import HyprBackend, HyprControlError


def completed(command, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class BackendTests(unittest.TestCase):
    def test_windows_profile_scales_curve_without_sensitivity(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {
                        "test-mouse": {
                            "profile": "windows",
                            "sensitivity": -0.5,
                            "curve_scale": 0.4,
                        }
                    },
                }
            )

        self.assertIn('name = "test-mouse"', lua)
        self.assertIn("custom 0.3431164009 0.000 0.103", lua)
        self.assertNotIn("sensitivity", lua)

    def test_flat_profile_writes_sensitivity(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {
                        "test-mouse": {
                            "profile": "flat",
                            "sensitivity": -0.25,
                            "curve_scale": 0.4,
                        }
                    },
                }
            )

        self.assertIn('accel_profile = "flat"', lua)
        self.assertIn("sensitivity = -0.25", lua)

    def test_macos_profile_writes_cubic_approximation(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {
                        "test-mouse": {
                            "profile": "macos",
                            "sensitivity": 0,
                            "curve_scale": 0.4,
                        }
                    },
                }
            )

        self.assertIn("custom 0.5000000000 0.000 0.053 0.115", lua)
        self.assertNotIn("sensitivity", lua)

    def test_macos_profile_applies_pointer_speed_gain(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {
                        "test-mouse": {
                            "profile": "macos",
                            "sensitivity": 0,
                            "curve_scale": 0.4,
                            "curve_gain": 0.5,
                        }
                    },
                }
            )

        self.assertIn("custom 0.5000000000 0.000 0.026 0.058", lua)

    def test_macos_profile_exposes_generated_graph_points(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            backend.state_path.parent.mkdir(parents=True)
            backend.state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "devices": {
                            "test-mouse": {
                                "profile": "macos",
                                "sensitivity": 0,
                                "curve_scale": 0.4,
                                "curve_step": 0.5,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            settings = backend.device_settings("test-mouse")

        self.assertEqual(settings["curve_step"], 0.5)
        self.assertEqual(settings["curve_points"][:4], [0.0, 0.053, 0.115, 0.189])
        self.assertEqual(settings["curve_points"][-1], 6.139)

    def test_custom_profile_writes_edited_points(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {
                        "test-mouse": {
                            "profile": "custom",
                            "sensitivity": 0,
                            "curve_scale": 0.4,
                            "curve_step": 0.25,
                            "curve_points": [0, 0.2, 0.7, 1.5],
                        }
                    },
                }
            )

        self.assertIn("custom 0.2500000000 0.000 0.200 0.700 1.500", lua)

    def test_custom_profile_applies_pointer_speed_gain(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {
                        "test-mouse": {
                            "profile": "custom",
                            "sensitivity": 0,
                            "curve_scale": 0.4,
                            "curve_gain": 0.5,
                            "curve_step": 0.25,
                            "curve_points": [0, 0.2, 0.7, 1.5],
                        }
                    },
                }
            )

        self.assertIn("custom 0.2500000000 0.000 0.100 0.350 0.750", lua)

    def test_keyboard_settings_render_as_input_override(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = HyprBackend(home=Path(directory))
            lua = backend.render_lua(
                {
                    "version": 1,
                    "devices": {},
                    "keyboard": {
                        "layout": "us",
                        "variant": "",
                        "options": "compose:caps",
                        "repeat_rate": 40,
                        "repeat_delay": 250,
                        "numlock": True,
                    },
                }
            )

        self.assertIn('kb_layout = "us"', lua)
        self.assertIn("repeat_rate = 40", lua)
        self.assertIn("numlock_by_default = true", lua)

    def test_apply_rolls_back_when_hyprland_reports_error(self):
        calls = []

        def runner(command):
            calls.append(command)
            if command == ["hyprctl", "configerrors"]:
                return completed(command, stdout="bad generated config")
            return completed(command)

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            backend = HyprBackend(home=home, runner=runner)
            backend.state_path.parent.mkdir(parents=True)
            backend.lua_path.parent.mkdir(parents=True)
            backend.input_path.write_text(
                'require("hypr.hypr_control")\n',
                encoding="utf-8",
            )
            original_state = {"version": 1, "devices": {}}
            backend.state_path.write_text(json.dumps(original_state), encoding="utf-8")
            backend.lua_path.write_text("-- original\n", encoding="utf-8")

            with self.assertRaises(HyprControlError):
                backend.apply_device(
                    "test-mouse",
                    profile="flat",
                    sensitivity=0.2,
                    curve_scale=0.4,
                )

            self.assertEqual(json.loads(backend.state_path.read_text()), original_state)
            self.assertEqual(backend.lua_path.read_text(), "-- original\n")
            self.assertEqual(calls.count(["hyprctl", "reload"]), 2)


if __name__ == "__main__":
    unittest.main()
