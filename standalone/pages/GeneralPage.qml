import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "../components" as Components

ScrollView {
  id: root

  property var backend: null
  property var data: ({})
  property string mode: ""
  property string message: ""
  property bool messageError: false
  property int volume: 0
  property string selectedMonitor: ""
  property string selectedScale: "2"
  property string selectedTheme: ""
  property string selectedPowerProfile: ""
  property int screensaverMinutes: 0
  property int lockMinutes: 0
  property int nightTemperature: 1800

  readonly property var scaleOptions: [
    { value: "1", label: "100%" },
    { value: "1.25", label: "125%" },
    { value: "1.6", label: "160%" },
    { value: "2", label: "200%" },
    { value: "3", label: "300%" },
    { value: "4", label: "400%" }
  ]
  readonly property var nightTemperaturePresets: [1000, 1400, 1800, 2200, 3000, 4000]

  clip: true
  ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

  function bytes(value) {
    var number = Number(value || 0)
    var units = ["B", "KB", "MB", "GB", "TB"]
    var index = 0
    while (number >= 1024 && index < units.length - 1) {
      number /= 1024
      index++
    }
    return number.toFixed(index >= 3 ? 1 : 0) + " " + units[index]
  }

  function sync() {
    if (mode === "sound") volume = Number(data.volume || 0)
    if (mode === "displays" && data.monitors && data.monitors.length) {
      var monitor = data.monitors[0]
      for (var i = 0; i < data.monitors.length; i++)
        if (data.monitors[i].focused) monitor = data.monitors[i]
      selectedMonitor = monitor.name
      selectedScale = String(monitor.scale)
    }
    if (mode === "appearance") selectedTheme = String(data.theme || "")
    if (mode === "power") selectedPowerProfile = String(data.active || "")
    if (mode === "security") {
      screensaverMinutes = Math.round(Number(data.screensaverSeconds || 0) / 60)
      lockMinutes = Math.round(Number(data.lockSeconds || 0) / 60)
    }
    if (mode === "nightlight")
      nightTemperature = Number(data.configuredTemperature || 1800)
  }

  function themeOptions() {
    var result = []
    var themes = data.themes || []
    for (var i = 0; i < themes.length; i++)
      result.push({ value: themes[i], label: themes[i] })
    return result
  }

  function monitorOptions() {
    var result = []
    var monitors = data.monitors || []
    for (var i = 0; i < monitors.length; i++)
      result.push({ value: monitors[i].name, label: monitors[i].name })
    return result
  }

  function applyNightTemperature(value) {
    nightTemperature = Math.round(Number(value) / 100) * 100
    if (!backend || backend.busy) return
    backend.run(
      ["nightlight-temperature", "--kelvin", String(nightTemperature)],
      "Night-light temperature applied."
    )
  }

  onDataChanged: sync()
  onModeChanged: sync()
  Component.onCompleted: sync()

  Connections {
    target: root.backend
    ignoreUnknownSignals: true
    function onActionFinished(success, text) {
      root.messageError = !success
      root.message = text
    }
  }

  Column {
    width: root.availableWidth
    spacing: Style.space(16)

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "network"

      Item {
        width: parent.width
        implicitHeight: Math.max(wifiLabel.implicitHeight, wifiSwitch.implicitHeight)
        Text {
          id: wifiLabel
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          text: root.data.wifiPresent ? "Wi-Fi" : "Wi-Fi hardware not detected"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }
        ToggleSwitch {
          id: wifiSwitch
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          visible: root.data.wifiPresent === true
          checked: root.data.wifiEnabled === true
          busy: root.backend && root.backend.busy
          onToggled: root.backend.run(
            ["wifi-power", "--enabled", checked ? "false" : "true"],
            checked ? "Wi-Fi disabled." : "Wi-Fi enabled."
          )
        }
      }

      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "NETWORK INTERFACES"; foreground: Color.foreground }

      Repeater {
        model: root.data.devices || []
        Column {
          required property var modelData
          width: parent.width
          spacing: Style.space(2)
          Components.InfoRow {
            label: String(modelData.device || "") + " · " + String(modelData.type || "")
            value: String(modelData.state || "")
          }
          Components.InfoRow {
            label: String(modelData.connection || "")
            value: String(modelData.address || "")
          }
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "tailscale"

      Item {
        width: parent.width
        implicitHeight: Math.max(tailscaleLabel.implicitHeight, tailscaleSwitch.implicitHeight)
        Text {
          id: tailscaleLabel
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          text: root.data.installed
            ? "Tailscale · " + String(root.data.state || "Unknown")
            : "Tailscale is not installed"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }
        ToggleSwitch {
          id: tailscaleSwitch
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          visible: root.data.installed === true
          checked: root.data.active === true
          busy: root.backend && root.backend.busy
          onToggled: root.backend.run(
            ["tailscale-power", "--enabled", checked ? "false" : "true"],
            checked ? "Tailscale turned off." : "Tailscale turned on."
          )
        }
      }
      Repeater {
        model: root.data.addresses || []
        Components.InfoRow {
          required property var modelData
          label: "This device"
          value: String(modelData)
        }
      }
      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "TAILNET PEERS"; foreground: Color.foreground }
      Repeater {
        model: root.data.peers || []
        Components.InfoRow {
          required property var modelData
          label: String(modelData.name || "")
          value: (modelData.online ? "Online" : "Offline") + (modelData.address ? " · " + modelData.address : "")
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "bluetooth"

      Item {
        width: parent.width
        implicitHeight: Math.max(bluetoothLabel.implicitHeight, bluetoothSwitch.implicitHeight)
        Text {
          id: bluetoothLabel
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          text: root.data.available ? "Bluetooth power" : "Bluetooth adapter not detected"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }
        ToggleSwitch {
          id: bluetoothSwitch
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          visible: root.data.available === true
          checked: root.data.powered === true
          busy: root.backend && root.backend.busy
          onToggled: root.backend.run(
            ["bluetooth-power", "--enabled", checked ? "false" : "true"],
            checked ? "Bluetooth disabled." : "Bluetooth enabled."
          )
        }
      }

      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "PAIRED DEVICES"; foreground: Color.foreground }
      Text {
        visible: !root.data.devices || root.data.devices.length === 0
        text: "No paired Bluetooth devices."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.devices || []
        Item {
          required property var modelData
          width: parent.width
          implicitHeight: Math.max(deviceName.implicitHeight, deviceButton.implicitHeight)
          Text {
            id: deviceName
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: String(modelData.name || "")
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
          }
          Button {
            id: deviceButton
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: modelData.connected ? "Disconnect" : "Connect"
            bordered: true
            onClicked: root.backend.run([
              "bluetooth-device",
              "--address", modelData.address,
              "--action", modelData.connected ? "disconnect" : "connect"
            ], modelData.connected ? "Bluetooth device disconnected." : "Bluetooth device connected.")
          }
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "sound"

      Components.InfoRow { label: "Output volume"; value: root.volume + "%" }
      PanelSlider {
        width: parent.width
        minimum: 0
        maximum: 150
        step: 1
        integer: true
        value: root.volume
        onMoved: function(value) { root.volume = Math.round(value) }
        onReleased: function(value) {
          root.volume = Math.round(value)
          root.backend.run(["audio-volume", "--percent", String(root.volume)], "Output volume changed.")
        }
      }
      Button {
        text: root.data.muted ? "Unmute output" : "Mute output"
        bordered: true
        onClicked: root.backend.run(["audio-mute"], root.data.muted ? "Output unmuted." : "Output muted.")
      }
      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "OUTPUT DEVICES"; foreground: Color.foreground }
      Repeater {
        model: root.data.sinks || []
        Item {
          required property var modelData
          width: parent.width
          implicitHeight: Math.max(outputName.implicitHeight, outputButton.implicitHeight)
          Text {
            id: outputName
            anchors.left: parent.left
            anchors.right: outputButton.left
            anchors.rightMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            text: String(modelData.description || modelData.name || "")
            color: Color.foreground
            elide: Text.ElideRight
            font.family: Style.font.family
            font.pixelSize: Style.font.body
          }
          Button {
            id: outputButton
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: modelData.default ? "Default" : "Use"
            bordered: true
            enabled: !modelData.default && root.backend && !root.backend.busy
            onClicked: root.backend.run([
              "audio-default", "--kind", "sink",
              "--id", String(modelData.id), "--name", modelData.name
            ], "Default output changed.")
          }
        }
      }
      PanelSectionHeader { text: "INPUT DEVICES"; foreground: Color.foreground }
      Repeater {
        model: root.data.sources || []
        Item {
          required property var modelData
          width: parent.width
          implicitHeight: Math.max(inputName.implicitHeight, inputButton.implicitHeight)
          Text {
            id: inputName
            anchors.left: parent.left
            anchors.right: inputButton.left
            anchors.rightMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            text: String(modelData.description || modelData.name || "")
            color: Color.foreground
            elide: Text.ElideRight
            font.family: Style.font.family
            font.pixelSize: Style.font.body
          }
          Button {
            id: inputButton
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: modelData.default ? "Default" : "Use"
            bordered: true
            enabled: !modelData.default && root.backend && !root.backend.busy
            onClicked: root.backend.run([
              "audio-default", "--kind", "source",
              "--id", String(modelData.id), "--name", modelData.name
            ], "Default input changed.")
          }
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "displays"

      Dropdown {
        width: parent.width
        label: "MONITOR"
        value: root.selectedMonitor
        options: root.monitorOptions()
        onChanged: function(value) {
          root.selectedMonitor = value
          var monitors = root.data.monitors || []
          for (var i = 0; i < monitors.length; i++)
            if (monitors[i].name === value) root.selectedScale = String(monitors[i].scale)
        }
      }
      Repeater {
        model: root.data.monitors || []
        Column {
          required property var modelData
          width: parent.width
          visible: String(modelData.name || "") === root.selectedMonitor
          Components.InfoRow { label: "Model"; value: String(modelData.description || "") }
          Components.InfoRow { label: "Resolution"; value: modelData.width + " × " + modelData.height }
          Components.InfoRow { label: "Refresh rate"; value: Number(modelData.refreshRate).toFixed(2) + " Hz" }
        }
      }
      Dropdown {
        width: parent.width
        label: "DISPLAY SCALE"
        value: root.selectedScale
        options: root.scaleOptions
        onChanged: function(value) { root.selectedScale = value }
      }
      Button {
        anchors.right: parent.right
        text: "Apply scale"
        bordered: true
        selected: true
        onClicked: root.backend.run([
          "display-scale",
          "--monitor", root.selectedMonitor,
          "--scale", root.selectedScale
        ], "Display scale applied.")
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "graphics"
      PanelSectionHeader { text: "GRAPHICS"; foreground: Color.foreground }
      Repeater {
        model: root.data.devices || []
        Components.InfoRow {
          required property var modelData
          label: String(modelData.vendor || "")
          value: String(modelData.model || "")
        }
      }
      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "VIDEO DEVICES"; foreground: Color.foreground }
      Text {
        visible: !root.data.cameras || root.data.cameras.length === 0
        text: "No camera devices detected."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.cameras || []
        Components.InfoRow {
          required property var modelData
          label: String(modelData.device || "")
          value: String(modelData.name || "")
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "appearance"
      Components.InfoRow { label: "Current theme"; value: root.data.theme || "Unknown" }
      Dropdown {
        width: parent.width
        label: "OMARCHY THEME"
        value: root.selectedTheme
        options: root.themeOptions()
        onChanged: function(value) { root.selectedTheme = value }
      }
      Row {
        anchors.right: parent.right
        spacing: Style.space(10)
        Button {
          text: "Visual theme picker"
          bordered: true
          onClicked: root.backend.run(["launch-tool", "--tool", "themes"], "Theme applied.")
        }
        Button {
          text: "Apply theme"
          bordered: true
          selected: true
          onClicked: root.backend.run(["theme-set", "--theme", root.selectedTheme], "Theme applied.")
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "power"
      PanelSectionHeader { text: "POWER PROFILE"; foreground: Color.foreground }
      ButtonGroup {
        options: [
          { value: "power-saver", label: "Saver" },
          { value: "balanced", label: "Balanced" },
          { value: "performance", label: "Performance" }
        ]
        value: root.selectedPowerProfile
        onChanged: function(value) {
          root.selectedPowerProfile = value
          root.backend.run(["power-profile", "--profile", value], "Power profile changed.")
        }
      }
      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "BATTERY"; foreground: Color.foreground }
      Text {
        visible: !root.data.batteries || root.data.batteries.length === 0
        text: "No battery detected on this device."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.batteries || []
        Column {
          required property var modelData
          width: parent.width
          Components.InfoRow {
            label: String(modelData.name || "")
            value: String(modelData.capacity === null ? "Unavailable" : modelData.capacity + "%") + " · " + String(modelData.status || "")
          }
          Components.InfoRow { label: "Battery health"; value: modelData.health === null ? "Unavailable" : modelData.health + "%" }
          Components.InfoRow { label: "Cycle count"; value: modelData.cycleCount === null ? "Unavailable" : String(modelData.cycleCount) }
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "storage"
      Components.InfoRow { label: "Capacity"; value: root.bytes(root.data.root ? root.data.root.total : 0) }
      Components.InfoRow { label: "Used"; value: root.bytes(root.data.root ? root.data.root.used : 0) }
      Components.InfoRow { label: "Available"; value: root.bytes(root.data.root ? root.data.root.free : 0) }
      PanelSlider {
        width: parent.width
        enabled: false
        minimum: 0
        maximum: Math.max(1, Number(root.data.root ? root.data.root.total : 1))
        value: Number(root.data.root ? root.data.root.used : 0)
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "datetime"
      Components.InfoRow { label: "Timezone"; value: root.data.timezone || "Unknown" }
      Components.InfoRow { label: "Network time"; value: root.data.ntpSynchronized ? "Synchronized" : "Not synchronized" }
      Button {
        anchors.right: parent.right
        text: "Choose timezone"
        bordered: true
        onClicked: root.backend.run(["launch-tool", "--tool", "timezone"], "Timezone picker opened.")
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "nightlight"

      Components.InfoRow {
        label: "Status"
        value: root.data.enabled
          ? "On · " + Number(root.data.currentTemperature || root.nightTemperature) + "K"
          : "Off"
      }
      Components.InfoRow {
        label: "Night temperature"
        value: root.nightTemperature + "K"
      }
      Item {
        width: parent.width
        implicitHeight: kelvinSlider.implicitHeight

        PanelSlider {
          id: kelvinSlider
          anchors.fill: parent
          minimum: 1000
          maximum: 5500
          step: 100
          integer: true
          value: root.nightTemperature
          onMoved: function(value) { root.nightTemperature = Math.round(value / 100) * 100 }
          onReleased: function(value) { root.applyNightTemperature(value) }
        }

        Repeater {
          model: root.nightTemperaturePresets
          Rectangle {
            required property int modelData
            readonly property real position: (modelData - kelvinSlider.minimum)
              / (kelvinSlider.maximum - kelvinSlider.minimum)
            visible: root.nightTemperature !== modelData
            width: Math.max(1, Style.space(2))
            height: kelvinSlider.trackHeight + Style.space(4)
            radius: width / 2
            color: Color.background
            anchors.verticalCenter: parent.verticalCenter
            x: Math.max(0, Math.min(parent.width - width, parent.width * position - width / 2))
          }
        }
      }
      GridLayout {
        width: parent.width
        columns: 3
        columnSpacing: Style.space(8)
        rowSpacing: Style.space(8)

        Repeater {
          model: root.nightTemperaturePresets
          Button {
            required property int modelData
            Layout.fillWidth: true
            text: modelData + "K"
            bordered: true
            selected: root.nightTemperature === modelData
            enabled: root.backend && !root.backend.busy
            onClicked: root.applyNightTemperature(modelData)
          }
        }
      }
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: "Lower Kelvin values are redder. This setting is shared by the scheduled Hyprsunset profile and the Stream Deck night-mode controls."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Row {
        anchors.right: parent.right
        spacing: Style.space(10)
        Button {
          text: root.data.enabled ? "Turn off" : "Turn on"
          bordered: true
          onClicked: root.backend.run(
            ["nightlight-toggle"],
            root.data.enabled ? "Night light turned off." : "Night light turned on."
          )
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "security"
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: "Set either timer to 0 to disable it."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Row {
        spacing: Style.space(24)
        NumberField {
          label: "SCREENSAVER (MIN)"
          value: root.screensaverMinutes
          from: 0
          to: 1440
          onModified: function(value) { root.screensaverMinutes = value }
        }
        NumberField {
          label: "LOCK (MIN)"
          value: root.lockMinutes
          from: 0
          to: 1440
          onModified: function(value) { root.lockMinutes = value }
        }
      }
      Button {
        anchors.right: parent.right
        text: "Apply idle settings"
        bordered: true
        selected: true
        onClicked: root.backend.run([
          "idle-apply",
          "--screensaver", String(root.screensaverMinutes * 60),
          "--lock", String(root.lockMinutes * 60)
        ], "Idle and lock settings applied.")
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "updates"
      Components.InfoRow { label: "Last package update"; value: root.data.lastUpdate || "Unknown" }
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: "Updates run through Omarchy's existing terminal workflow so package prompts and failures remain visible."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Button {
        anchors.right: parent.right
        text: "Open Omarchy Update"
        bordered: true
        selected: true
        onClicked: root.backend.run(["launch-tool", "--tool", "updates"], "Update terminal opened.")
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(12)
      visible: root.mode === "about"
      Components.InfoRow { label: "Device name"; value: root.data.hostname || "" }
      Components.InfoRow { label: "Operating system"; value: root.data.os || "" }
      Components.InfoRow { label: "Kernel"; value: root.data.kernel || "" }
      Components.InfoRow { label: "Architecture"; value: root.data.architecture || "" }
      Components.InfoRow { label: "Processor"; value: root.data.cpu || "" }
      Components.InfoRow { label: "Memory"; value: root.bytes(root.data.memoryTotal || 0) }
    }

    Text {
      width: parent.width
      visible: root.message !== ""
      wrapMode: Text.Wrap
      text: root.message
      color: root.messageError ? Color.urgent : Qt.darker(Color.foreground, 1.35)
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
    }
  }
}
