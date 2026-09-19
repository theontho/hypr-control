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
  property string selectedLocale: ""
  property string selectedEffect: "random"
  property string startupCommand: ""
  property string message: ""
  property bool messageError: false

  clip: true
  ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

  function optionRows(values) {
    var rows = []
    for (var i = 0; i < (values || []).length; ++i) {
      var value = String(values[i])
      rows.push({ value: value, label: value === "random" ? "Random effects" : value })
    }
    return rows
  }

  function sync() {
    if (mode === "locale") selectedLocale = String(data.current || "")
    if (mode === "screensaver") selectedEffect = String(data.effect || "random")
  }

  onDataChanged: sync()
  onModeChanged: sync()

  Connections {
    target: root.backend
    ignoreUnknownSignals: true
    function onActionFinished(success, text) {
      root.messageError = !success
      root.message = text
      if (success && root.mode === "startup") root.startupCommand = ""
    }
  }

  Column {
    width: root.availableWidth
    spacing: Style.space(16)

    Column {
      width: parent.width
      spacing: Style.space(14)
      visible: root.mode === "backgrounds"

      Components.InfoRow {
        label: "Current background"
        value: root.data.current ? String(root.data.current).split("/").pop() : "Unknown"
      }
      Button {
        anchors.right: parent.right
        text: "Visual background picker"
        bordered: true
        selected: true
        onClicked: root.backend.run(["background-picker"], "Background applied.")
      }
      GridLayout {
        width: parent.width
        columns: width >= Style.space(760) ? 3 : 2
        columnSpacing: Style.space(12)
        rowSpacing: Style.space(12)

        Repeater {
          model: root.data.available || []
          Rectangle {
            required property var modelData
            Layout.fillWidth: true
            Layout.preferredHeight: Style.space(150)
            color: "transparent"
            border.width: String(root.data.current || "") === String(modelData.path) ? 2 : 1
            border.color: String(root.data.current || "") === String(modelData.path)
              ? Color.accent : Qt.darker(Color.foreground, 1.8)
            radius: Style.cornerRadius
            clip: true

            Image {
              anchors.fill: parent
              source: Util.fileUrl(String(parent.modelData.path))
              fillMode: Image.PreserveAspectCrop
              asynchronous: true
            }
            Rectangle {
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.bottom: parent.bottom
              height: Style.space(34)
              color: Qt.rgba(0, 0, 0, 0.7)
              Text {
                anchors.fill: parent
                anchors.margins: Style.space(8)
                text: parent.parent.modelData.name
                color: "white"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.backend.run(
                ["background-set", "--path", String(parent.modelData.path)],
                "Background applied."
              )
            }
          }
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(14)
      visible: root.mode === "controllers"
      PanelSectionHeader { text: "GAME CONTROLLERS"; foreground: Color.foreground }
      Text {
        visible: !root.data.devices || root.data.devices.length === 0
        text: "No game controllers detected."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.devices || []
        Components.InfoRow {
          required property var modelData
          label: modelData.name
          value: modelData.device
        }
      }
      Button {
        visible: root.data.managerAvailable === true
        anchors.right: parent.right
        text: "Open Steam controller settings"
        bordered: true
        onClicked: root.backend.run(["launch-tool", "--tool", "controllers"], "Controller settings opened.")
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(14)
      visible: root.mode === "printers"
      PanelSectionHeader { text: "PRINTERS"; foreground: Color.foreground }
      Text {
        visible: !root.data.printers || root.data.printers.length === 0
        text: "No printers configured."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.printers || []
        Components.InfoRow {
          required property var modelData
          label: modelData.name
          value: modelData.name === root.data.default ? "Default · " + modelData.status : modelData.status
        }
      }
      Button {
        visible: root.data.printerManagerAvailable === true
        anchors.right: parent.right
        text: "Manage printers"
        bordered: true
        onClicked: root.backend.run(["launch-tool", "--tool", "printers"], "Printer settings opened.")
      }
      PanelSeparator { foreground: Color.foreground }
      PanelSectionHeader { text: "SCANNERS"; foreground: Color.foreground }
      Text {
        visible: !root.data.scanners || root.data.scanners.length === 0
        text: root.data.scannerManagerAvailable === true
          ? "No scanners detected."
          : "Scanner support is not installed."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.scanners || []
        Components.InfoRow {
          required property var modelData
          label: modelData.name
          value: modelData.device
        }
      }
      Button {
        visible: root.data.scannerManagerAvailable === true
        anchors.right: parent.right
        text: "Open scanner"
        bordered: true
        onClicked: root.backend.run(["launch-tool", "--tool", "scanner"], "Scanner opened.")
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(14)
      visible: root.mode === "screensaver"
      Components.InfoRow { label: "Current effect"; value: root.data.effect || "random" }
      SearchableDropdown {
        width: parent.width
        label: "SCREENSAVER EFFECT"
        value: root.selectedEffect
        options: root.optionRows(root.data.effects || [])
        placeholderText: "Search effects..."
        onChanged: function(value) { root.selectedEffect = value }
      }
      Row {
        anchors.right: parent.right
        spacing: Style.space(10)
        Button {
          text: "Preview"
          bordered: true
          onClicked: root.backend.run(["launch-tool", "--tool", "screensaver"], "Screensaver opened.")
        }
        Button {
          text: "Apply effect"
          bordered: true
          selected: true
          onClicked: root.backend.run(
            ["screensaver-effect", "--effect", root.selectedEffect],
            "Screensaver effect applied."
          )
        }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(14)
      visible: root.mode === "startup"
      PanelSectionHeader { text: "STARTUP COMMANDS"; foreground: Color.foreground }
      Text {
        visible: !root.data.commands || root.data.commands.length === 0
        text: "No extra startup commands configured."
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Repeater {
        model: root.data.commands || []
        RowLayout {
          required property string modelData
          width: root.availableWidth
          Text {
            Layout.fillWidth: true
            text: modelData
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            elide: Text.ElideMiddle
          }
          Button {
            text: "Remove"
            bordered: true
            onClicked: root.backend.run(
              ["startup-command", "--command", modelData, "--enabled", "false"],
              "Startup command removed."
            )
          }
        }
      }
      TextField {
        width: parent.width
        text: root.startupCommand
        placeholderText: "Command to launch at login"
        onTextChanged: root.startupCommand = text
      }
      Button {
        anchors.right: parent.right
        text: "Add startup command"
        bordered: true
        selected: true
        enabled: root.startupCommand.trim() !== ""
        onClicked: root.backend.run(
          ["startup-command", "--command", root.startupCommand, "--enabled", "true"],
          "Startup command added."
        )
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(14)
      visible: root.mode === "locale"
      Components.InfoRow { label: "Current locale"; value: root.data.current || "Unknown" }
      SearchableDropdown {
        width: parent.width
        label: "SYSTEM LOCALE"
        value: root.selectedLocale
        options: root.optionRows(root.data.available || [])
        placeholderText: "Search locales..."
        onChanged: function(value) { root.selectedLocale = value }
      }
      Text {
        width: parent.width
        text: "Changing the locale requires administrator approval and applies fully after your next login."
        wrapMode: Text.Wrap
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
      Button {
        anchors.right: parent.right
        text: "Apply locale"
        bordered: true
        selected: true
        enabled: root.selectedLocale !== ""
        onClicked: root.backend.run(
          ["locale-set", "--locale", root.selectedLocale],
          "Locale applied. Sign out to update all applications."
        )
      }
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
