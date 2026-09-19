#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
from pathlib import Path


SOURCE_ROOT = Path("/usr/share/omarchy/shell/plugins/panels")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESTINATION_ROOT = PROJECT_ROOT / "standalone/BuiltinPanels"
PANELS = ("audio", "bluetooth", "monitor", "network", "tailscale")


def block_bounds(source: str, marker: str) -> tuple[int, int]:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False

    for index in range(opening, len(source)):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
            continue
        if block_comment:
            if char == "*" and following == "/":
                block_comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char == "/" and following == "/":
            line_comment = True
            continue
        if char == "/" and following == "*":
            block_comment = True
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                if end < len(source) and source[end] == "\n":
                    end += 1
                return start, end

    raise ValueError(f"Unclosed block beginning with {marker!r}")


def remove_blocks(source: str, marker: str) -> str:
    while marker in source:
        start, end = block_bounds(source, marker)
        source = source[:start] + source[end:]
    return source


def adapt_panel(source: str) -> str:
    defines_close = re.search(r"^  function close\(\)", source, re.MULTILINE) is not None
    source = source.replace("Panel {\n  id: root", "Item {\n  id: root", 1)
    close_function = "" if defines_close else "  function close() { embeddedController.hide() }\n"
    compatibility = """

  property QtObject bar: null
  property string moduleName
  property var settings: ({})
  property string ipcTarget
  property bool manageIpc
  property bool popoutSwitching: false
  property bool popoutSwitchClosing: false
  property bool opened: true
  readonly property color barForeground: bar ? bar.barForeground : Color.foreground
  property alias controller: embeddedController

  function open() { embeddedController.show() }
__CLOSE_FUNCTION__  function closeForPopoutSwitch() {
    popoutSwitchClosing = true
    close()
    Qt.callLater(function() { popoutSwitchClosing = false })
  }
  function toggle() { opened ? close() : open() }
  function switchPanel(direction) { return false }
  function setting(name, fallback) {
    var value = settings ? settings[name] : undefined
    return value === undefined || value === null ? fallback : value
  }

  QtObject {
    id: embeddedController
    function show() { root.opened = true }
    function hide() { root.opened = false }
  }
""".replace("__CLOSE_FUNCTION__", close_function)
    source = source.replace("Item {\n  id: root", "Item {\n  id: root" + compatibility, 1)
    source = remove_blocks(source, "  IpcHandler {")
    button_start, button_end = block_bounds(source, "  BarIconButton {")
    source = source[:button_start] + "  Item { id: button; visible: false }\n\n" + source[button_end:]
    source = source.replace("  KeyboardPanel {\n", "  Item {\n    anchors.fill: parent\n", 1)
    source = re.sub(
        r"^    (anchorItem|owner|bar|open|focusTarget|contentWidth|contentHeight):.*\n",
        "",
        source,
        flags=re.MULTILINE,
    )
    source = re.sub(
        r"(?m)^(\s*)Column \{\n(\s*)id: (panelColumn|column)\n",
        r"\1Column {\n\2id: \3\n\2height: childrenRect.height\n",
        source,
        count=1,
    )
    return "// Generated from the installed Omarchy panel. Do not edit directly.\n" + source


def main() -> None:
    if DESTINATION_ROOT.exists():
        shutil.rmtree(DESTINATION_ROOT)
    DESTINATION_ROOT.mkdir(parents=True, exist_ok=True)
    for panel in PANELS:
        source_directory = SOURCE_ROOT / panel
        destination = DESTINATION_ROOT / panel
        shutil.copytree(source_directory, destination)
        panel_path = destination / "Panel.qml"
        panel_path.write_text(adapt_panel(panel_path.read_text(encoding="utf-8")), encoding="utf-8")
        qml_types = []
        for qml_path in sorted(destination.glob("*.qml")):
            qml_types.append(f"{qml_path.stem} 1.0 {qml_path.name}")
        (destination / "qmldir").write_text("\n".join(qml_types) + "\n", encoding="utf-8")
    print(f"Synchronized {len(PANELS)} Omarchy panels into {DESTINATION_ROOT}")


if __name__ == "__main__":
    main()
