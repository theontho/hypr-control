import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "../components" as Components

ScrollView {
  id: root

  property var backend: null
  property var data: ({})
  property var devices: []
  property var deviceOptions: []
  property string selectedDevice: ""
  property string profile: "adaptive"
  property real sensitivity: 0
  property real curveScale: 0.4
  property real curveGain: 1
  property real curveStep: 0.3431164009
  property var curvePoints: []
  property var savedCustomPoints: []
  property real savedCustomStep: 0.3431164009
  property string message: ""
  property bool messageError: false

  readonly property var windowsBase: [
    0, 0.258, 0.514, 0.900, 1.286, 1.672, 2.092, 2.678, 3.264, 3.850,
    4.438, 5.024, 5.610, 6.196, 6.782, 7.370, 7.956, 8.542, 9.128, 10.340
  ]
  readonly property var macosPoints: [
    0.000, 0.053, 0.115, 0.189, 0.280, 0.391, 0.525, 0.687, 0.880, 1.108,
    1.375, 1.684, 2.040, 2.446, 2.905, 3.422, 4.000, 4.643, 5.355, 6.139
  ]
  readonly property var profileOptions: [
    { value: "adaptive", label: "Adaptive acceleration" },
    { value: "flat", label: "Flat acceleration" },
    { value: "windows", label: "Windows-style acceleration" },
    { value: "macos", label: "macOS-style acceleration" },
    { value: "custom", label: "Custom acceleration curve" }
  ]

  clip: true
  ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

  function scaledWindowsPoints(scale) {
    var points = []
    for (var i = 0; i < windowsBase.length; i++)
      points.push(Math.round(windowsBase[i] * scale * 1000) / 1000)
    return points
  }

  function scaledMacosPoints(gain) {
    var points = []
    for (var i = 0; i < macosPoints.length; i++)
      points.push(Math.round(macosPoints[i] * gain * 1000) / 1000)
    return points
  }

  function scaledCustomPoints(gain) {
    var points = []
    for (var i = 0; i < savedCustomPoints.length; i++)
      points.push(Math.round(Number(savedCustomPoints[i]) * gain * 1000) / 1000)
    return points
  }

  function flatPoints() {
    var points = []
    var multiplier = Math.max(0.2, 1 + sensitivity * 0.8)
    for (var i = 0; i < 20; i++)
      points.push(Math.round(i * 0.5 * multiplier * 1000) / 1000)
    return points
  }

  function adaptivePoints() {
    var points = []
    var multiplier = Math.max(0.2, 1 + sensitivity * 0.8)
    for (var i = 0; i < 20; i++) {
      var speed = i * 0.5
      var output = speed * (0.55 + 0.055 * speed) * multiplier
      points.push(Math.round(output * 1000) / 1000)
    }
    return points
  }

  function pointsForProfile(value) {
    if (value === "flat") return flatPoints()
    if (value === "adaptive") return adaptivePoints()
    if (value === "windows") return scaledWindowsPoints(curveScale)
    if (value === "macos") return scaledMacosPoints(curveGain)
    if (savedCustomPoints && savedCustomPoints.length >= 2) return scaledCustomPoints(curveGain)
    return curvePoints && curvePoints.length >= 2 ? curvePoints.slice() : scaledWindowsPoints(curveScale)
  }

  function graphMaximum() {
    var maximum = 0
    for (var i = 0; i < curvePoints.length; i++)
      maximum = Math.max(maximum, Number(curvePoints[i]))
    return Math.max(12, Math.ceil(maximum * 1.12))
  }

  function selectProfile(value) {
    profile = value
    curveStep = value === "custom"
      ? savedCustomStep
      : (value === "macos" || value === "flat" || value === "adaptive" ? 0.5 : 0.3431164009)
    curvePoints = pointsForProfile(value)
  }

  function setPointerSpeed(value) {
    if (profile === "adaptive" || profile === "flat") {
      sensitivity = value
    } else if (profile === "windows") {
      curveScale = value
    } else if (profile === "macos" || profile === "custom") {
      curveGain = value
    }
    curvePoints = pointsForProfile(profile)
  }

  function sync() {
    devices = data && data.devices ? data.devices : []
    var options = []
    for (var i = 0; i < devices.length; i++)
      options.push({ value: devices[i].name, label: devices[i].name })
    deviceOptions = options
    var found = false
    for (var j = 0; j < devices.length; j++)
      if (devices[j].name === selectedDevice) found = true
    if (!found) selectedDevice = devices.length ? devices[0].name : ""
    loadSelected()
  }

  function loadSelected() {
    for (var i = 0; i < devices.length; i++) {
      if (devices[i].name !== selectedDevice) continue
      var settings = devices[i].settings || {}
      profile = String(settings.profile || "adaptive")
      sensitivity = Number(settings.sensitivity || 0)
      curveScale = Number(settings.curve_scale || 0.4)
      curveGain = Number(settings.curve_gain === undefined ? 1 : settings.curve_gain)
      curveStep = Number(settings.curve_step || 0.3431164009)
      savedCustomPoints = []
      if (profile === "custom") {
        savedCustomStep = curveStep
        savedCustomPoints = (settings.curve_points || scaledWindowsPoints(curveScale)).slice()
        curvePoints = scaledCustomPoints(curveGain)
      } else {
        curvePoints = pointsForProfile(profile)
      }
      return
    }
  }

  function apply() {
    if (!backend || !selectedDevice) return
    backend.run([
      "input-apply",
      "--device", selectedDevice,
      "--profile", profile,
      "--sensitivity", String(sensitivity),
      "--curve-scale", String(curveScale),
      "--curve-gain", String(curveGain),
      "--curve-step", String(curveStep),
      "--curve-points", JSON.stringify(profile === "custom" ? savedCustomPoints : curvePoints)
    ], "Mouse settings applied.")
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

    Text {
      width: parent.width
      wrapMode: Text.Wrap
      text: "Hardware DPI stays on the mouse. These settings control Hyprland's software pointer response."
      color: Qt.darker(Color.foreground, 1.35)
      font.family: Style.font.family
      font.pixelSize: Style.font.body
    }

    Dropdown {
      width: parent.width
      label: "POINTER DEVICE"
      value: root.selectedDevice
      options: root.deviceOptions
      onChanged: function(value) {
        root.selectedDevice = value
        root.loadSelected()
      }
    }

    Dropdown {
      width: parent.width
      label: "ACCELERATION PROFILE"
      value: root.profile
      options: root.profileOptions
      onChanged: function(value) {
        root.selectProfile(value)
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(6)

      Components.InfoRow {
        label: "Pointer speed"
        value: root.profile === "adaptive" || root.profile === "flat"
          ? root.sensitivity.toFixed(2)
          : (root.profile === "windows" ? root.curveScale : root.curveGain).toFixed(2) + "×"
      }
      PanelSlider {
        width: parent.width
        minimum: root.profile === "adaptive" || root.profile === "flat" ? -1 : 0.1
        maximum: root.profile === "adaptive" || root.profile === "flat"
          ? 1
          : (root.profile === "windows" ? 1 : 1.5)
        step: 0.05
        value: root.profile === "adaptive" || root.profile === "flat"
          ? root.sensitivity
          : (root.profile === "windows" ? root.curveScale : root.curveGain)
        onMoved: function(value) { root.setPointerSpeed(value) }
        onReleased: function(value) { root.setPointerSpeed(value) }
      }
    }

    Column {
      width: parent.width
      spacing: Style.space(10)

      Components.InfoRow {
        label: root.profile === "custom" ? "Custom curve" : "Response curve"
        value: root.curvePoints.length + " points"
      }

      Components.CurveEditor {
        width: parent.width
        points: root.curvePoints
        maxY: root.graphMaximum()
        onEditStarted: {
          if (root.profile !== "custom") {
            root.profile = "custom"
            root.savedCustomPoints = root.curvePoints.slice()
            root.savedCustomStep = root.curveStep
            root.curveGain = 1
          } else if (root.curveGain !== 1) {
            root.savedCustomPoints = root.curvePoints.slice()
            root.curveGain = 1
          }
        }
        onChanged: function(points) {
          root.profile = "custom"
          root.curvePoints = points
          root.savedCustomPoints = points.slice()
        }
      }

      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: root.profile === "flat" || root.profile === "adaptive"
          ? "Flat and adaptive are reference visualizations of libinput behavior. Drag anywhere to sample the graph into a persistent Custom curve."
          : (root.profile === "macos"
            ? "The macOS-style preset is a cubic approximation because Apple does not publish its exact curve. Drag anywhere to switch to Custom curve."
          : "Drag the points to shape acceleration. Editing any preset immediately switches the selector to Custom curve."
          )
        color: Qt.darker(Color.foreground, 1.4)
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
    }

    Row {
      anchors.right: parent.right
      spacing: Style.space(10)

      Button {
        text: "Reset Windows curve"
        bordered: true
        onClicked: {
          root.profile = "windows"
          root.curveScale = 0.4
          root.curvePoints = root.scaledWindowsPoints(0.4)
        }
      }

      Button {
        text: "Use Omarchy default"
        bordered: true
        enabled: root.selectedDevice !== "" && root.backend && !root.backend.busy
        onClicked: root.backend.run(["input-reset", "--device", root.selectedDevice], "Mouse override removed.")
      }

      Button {
        text: root.backend && root.backend.busy ? "Applying..." : "Apply"
        bordered: true
        selected: true
        enabled: root.selectedDevice !== "" && root.backend && !root.backend.busy
        onClicked: root.apply()
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
