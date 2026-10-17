import QtQuick
import Quickshell.Io
import qs.Ui
import qs.Commons

Column {
  id: root
  objectName: "musicRatings"
  property string videoId: ""
  property bool active: false
  property bool supported: false
  property color foreground: Color.foreground
  property var commandPrefix: []
  property string ratingStatus: "UNKNOWN"
  property string errorText: ""
  property bool busy: false
  visible: supported && videoId !== ""
  spacing: Style.space(4)

  onVideoIdChanged: {
    ratingStatus = "UNKNOWN"
    errorText = ""
    refresh()
  }
  onActiveChanged: if (active) refresh()
  onSupportedChanged: if (supported) refresh()

  function refresh() {
    if (active) send("get")
  }

  function rate(status) {
    send(ratingStatus === status ? "INDIFFERENT" : status)
  }

  function send(action) {
    if (!supported || videoId === "" || busy || commandPrefix.length === 0) return
    errorText = ""
    busy = true
    request.requestVideo = videoId
    request.command = commandPrefix.concat([action, videoId])
    request.running = true
  }

  Process {
    id: request
    property string requestVideo: ""
    stdout: StdioCollector { id: output; waitForEnd: true }
    stderr: StdioCollector { id: errors; waitForEnd: true }
    onExited: function(exitCode) {
      root.busy = false
      if (requestVideo !== root.videoId) { Qt.callLater(root.refresh); return }
      if (exitCode !== 0) {
        root.errorText = errors.text.trim().slice(0, 180) || "Could not update the song rating"
        return
      }
      try {
        var result = JSON.parse(output.text)
        if (result.video_id !== root.videoId || !["LIKE", "DISLIKE", "INDIFFERENT", "UNKNOWN"].includes(result.status)) throw new Error("Invalid rating response")
        root.ratingStatus = result.status
      } catch (error) { root.errorText = "Could not read the song rating" }
    }
  }

  Row {
    anchors.horizontalCenter: parent.horizontalCenter
    spacing: Style.space(6)
    Repeater {
      model: ["LIKE", "DISLIKE"]
      delegate: Button {
        id: thumb
        required property string modelData
        objectName: modelData === "LIKE" ? "musicLikeButton" : "musicDislikeButton"
        width: Style.space(38)
        height: Style.space(30)
        foreground: root.foreground
        selected: root.ratingStatus === modelData
        enabled: root.supported && root.videoId !== "" && !root.busy
        opacity: enabled ? 1 : 0.45
        focusable: true
        tooltipText: selected ? (modelData === "LIKE" ? "Remove like" : "Remove dislike") : (modelData === "LIKE" ? "Like" : "Dislike")
        Accessible.role: Accessible.Button
        Accessible.name: tooltipText
        onClicked: root.rate(modelData)
        Image {
          objectName: "musicThumbImage"
          anchors.centerIn: parent
          width: Style.space(18)
          height: width
          rotation: thumb.modelData === "DISLIKE" ? 180 : 0
          readonly property color ink: thumb.selected ? Style.selectedStateColor(root.foreground, Color.accent) : root.foreground
          source: "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="' + ink + '" d="M2 10h4v12H2zM8 10l5-8h2v6h5a2 2 0 0 1 2 2l-2 10a2 2 0 0 1-2 2H8z"/></svg>')
          sourceSize.width: width
          sourceSize.height: height
        }
      }
    }
  }

  Text {
    width: parent.width
    horizontalAlignment: Text.AlignHCenter
    wrapMode: Text.Wrap
    textFormat: Text.PlainText
    text: root.busy ? "Updating rating…" : (root.errorText || (root.ratingStatus === "UNKNOWN" ? "Rating unavailable" : ""))
    visible: text !== ""
    color: root.foreground
    font.pixelSize: Style.font.caption
    opacity: 0.75
  }
}
