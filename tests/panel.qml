import QtQuick
import Quickshell
import Quickshell.Io
import QtTest

ShellRoot {
  Item {
    id: test
    TestCase { id: checks; name: "MusicPanel"; when: false }
    FileView {
      id: setupWriter
      path: Quickshell.env("XDG_CONFIG_HOME") + "/omarchy-ytmusic/settings.json"
      printErrors: false
    }
    Timer {
      interval: 100
      running: Quickshell.env("TEST_FIRST_RUN") === "1"
      onTriggered: setupWriter.setText('{"backend":"custom","browser":"later"}')
    }
    QtObject {
      id: music
      property string desktopEntry: "ytmusic-tui"
      property bool canControl: true
      property bool volumeSupported: true
      property real volume: 0.4
      property var metadata: ({"ytmusic:upNext": JSON.stringify([{title: "Next Song", artist: "Artist"}])})
      property string trackTitle: "Current Song"
      property string trackArtist: "Artist"
      property string trackAlbum: "Album"
      property string trackArtUrl: ""
      property bool isPlaying: false
      property bool canGoNext: true
      property bool canGoPrevious: true
      property bool canTogglePlaying: true
      property bool canPlay: true
      property bool canPause: true
      property int toggles: 0
      function togglePlaying() { toggles++; isPlaying = !isPlaying }
      function pause() { isPlaying = false }
      function play() { isPlaying = true }
    }
    QtObject { id: browser; property string desktopEntry: "chrome"; property real volume: 0.8 }
    QtObject { id: media; property var players: [browser, music] }
    QtObject { id: shellApi; function firstPartyServiceFor(id) { return media } }
    QtObject {
      id: bar
      property QtObject shell: shellApi
      property bool vertical: false
      property int barSize: 26
      property color foreground: "#eeeeee"
      property color barForeground: foreground
      property color background: "#111111"
      property string fontFamily: "monospace"
      property bool foregroundAnimationEnabled: false
      property string position: "top"
      property var activePopout: null
      function releasePopout(owner) {}
    }
    Loader {
      id: widget
      source: "MusicWidget.qml"
      onLoaded: { item.bar = bar; item.players = [browser, music] }
    }
    Timer {
      interval: 300
      running: true
      onTriggered: {
        function check(ok, message) { if (!ok) throw new Error(message) }
        check(widget.status === Loader.Ready, "widget failed to load")
        check(widget.item.backend === "custom", "first-run settings did not load")
        check(widget.item.activePlayer === music, "wrong player selected")
        widget.item.togglePlayback()
        check(music.toggles === 1 && music.isPlaying, "playback toggle did not reach music")
        music.canTogglePlaying = false
        widget.item.togglePlayback()
        check(!music.isPlaying, "pause fallback failed")
        widget.item.togglePlayback()
        check(music.isPlaying, "play fallback failed")
        music.canTogglePlaying = true
        var slider = checks.findChild(widget.item, "musicVolumeSlider")
        var rail = checks.findChild(widget.item, "musicVolumeRail")
        check(slider !== null && rail !== null, "volume slider missing")
        check(slider.rotation === -90 && rail.height > rail.width, "volume slider is not vertical")
        check(slider.mapToItem(rail, 0, slider.height / 2).y > slider.mapToItem(rail, slider.width, slider.height / 2).y, "volume direction is reversed")
        slider.moved(0.55)
        check(music.volume === 0.55, "slider movement did not set player volume")
        music.volume = 0.4
        widget.item.adjustPlayerVolume(0.05)
        check(Math.abs(music.volume - 0.45) < 0.001, "volume step")
        widget.item.setPlayerVolume(2)
        check(music.volume === 1, "upper limit")
        widget.item.setPlayerVolume(-1)
        check(music.volume === 0, "lower limit")
        check(browser.volume === 0.8, "browser volume changed")
        check(widget.item.upNext.length === 1 && widget.item.upNext[0].title === "Next Song", "queue missing")
        var queueList = checks.findChild(widget.item, "musicUpNextList")
        music.metadata = ({"ytmusic:upNext": JSON.stringify(Array.from({length: 7}, (_, i) => ({title: "Song " + i, artist: "Artist"})))})
        queueList.forceLayout()
        check(queueList.count === 7 && queueList.contentHeight > queueList.height && queueList.clip, "queue does not scroll independently")
        music.metadata = ({"ytmusic:upNext": "invalid-json"})
        check(widget.item.upNext.length === 0, "invalid queue not rejected")
        widget.item.backend = "original"
        check(!widget.item.canSetVolume && widget.item.upNext.length === 0, "original mode exposes unsupported controls")
        console.log("PASS: actual widget selects music, changes only its volume, clamps limits and reads queue")
        Qt.quit()
      }
    }
  }
}
