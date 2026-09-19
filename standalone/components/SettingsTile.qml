import QtQuick
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property string icon: ""
  property string title: ""
  property string subtitle: ""
  property real sizeScale: 1
  signal clicked()

  implicitWidth: Style.space(185) * sizeScale
  implicitHeight: Style.space(128) * sizeScale
  radius: Math.max(Style.cornerRadius, Style.space(12) * sizeScale)
  color: mouse.containsMouse
    ? Style.hoverFillFor(Color.foreground, Color.accent)
    : Style.normalFillFor(Color.foreground, Color.accent)
  borderSpec: Border.controlSpec(mouse.containsMouse ? "hover-cursor" : "normal", Color.foreground, Color.accent)

  Column {
    anchors.centerIn: parent
    width: parent.width - Style.space(24) * root.sizeScale
    spacing: Style.space(6) * root.sizeScale

    Text {
      anchors.horizontalCenter: parent.horizontalCenter
      text: root.icon
      textFormat: Text.PlainText
      color: mouse.containsMouse ? Style.hoverStateColor(Color.foreground, Color.accent) : Color.foreground
      font.family: Style.font.family
      font.pixelSize: Math.round(Style.font.display * root.sizeScale)
    }

    Text {
      width: parent.width
      horizontalAlignment: Text.AlignHCenter
      text: root.title
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Math.round(Style.font.body * Math.max(0.85, root.sizeScale))
      font.bold: true
      elide: Text.ElideRight
    }

    Text {
      width: parent.width
      horizontalAlignment: Text.AlignHCenter
      text: root.subtitle
      visible: subtitle !== ""
      color: Qt.darker(Color.foreground, 1.45)
      font.family: Style.font.family
      font.pixelSize: Math.round(Style.font.caption * Math.max(0.85, root.sizeScale))
      elide: Text.ElideRight
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.clicked()
  }
}
