import QtQuick
import qs.Commons

Item {
  id: root

  property string label: ""
  property string value: ""

  width: parent ? parent.width : implicitWidth
  implicitHeight: Math.max(labelText.implicitHeight, valueText.implicitHeight) + Style.space(8)

  Text {
    id: labelText
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    text: root.label
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.body
  }

  Text {
    id: valueText
    anchors.left: labelText.right
    anchors.leftMargin: Style.space(18)
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    horizontalAlignment: Text.AlignRight
    text: root.value
    color: Qt.darker(Color.foreground, 1.35)
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    elide: Text.ElideMiddle
  }
}
