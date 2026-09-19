from __future__ import annotations

import argparse
import json
import sys

from .backend import HyprBackend, HyprControlError
from .system_backend import SystemBackend


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backend for the Hypr Control Quickshell panel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("snapshot", help="Print current settings and hardware state")

    apply_parser = subparsers.add_parser("input-apply", aliases=["apply"], help="Apply settings to one pointer device")
    apply_parser.add_argument("--device", required=True)
    apply_parser.add_argument(
        "--profile",
        choices=("adaptive", "flat", "windows", "macos", "custom"),
        required=True,
    )
    apply_parser.add_argument("--sensitivity", type=float, required=True)
    apply_parser.add_argument("--curve-scale", type=float, required=True)
    apply_parser.add_argument("--curve-gain", type=float, default=1.0)
    apply_parser.add_argument("--curve-step", type=float, default=0.3431164009)
    apply_parser.add_argument("--curve-points", default="")

    reset_parser = subparsers.add_parser("input-reset", aliases=["reset"], help="Remove one pointer override")
    reset_parser.add_argument("--device", required=True)

    keyboard = subparsers.add_parser("keyboard-apply", help="Apply keyboard settings")
    keyboard.add_argument("--layout", required=True)
    keyboard.add_argument("--variant", default="")
    keyboard.add_argument("--options", default="")
    keyboard.add_argument("--repeat-rate", type=int, required=True)
    keyboard.add_argument("--repeat-delay", type=int, required=True)
    keyboard.add_argument("--numlock", choices=("true", "false"), required=True)

    wifi = subparsers.add_parser("wifi-power", help="Turn Wi-Fi on or off")
    wifi.add_argument("--enabled", choices=("true", "false"), required=True)

    bluetooth = subparsers.add_parser("bluetooth-power", help="Turn Bluetooth on or off")
    bluetooth.add_argument("--enabled", choices=("true", "false"), required=True)

    bluetooth_device = subparsers.add_parser("bluetooth-device", help="Connect or disconnect a device")
    bluetooth_device.add_argument("--address", required=True)
    bluetooth_device.add_argument("--action", choices=("connect", "disconnect"), required=True)

    volume = subparsers.add_parser("audio-volume", help="Set output volume")
    volume.add_argument("--percent", type=int, required=True)
    subparsers.add_parser("audio-mute", help="Toggle output mute")
    audio_default = subparsers.add_parser("audio-default", help="Select a default audio device")
    audio_default.add_argument("--kind", choices=("sink", "source"), required=True)
    audio_default.add_argument("--id", type=int, required=True)
    audio_default.add_argument("--name", required=True)

    tailscale = subparsers.add_parser("tailscale-power", help="Turn Tailscale on or off")
    tailscale.add_argument("--enabled", choices=("true", "false"), required=True)

    display = subparsers.add_parser("display-scale", help="Set monitor scale")
    display.add_argument("--monitor", required=True)
    display.add_argument("--scale", type=float, required=True)

    power = subparsers.add_parser("power-profile", help="Set the power profile")
    power.add_argument("--profile", choices=("power-saver", "balanced", "performance"), required=True)

    theme = subparsers.add_parser("theme-set", help="Apply an Omarchy theme")
    theme.add_argument("--theme", required=True)

    background = subparsers.add_parser("background-set", help="Apply a desktop background")
    background.add_argument("--path", required=True)
    subparsers.add_parser("background-picker", help="Choose and apply a desktop background")

    screensaver = subparsers.add_parser("screensaver-effect", help="Set the screensaver effect")
    screensaver.add_argument("--effect", required=True)

    locale = subparsers.add_parser("locale-set", help="Set the system locale")
    locale.add_argument("--locale", required=True)

    startup = subparsers.add_parser("startup-command", help="Enable or disable a startup command")
    startup.add_argument("--command", dest="startup_command", required=True)
    startup.add_argument("--enabled", choices=("true", "false"), required=True)

    idle = subparsers.add_parser("idle-apply", help="Apply screensaver and lock timers")
    idle.add_argument("--screensaver", type=int, required=True)
    idle.add_argument("--lock", type=int, required=True)

    night_light = subparsers.add_parser(
        "nightlight-temperature",
        help="Set the shared Hyprsunset and Stream Deck night temperature",
    )
    night_light.add_argument("--kelvin", type=int, required=True)
    subparsers.add_parser("nightlight-toggle", help="Toggle night light")

    launch = subparsers.add_parser("launch-tool", help="Open an existing Omarchy settings workflow")
    launch.add_argument(
        "--tool",
        choices=("timezone", "updates", "themes", "printers", "scanner", "controllers", "screensaver"),
        required=True,
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backend = HyprBackend()
    system = SystemBackend()

    try:
        if args.command == "snapshot":
            result = system.snapshot()
        elif args.command in {"input-apply", "apply"}:
            curve_points = json.loads(args.curve_points) if args.curve_points else None
            backend.apply_device(
                args.device,
                profile=args.profile,
                sensitivity=args.sensitivity,
                curve_scale=args.curve_scale,
                curve_gain=args.curve_gain,
                curve_step=args.curve_step,
                curve_points=curve_points,
            )
            result = {"ok": True}
        elif args.command in {"input-reset", "reset"}:
            backend.reset_device(args.device)
            result = {"ok": True}
        elif args.command == "keyboard-apply":
            backend.apply_keyboard(
                layout=args.layout,
                variant=args.variant,
                options=args.options,
                repeat_rate=args.repeat_rate,
                repeat_delay=args.repeat_delay,
                numlock=args.numlock == "true",
            )
            result = {"ok": True}
        elif args.command == "wifi-power":
            system.set_wifi_power(args.enabled == "true")
            result = {"ok": True}
        elif args.command == "bluetooth-power":
            system.set_bluetooth_power(args.enabled == "true")
            result = {"ok": True}
        elif args.command == "bluetooth-device":
            system.bluetooth_device(args.address, args.action)
            result = {"ok": True}
        elif args.command == "audio-volume":
            system.set_audio_volume(args.percent)
            result = {"ok": True}
        elif args.command == "audio-mute":
            system.toggle_audio_mute()
            result = {"ok": True}
        elif args.command == "audio-default":
            system.set_audio_default(args.kind, args.id, args.name)
            result = {"ok": True}
        elif args.command == "tailscale-power":
            system.set_tailscale_enabled(args.enabled == "true")
            result = {"ok": True}
        elif args.command == "display-scale":
            system.set_display_scale(args.monitor, args.scale)
            result = {"ok": True}
        elif args.command == "power-profile":
            system.set_power_profile(args.profile)
            result = {"ok": True}
        elif args.command == "theme-set":
            system.set_theme(args.theme)
            result = {"ok": True}
        elif args.command == "background-set":
            system.set_background(args.path)
            result = {"ok": True}
        elif args.command == "background-picker":
            system.choose_background()
            result = {"ok": True}
        elif args.command == "screensaver-effect":
            system.set_screensaver_effect(args.effect)
            result = {"ok": True}
        elif args.command == "locale-set":
            system.set_locale(args.locale)
            result = {"ok": True}
        elif args.command == "startup-command":
            system.set_startup_command(args.startup_command, args.enabled == "true")
            result = {"ok": True}
        elif args.command == "idle-apply":
            system.set_idle(
                screensaver_seconds=args.screensaver,
                lock_seconds=args.lock,
            )
            result = {"ok": True}
        elif args.command == "nightlight-temperature":
            system.set_night_light_temperature(args.kelvin)
            result = {"ok": True}
        elif args.command == "nightlight-toggle":
            system.toggle_night_light()
            result = {"ok": True}
        elif args.command == "launch-tool":
            system.launch_tool(args.tool)
            result = {"ok": True}
        else:
            raise HyprControlError(f"Unsupported command: {args.command}")
    except HyprControlError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
