import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

ShellRoot {
  id: root

  property string currentPage: "home"

  readonly property var pageTitles: ({
    home: "System Settings",
    mouse: "Mouse",
    keyboard: "Keyboard",
    network: "Wi-Fi & Network",
    tailscale: "Tailscale",
    bluetooth: "Bluetooth",
    sound: "Sound",
    displays: "Displays",
    graphics: "Graphics & Video",
    appearance: "Appearance",
    backgrounds: "Desktop Background",
    controllers: "Game Controllers",
    printers: "Printers & Scanners",
    power: "Power & Battery",
    storage: "Storage",
    datetime: "Date & Time",
    nightlight: "Night Light",
    security: "Security & Lock",
    screensaver: "Screensaver",
    startup: "Startup",
    locale: "Language & Region",
    updates: "Updates",
    about: "About"
  })

  function pageSource(page) {
    if (page === "home") return "pages/HomePage.qml"
    if (page === "mouse") return "pages/MousePage.qml"
    if (page === "keyboard") return "pages/KeyboardPage.qml"
    if (page === "backgrounds" || page === "controllers" || page === "printers"
        || page === "screensaver" || page === "startup" || page === "locale")
      return "pages/SystemToolsPage.qml"
    if (page === "network" || page === "tailscale" || page === "bluetooth"
        || page === "sound" || page === "displays")
      return "pages/BuiltinPanelPage.qml"
    return "pages/GeneralPage.qml"
  }

  function pageData(page) {
    if (!backend.data) return ({})
    if (page === "mouse") return backend.data.input || ({})
    if (page === "sound") return backend.data.audio || ({})
    if (page === "datetime") return backend.data.dateTime || ({})
    if (page === "nightlight") return backend.data.nightLight || ({})
    if (page === "about") return backend.data.system || ({})
    return backend.data[page] || ({})
  }

  function pageAcceptsData(page) {
    return page !== "home"
      && page !== "network"
      && page !== "tailscale"
      && page !== "bluetooth"
      && page !== "sound"
      && page !== "displays"
  }

  SettingsBackend {
    id: backend
  }

  IpcHandler {
    target: "hypr-control"

    function page(name: string): void {
      if (root.pageTitles[name] !== undefined) root.currentPage = name
    }

    function refresh(): void {
      backend.refresh()
    }
  }

  FloatingWindow {
    id: window
    visible: true
    title: "System Settings"
    color: Color.background
    implicitWidth: 980
    implicitHeight: 760
    minimumSize: Qt.size(700, 560)
    onVisibleChanged: if (!visible) Qt.quit()

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: Style.space(22)
      spacing: Style.space(14)

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(12)

        Button {
          visible: root.currentPage !== "home"
          iconText: "󰁍"
          tooltipText: "Back to all settings"
          bordered: true
          foreground: Color.foreground
          onClicked: root.currentPage = "home"
        }

        Text {
          Layout.fillWidth: true
          text: root.pageTitles[root.currentPage] || "System Settings"
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.title
          font.bold: true
          elide: Text.ElideRight
        }

        Text {
          visible: backend.busy
          text: "Refreshing…"
          color: Qt.darker(Color.foreground, 1.4)
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        Button {
          iconText: "󰑐"
          tooltipText: "Refresh settings"
          bordered: true
          foreground: Color.foreground
          enabled: !backend.busy
          onClicked: backend.refresh()
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
        foreground: Color.foreground
      }

      Text {
        Layout.fillWidth: true
        visible: backend.error !== ""
        wrapMode: Text.Wrap
        text: backend.error
        color: Color.urgent
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }

      Loader {
        id: pageLoader
        Layout.fillWidth: true
        Layout.fillHeight: true
        source: root.pageSource(root.currentPage)

        onLoaded: {
          if (!item) return
          if ("backend" in item) item.backend = backend
          if ("mode" in item) item.mode = root.currentPage
          if (root.pageAcceptsData(root.currentPage)) item.data = root.pageData(root.currentPage)
        }
      }

      Binding {
        target: pageLoader.item
        property: "data"
        value: root.pageData(root.currentPage)
        when: pageLoader.item && root.pageAcceptsData(root.currentPage)
      }

      Binding {
        target: pageLoader.item
        property: "width"
        value: pageLoader.width
        when: pageLoader.item
      }

      Binding {
        target: pageLoader.item
        property: "height"
        value: pageLoader.height
        when: pageLoader.item
      }

      Binding {
        target: pageLoader.item
        property: "mode"
        value: root.currentPage
        when: pageLoader.item && "mode" in pageLoader.item
      }


      Connections {
        target: pageLoader.item
        ignoreUnknownSignals: true
        function onOpenPage(page) { root.currentPage = page }
      }
    }
  }

  Component.onCompleted: backend.refresh()
}
