import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import qs.Ui
import qs.Commons

BarWidget {
  id: root
  moduleName: "lisim.ytmusic"
  property var players: Mpris.players ? Mpris.players.values : []
  property string backend: ""
  readonly property string scriptPath: decodeURIComponent(Qt.resolvedUrl("scripts/ytmusic.py").toString().replace(/^file:\/\//, ""))
  function launchAction(action) { Quickshell.execDetached(["python3", scriptPath, action]) }

  FileView {
    id: preferences
    path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/lisim-ytmusic/settings.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try { root.backend = JSON.parse(text()).backend || "" }
      catch (error) { root.backend = "" }
    }
    onLoadFailed: root.backend = ""
  }

  readonly property var activePlayer: {
    var players = root.players
    for (var i = 0; i < players.length; i++) {
      if (players[i].desktopEntry === "ytmusic-tui") return players[i]
    }
    return null
  }
  readonly property bool canSetVolume: backend === "custom" && !!activePlayer && activePlayer.canControl && activePlayer.volumeSupported && activePlayer.metadata["ytmusic:upNext"] !== undefined
  readonly property real playerVolume: canSetVolume ? activePlayer.volume : 0
  readonly property var upNext: {
    if (backend !== "custom" || !activePlayer) return []
    try {
      var items = JSON.parse(String(activePlayer.metadata["ytmusic:upNext"] || "[]"))
      return Array.isArray(items) ? items.filter(item => typeof item.title === "string" && typeof item.artist === "string").slice(0, 100) : []
    } catch (error) { return [] }
  }

  function setPlayerVolume(value) {
    if (canSetVolume && isFinite(value)) activePlayer.volume = Math.round(Math.max(0, Math.min(1, value)) * 100) / 100
  }

  function adjustPlayerVolume(delta) { setPlayerVolume(playerVolume + delta) }

  function togglePlayback() {
    if (!activePlayer) return
    if (activePlayer.canTogglePlaying) activePlayer.togglePlaying()
    else if (activePlayer.isPlaying && activePlayer.canPause) activePlayer.pause()
    else if (activePlayer.canPlay) activePlayer.play()
  }

  readonly property bool hasMedia: activePlayer !== null && (activePlayer.trackTitle || activePlayer.trackArtist)
  readonly property string playIcon: activePlayer && activePlayer.isPlaying ? "󰏤" : "󰗃"
  readonly property string title: activePlayer ? (activePlayer.trackTitle || "YouTube Music TUI (lisim)") : "YouTube Music TUI (lisim)"
  readonly property string artist: activePlayer ? (activePlayer.trackArtist || "") : ""

  property bool popupOpen: false
  onPopupOpenChanged: if (popupOpen) preferences.reload()


  function close() { popupOpen = false }
  property real maxLabelWidth: 180

  visible: true
  implicitWidth: row.implicitWidth + Style.space(14)
  implicitHeight: barSize

  Row {
    id: row
    anchors.centerIn: parent
    spacing: Style.space(6)

    Text {
      id: glyph
      textFormat: Text.PlainText
      anchors.verticalCenter: parent.verticalCenter
      text: root.playIcon
      color: activePlayer && activePlayer.isPlaying ? root.bar.barForeground : Qt.darker(root.bar.barForeground, 1.5)
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.body
      Behavior on color {
        enabled: !root.bar || root.bar.foregroundAnimationEnabled
        ColorAnimation { duration: 160 }
      }
    }

    Item {
      id: scrollClip
      width: Math.min(root.maxLabelWidth, labelText.implicitWidth)
      height: glyph.height
      clip: true
      anchors.verticalCenter: parent.verticalCenter
      visible: !root.bar.vertical && root.title !== ""

      Text {
        id: labelText
        textFormat: Text.PlainText
        text: root.title + (root.artist ? "  ·  " + root.artist : "")
        color: root.bar.barForeground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.body
        anchors.verticalCenter: parent.verticalCenter

        property bool needsScroll: implicitWidth > scrollClip.width

        NumberAnimation on x {
          id: scrollAnim
          running: labelText.needsScroll && !root.popupOpen && !root.bar.vertical
          loops: Animation.Infinite
          duration: Math.max(6000, labelText.implicitWidth * 25)
          from: scrollClip.width
          to: -labelText.implicitWidth
          easing.type: Easing.Linear
        }
      }
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

    onClicked: function(mouse) {
      if (mouse.button === Qt.LeftButton) {
        root.launchAction("toggle")
      } else if (mouse.button === Qt.MiddleButton && root.activePlayer) {
        root.togglePlayback()
      } else if (mouse.button === Qt.RightButton) {
        root.popupOpen = !root.popupOpen
      }
    }
    onWheel: function(wheel) {
      if (!root.activePlayer) return
      if (wheel.angleDelta.y > 0 && root.activePlayer.canGoPrevious) root.activePlayer.previous()
      else if (wheel.angleDelta.y < 0 && root.activePlayer.canGoNext) root.activePlayer.next()
    }
    onEntered: if (root.bar) root.bar.showTooltip(root, "Left: show/hide player · Middle: play/pause · Right: controls")
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(Style.space(320))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    MouseArea {
      anchors.top: parent.top
      anchors.left: parent.left
      width: parent.width
      height: upNextHeader.y
      enabled: root.canSetVolume
      z: 5
      acceptedButtons: Qt.NoButton
      onWheel: function(wheel) {
        if (wheel.angleDelta.y !== 0) root.adjustPlayerVolume(wheel.angleDelta.y > 0 ? 0.05 : -0.05)
        wheel.accepted = true
      }
    }

    Column {
      id: column
      anchors.fill: parent
      spacing: Style.space(10)

      Button {
        text: root.backend ? "Player setup" : "Set up YouTube Music"
        foreground: root.bar.foreground
        onClicked: root.launchAction("configure")
      }

      Row {
        width: parent.width
        spacing: Style.space(10)

        Column {
          id: nowPlayingDetails
          width: parent.width - (volumeColumn.visible ? volumeColumn.width + parent.spacing : 0)
          spacing: Style.space(10)
          Row {
            spacing: Style.space(10)
            width: parent.width

            BorderSurface {
              width: Style.space(64)
              height: Style.space(64)
              radius: Style.spacing.labelGap
              color: Style.normalFillFor(root.bar.foreground, Color.accent)
              borderSpec: Border.controlSpec("normal", root.bar.foreground, Color.accent)

              Image {
                anchors.fill: parent
                anchors.margins: Style.space(2)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                source: root.activePlayer && root.activePlayer.trackArtUrl ? root.activePlayer.trackArtUrl : ""
                visible: source !== ""
              }

              Text {
                anchors.centerIn: parent
                visible: !root.activePlayer || !root.activePlayer.trackArtUrl
                text: "󰝚"
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.displayLarge
              }
            }

            Column {
              spacing: Style.space(4)
              width: parent.width - Style.space(74)

              Text {
                textFormat: Text.PlainText
                text: root.title || "Nothing playing"
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.subtitle
                font.bold: true
                elide: Text.ElideRight
                width: parent.width
              }

              Text {
                textFormat: Text.PlainText
                text: root.artist
                color: Qt.darker(root.bar.foreground, 1.3)
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
                width: parent.width
                visible: text !== ""
              }

              Text {
                textFormat: Text.PlainText
                text: root.activePlayer && root.activePlayer.trackAlbum ? root.activePlayer.trackAlbum : ""
                color: Qt.darker(root.bar.foreground, 1.6)
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
                width: parent.width
                visible: text !== ""
              }
            }
          }

          Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Style.space(6)

            Button {
              iconText: "󰒮"
              foreground: root.bar.foreground
              horizontalPadding: Style.spacing.controlPaddingX
              verticalPadding: Style.spacing.controlPaddingY
              enabled: root.activePlayer && root.activePlayer.canGoPrevious
              opacity: enabled ? 1.0 : 0.4
              onClicked: if (root.activePlayer) root.activePlayer.previous()
            }

            Button {
              iconText: root.activePlayer && root.activePlayer.isPlaying ? "󰏤" : "󰐊"
              foreground: root.bar.foreground
              horizontalPadding: Style.spacing.panelGap
              verticalPadding: Style.spacing.controlPaddingY
              iconSize: Style.font.iconLarge
              enabled: root.activePlayer && (root.activePlayer.canTogglePlaying || root.activePlayer.canPlay || root.activePlayer.canPause)
              opacity: enabled ? 1.0 : 0.4
              onClicked: root.togglePlayback()
            }

            Button {
              iconText: "󰒭"
              foreground: root.bar.foreground
              horizontalPadding: Style.spacing.controlPaddingX
              verticalPadding: Style.spacing.controlPaddingY
              enabled: root.activePlayer && root.activePlayer.canGoNext
              opacity: enabled ? 1.0 : 0.4
              onClicked: if (root.activePlayer) root.activePlayer.next()
            }
          }
        }

        Column {
          id: volumeColumn
          visible: root.backend === "custom"
          width: Style.space(34)
          spacing: Style.space(4)
          opacity: root.canSetVolume ? 1 : 0.4

          Text {
            width: parent.width
            text: "󰕾"
            horizontalAlignment: Text.AlignHCenter
            color: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.body
          }

          Item {
            objectName: "musicVolumeRail"
            width: parent.width
            height: Math.max(Style.space(70), nowPlayingDetails.implicitHeight - Style.space(38))

            PanelSlider {
              objectName: "musicVolumeSlider"
              bar: root.bar
              anchors.centerIn: parent
              width: parent.height
              height: implicitHeight
              rotation: -90
              minimum: 0
              maximum: 1
              step: 0.05
              value: root.playerVolume
              enabled: root.canSetVolume
              onMoved: function(value) { root.setPlayerVolume(value) }
            }
          }

          Text {
            width: parent.width
            text: Math.round(root.playerVolume * 100) + "%"
            horizontalAlignment: Text.AlignHCenter
            color: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      PanelSeparator { visible: root.backend === "custom"; foreground: root.bar.foreground }

      Text {
        id: upNextHeader
        visible: root.backend === "custom"
        text: "Up Next" + (root.upNext.length ? "  ·  " + root.upNext.length : "")
        color: root.bar.foreground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.subtitle
        font.bold: true
      }

      Text {
        visible: root.backend === "custom" && root.upNext.length === 0
        text: "No songs queued"
        color: root.bar.foreground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.bodySmall
        opacity: 0.6
      }

      ListView {
        id: upcomingList
        visible: root.backend === "custom"
        objectName: "musicUpNextList"
        width: parent.width
        height: Math.min(count, 5) * Style.space(40)
        clip: true
        model: root.upNext
        boundsBehavior: Flickable.StopAtBounds
        onModelChanged: contentY = 0
        Controls.ScrollBar.vertical: Controls.ScrollBar { }
        delegate: Column {
          required property var modelData
          required property int index
          width: upcomingList.width - Style.space(14)
          height: Style.space(40)
          spacing: Style.space(2)
          Text {
            width: parent.width
            textFormat: Text.PlainText
            text: (index + 1) + ". " + modelData.title
            elide: Text.ElideRight
            color: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
          Text {
            width: parent.width
            textFormat: Text.PlainText
            text: modelData.artist
            elide: Text.ElideRight
            color: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
            opacity: 0.65
          }
        }
      }
    }
  }
}
