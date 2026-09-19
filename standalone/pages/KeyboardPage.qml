import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "../components"

ScrollView {
  id: root

  property var backend: null
  property var data: ({})
  property string layoutValue: "us"
  property string variantValue: ""
  property string optionsValue: ""
  property int repeatRate: 40
  property int repeatDelay: 250
  property bool numlock: true
  property string message: ""
  property bool messageError: false

  clip: true
  ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

  function sync() {
    layoutValue = String(data.layout || "us")
    variantValue = String(data.variant || "")
    optionsValue = String(data.options || "")
    repeatRate = Number(data.repeat_rate || 40)
    repeatDelay = Number(data.repeat_delay || 250)
    numlock = data.numlock !== false
  }

  onDataChanged: sync()
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

    PanelSectionHeader { text: "LAYOUT"; foreground: Color.foreground }
    TextField {
      width: parent.width
      text: root.layoutValue
      placeholderText: "us"
      onTextChanged: root.layoutValue = text
    }

    PanelSectionHeader { text: "VARIANT"; foreground: Color.foreground }
    TextField {
      width: parent.width
      text: root.variantValue
      placeholderText: "Optional, for example intl"
      onTextChanged: root.variantValue = text
    }

    PanelSectionHeader { text: "XKB OPTIONS"; foreground: Color.foreground }
    TextField {
      width: parent.width
      text: root.optionsValue
      placeholderText: "compose:caps,shift:both_capslock_cancel"
      onTextChanged: root.optionsValue = text
    }

    Row {
      spacing: Style.space(24)
      NumberField {
        label: "REPEAT RATE"
        value: root.repeatRate
        from: 1
        to: 100
        onModified: function(value) { root.repeatRate = value }
      }
      NumberField {
        label: "REPEAT DELAY (MS)"
        value: root.repeatDelay
        from: 100
        to: 2000
        stepSize: 50
        onModified: function(value) { root.repeatDelay = value }
      }
    }

    Item {
      width: parent.width
      implicitHeight: Math.max(numlockLabel.implicitHeight, numlockSwitch.implicitHeight)
      Text {
        id: numlockLabel
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: "Enable Num Lock by default"
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      ToggleSwitch {
        id: numlockSwitch
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        checked: root.numlock
        onToggled: root.numlock = !root.numlock
      }
    }

    Button {
      anchors.right: parent.right
      text: root.backend && root.backend.busy ? "Applying..." : "Apply"
      bordered: true
      selected: true
      enabled: root.backend && !root.backend.busy
      onClicked: root.backend.run([
        "keyboard-apply",
        "--layout", root.layoutValue,
        "--variant", root.variantValue,
        "--options", root.optionsValue,
        "--repeat-rate", String(root.repeatRate),
        "--repeat-delay", String(root.repeatDelay),
        "--numlock", root.numlock ? "true" : "false"
      ], "Keyboard settings applied.")
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
