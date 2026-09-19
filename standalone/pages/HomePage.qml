import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons
import "../components" as Components

ScrollView {
  id: root

  property var data: ({})
  signal openPage(string page)
  readonly property real tileScale: Math.max(
    0.72,
    Math.min(1.35, root.availableWidth / Style.space(900))
  )

  clip: true
  ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

  readonly property var entries: [
    { page: "mouse", icon: "󰍽", title: "Mouse", subtitle: "Speed and curves" },
    { page: "keyboard", icon: "󰌌", title: "Keyboard", subtitle: "Layout and repeat" },
    { page: "network", icon: "󰤨", title: "Wi-Fi & Network", subtitle: "Connections and addresses" },
    { page: "tailscale", icon: "󰖂", title: "Tailscale", subtitle: "Tailnet and peers" },
    { page: "bluetooth", icon: "󰂯", title: "Bluetooth", subtitle: "Power and devices" },
    { page: "sound", icon: "󰕾", title: "Sound", subtitle: "Volume and devices" },
    { page: "displays", icon: "󰍹", title: "Displays", subtitle: "Resolution and scale" },
    { page: "graphics", icon: "󰢮", title: "Graphics & Video", subtitle: "GPU and cameras" },
    { page: "appearance", icon: "󰏘", title: "Appearance", subtitle: "Theme and styling" },
    { page: "power", icon: "󰁹", title: "Power & Battery", subtitle: "Profiles and health" },
    { page: "storage", icon: "󰋊", title: "Storage", subtitle: "Disk usage" },
    { page: "datetime", icon: "󰃰", title: "Date & Time", subtitle: "Timezone and sync" },
    { page: "nightlight", icon: "󰖔", title: "Night Light", subtitle: "Warmth and display tint" },
    { page: "security", icon: "󰒃", title: "Security & Lock", subtitle: "Idle and lock timers" },
    { page: "updates", icon: "󰚰", title: "Updates", subtitle: "System maintenance" },
    { page: "about", icon: "󰋼", title: "About", subtitle: "System information" }
  ]

  Column {
    width: root.availableWidth
    spacing: Style.space(18)

    Text {
      width: parent.width
      text: "Choose a settings category"
      color: Qt.darker(Color.foreground, 1.35)
      font.family: Style.font.family
      font.pixelSize: Style.font.body
    }

    GridLayout {
      width: parent.width
      columns: width >= Style.space(850) ? 4 : (width >= Style.space(620) ? 3 : 2)
      columnSpacing: Style.space(16) * root.tileScale
      rowSpacing: Style.space(16) * root.tileScale

      Repeater {
        model: root.entries

        Components.SettingsTile {
          required property var modelData
          Layout.fillWidth: true
          icon: modelData.icon
          title: modelData.title
          subtitle: modelData.subtitle
          sizeScale: root.tileScale
          onClicked: root.openPage(modelData.page)
        }
      }
    }
  }
}
