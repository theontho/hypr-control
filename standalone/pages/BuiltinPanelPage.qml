import QtQuick
import Quickshell
import qs.Commons
import "../BuiltinPanels/audio" as AudioPanel
import "../BuiltinPanels/bluetooth" as BluetoothPanel
import "../BuiltinPanels/monitor" as MonitorPanel
import "../BuiltinPanels/network" as NetworkPanel
import "../BuiltinPanels/tailscale" as TailscalePanel

Item {
  id: root

  property var backend: null
  property string mode: ""

  QtObject {
    id: embeddedShell

    function summon(moduleName, payload) {
      var command = [
        "quickshell", "ipc", "-p", "/usr/share/omarchy/shell",
        "call", moduleName, "show"
      ]
      if (payload !== undefined && String(payload) !== "") command.push(String(payload))
      Quickshell.execDetached(command)
    }

    function firstPartyServiceFor(moduleName) {
      return null
    }

    function updateEntryInline(moduleName, settings) {
      console.warn("Embedded panel settings persistence is unavailable for", moduleName)
      return false
    }
  }

  QtObject {
    id: embeddedBar

    property color foreground: Color.foreground
    property color barForeground: Color.foreground
    property color background: Color.background
    property color urgent: Color.urgent
    property string fontFamily: Style.font.family
    property string position: "top"
    property real barSize: 0
    property var activePopout: null
    property var clickTargets: []
    property QtObject shell: embeddedShell

    function requestPopout(owner) { activePopout = owner }
    function releasePopout(owner) { if (activePopout === owner) activePopout = null }
    function switchPanelFrom(owner, direction) { return false }
    function moduleWidgets(moduleName) { return [] }
    function targetBelongsToWindow(target, window) { return false }
    function run(command) { Quickshell.execDetached(["bash", "-lc", command]) }
  }

  Loader {
    id: panelLoader
    width: root.width
    height: root.height
    sourceComponent: {
      if (root.mode === "network") return networkComponent
      if (root.mode === "tailscale") return tailscaleComponent
      if (root.mode === "bluetooth") return bluetoothComponent
      if (root.mode === "sound") return audioComponent
      if (root.mode === "displays") return monitorComponent
      return null
    }

    onLoaded: {
      if (!item) return
      if (item.open) item.open()
    }
  }

  Component { id: networkComponent; NetworkPanel.Panel { bar: embeddedBar } }
  Component { id: tailscaleComponent; TailscalePanel.Panel { bar: embeddedBar } }
  Component { id: bluetoothComponent; BluetoothPanel.Panel { bar: embeddedBar } }
  Component { id: audioComponent; AudioPanel.Panel { bar: embeddedBar } }
  Component { id: monitorComponent; MonitorPanel.Panel { bar: embeddedBar } }

  Binding {
    target: panelLoader.item
    property: "width"
    value: panelLoader.width
    when: panelLoader.item
  }

  Binding {
    target: panelLoader.item
    property: "height"
    value: panelLoader.height
    when: panelLoader.item
  }

}
