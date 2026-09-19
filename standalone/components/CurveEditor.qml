import QtQuick
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property var points: []
  property real maxY: 12
  property int selectedIndex: -1
  property bool editable: true
  signal editStarted()
  signal changed(var points)

  implicitHeight: Style.space(260)
  radius: Style.cornerRadius
  color: Style.normalFillFor(Color.foreground, Color.accent)
  borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)

  function plotX(index) {
    if (points.length < 2) return chart.leftPadding
    return chart.leftPadding + index / (points.length - 1) * chart.plotWidth
  }

  function plotY(value) {
    return chart.topPadding + (1 - Math.max(0, Math.min(maxY, value)) / maxY) * chart.plotHeight
  }

  function updatePoint(x, y) {
    if (!points || points.length < 2) return
    var index = Math.round((x - chart.leftPadding) / chart.plotWidth * (points.length - 1))
    index = Math.max(0, Math.min(points.length - 1, index))
    var value = (1 - (y - chart.topPadding) / chart.plotHeight) * maxY
    value = Math.max(0, Math.min(maxY, value))
    var minimum = index > 0 ? Number(points[index - 1]) : 0
    var maximum = index < points.length - 1 ? Number(points[index + 1]) : maxY
    value = Math.max(minimum, Math.min(maximum, value))
    var next = points.slice()
    next[index] = Math.round(value * 1000) / 1000
    selectedIndex = index
    points = next
    changed(next)
  }

  onPointsChanged: chart.requestPaint()
  onMaxYChanged: chart.requestPaint()

  Canvas {
    id: chart
    anchors.fill: parent
    anchors.margins: Style.space(8)
    property real leftPadding: Style.space(34)
    property real rightPadding: Style.space(16)
    property real topPadding: Style.space(14)
    property real bottomPadding: Style.space(30)
    readonly property real plotWidth: Math.max(1, width - leftPadding - rightPadding)
    readonly property real plotHeight: Math.max(1, height - topPadding - bottomPadding)

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
      var ctx = getContext("2d")
      ctx.reset()
      ctx.clearRect(0, 0, width, height)

      ctx.strokeStyle = Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.14)
      ctx.lineWidth = 1
      for (var grid = 0; grid <= 4; grid++) {
        var gy = topPadding + grid / 4 * plotHeight
        ctx.beginPath()
        ctx.moveTo(leftPadding, gy)
        ctx.lineTo(leftPadding + plotWidth, gy)
        ctx.stroke()
      }

      ctx.strokeStyle = Color.foreground
      ctx.lineWidth = Math.max(2, Style.space(2))
      ctx.beginPath()
      for (var i = 0; i < root.points.length; i++) {
        var x = root.plotX(i)
        var y = root.plotY(Number(root.points[i]))
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      for (var point = 0; point < root.points.length; point++) {
        ctx.beginPath()
        ctx.fillStyle = point === root.selectedIndex ? Color.accent : Color.foreground
        ctx.arc(root.plotX(point), root.plotY(Number(root.points[point])), point === root.selectedIndex ? 5 : 3, 0, Math.PI * 2)
        ctx.fill()
      }

      ctx.fillStyle = Qt.darker(Color.foreground, 1.4)
      ctx.font = Style.font.caption + "px " + Style.font.family
      ctx.fillText("input speed →", leftPadding + plotWidth - 72, height - 6)
      ctx.save()
      ctx.translate(10, topPadding + 70)
      ctx.rotate(-Math.PI / 2)
      ctx.fillText("output speed →", 0, 0)
      ctx.restore()
    }
  }

  MouseArea {
    anchors.fill: chart
    enabled: root.editable
    cursorShape: root.editable ? Qt.CrossCursor : Qt.ArrowCursor
    onPressed: function(mouse) {
      root.editStarted()
      root.updatePoint(mouse.x, mouse.y)
    }
    onPositionChanged: function(mouse) {
      if (pressed) root.updatePoint(mouse.x, mouse.y)
    }
  }
}
