import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Live Scores: favorite teams, live.
// Bar: logos + score during a live match, a ball otherwise.
// Panel: FlashScore-style stats, upcoming matches, results,
// news and a Teams tab to pick favorites.
// Data: ESPN public API (no key), refreshed every refreshIntervalSec.
Panel {
  id: root
  moduleName: "meviusisback.live-scores"
  ipcTarget: "meviusisback.live-scores"
  manageIpc: false

  implicitWidth: Math.max(liveItem.implicitWidth, idleButton.implicitWidth)
  implicitHeight: Math.max(liveItem.implicitHeight, idleButton.implicitHeight)

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color accent: Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // ---------------------------------------------------------------- settings
  readonly property string favSetting: String(setting("favoriteTeams", "inter,milan,juventus,napoli,roma,lazio"))
  readonly property var favIds: favSetting.split(",").map(function (s) { return s.trim().toLowerCase() }).filter(function (s) { return s !== "" })
  readonly property string leaguesSetting: String(setting("leagues", "soccer/ita.1,soccer/eng.1,soccer/esp.1,soccer/ger.1,soccer/fra.1,soccer/ned.1,soccer/por.1,soccer/uefa.champions,soccer/uefa.europa,soccer/uefa.euro,soccer/uefa.nations,basketball/nba,basketball/euroleague,basketball/lba,hockey/nhl"))
  readonly property int refreshIntervalSec: Math.min(600, Math.max(30, Number(setting("refreshIntervalSec", 90)) || 90))

  // --------------------------------------------------------------------- data
  property var liveMatches: []
  property var upcoming: []
  property var results: []
  property var news: []
  property var teams: []
  property bool loading: true
  property string errorText: ""

  property string tab: "live"
  property var selected: null
  property var summaryStats: []
  property var summaryTimeline: []
  property var summaryLineups: []
  property var summaryCommentary: []
  property bool summaryLoading: false
  property bool scoreArmed: false

  // Team search (Teams tab): type to filter in real time.
  property string searchText: ""

  readonly property string scoreKey: root.firstLive
    ? (root.firstLive.id + "|" + root.firstLive.home.score + ":" + root.firstLive.away.score) : ""

  onScoreKeyChanged: {
    // The first round only arms: no animation at startup.
    if (!root.scoreArmed) return
    if (root.scoreKey !== "") goalPulse.restart()
  }

  // Team selection (draft until you press Save).
  property var pendingFavs: []
  property bool favsDirty: false

  readonly property bool hasLive: (root.liveMatches || []).length > 0
  readonly property var firstLive: root.hasLive ? root.liveMatches[0] : null
  readonly property int extraLive: root.hasLive ? root.liveMatches.length - 1 : 0

  readonly property var leagueNames: ({
    "soccer/ita.1": "Serie A", "soccer/eng.1": "Premier League",
    "soccer/esp.1": "LaLiga", "soccer/ger.1": "Bundesliga",
    "soccer/fra.1": "Ligue 1", "soccer/uefa.champions": "Champions",
    "soccer/uefa.europa": "Europa League", "soccer/uefa.euro": "Euros",
    "soccer/uefa.nations": "Nations League", "soccer/ned.1": "Eredivisie",
    "soccer/por.1": "Liga Portugal", "basketball/nba": "NBA",
    "basketball/euroleague": "EuroLeague", "basketball/lba": "LBA Serie A",
    "hockey/nhl": "NHL"
  })

  function leagueLabel(league) { return root.leagueNames[league] || league }

  readonly property string heroCaption: {
    if (root.loading) return "LOADING…"
    var n = (root.liveMatches || []).length
    if (n > 0) return n === 1 ? "1 LIVE" : n + " LIVE"
    if (root.errorText !== "") return "OFFLINE"
    return "NO LIVE"
  }

  readonly property string tooltipText: {
    if (!root.hasLive) return "Live Scores — none of your teams are playing"
    var parts = []
    for (var i = 0; i < root.liveMatches.length; i++) {
      var m = root.liveMatches[i]
      parts.push(m.home.abbr + " " + m.home.score + "–" + m.away.score + " " + m.away.abbr + " (" + liveLabel(m) + ")")
    }
    return "Live Scores — " + parts.join(" · ")
  }

  function liveLabel(m) {
    if (!m) return ""
    if (m.clock !== "") return m.clock
    return m.detail !== "" ? m.detail : "live"
  }

  function scoreText(m) {
    if (!m) return "—"
    return m.home.abbr + " " + m.home.score + "–" + m.away.score + " " + m.away.abbr
  }

  function fmtDate(iso) {
    var d = new Date(iso)
    if (!isFinite(d.getTime())) return ""
    return Qt.formatDateTime(d, "ddd d MMM hh:mm")
  }

  function isFav(id) { return root.pendingFavs.indexOf(id) !== -1 }

  function foldQ(s) {
    var text = String(s || "")
    try { text = text.normalize("NFD").replace(/[̀-ͯ]/g, "") } catch (e) {}
    return text.toLowerCase()
  }

  function teamLabel(id) {
    var found = (root.teams || []).filter(function (t) { return t && String(t.id) === String(id) })[0]
    return found ? found.label : String(id)
  }

  readonly property var searchHits: {
    var q = root.foldQ(root.searchText.trim())
    if (q.length < 2) return []
    var hits = []
    var list = root.teams || []
    for (var i = 0; i < list.length && hits.length < 8; i++) {
      var t = list[i]
      if (!t) continue
      var hay = root.foldQ((t.label || "") + " " + (t.tokens || []).join(" "))
      if (hay.indexOf(q) !== -1) hits.push(t)
    }
    return hits
  }

  function toggleFav(id) {
    var list = root.pendingFavs.slice()
    var i = list.indexOf(id)
    if (i === -1) list.push(id)
    else list.splice(i, 1)
    root.pendingFavs = list
    root.favsDirty = true
  }

  function syncPending() {
    root.pendingFavs = root.favIds.slice()
    root.searchText = ""
    root.favsDirty = false
  }

  function persistSetting(key, value) {
    root.close()
    var entry = { id: root.moduleName }
    for (var k in root.settings) if (k !== "id") entry[k] = root.settings[k]
    entry[key] = value
    root.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }

  function saveFavs() {
    root.persistSetting("favoriteTeams", root.pendingFavs.join(","))
    root.favsDirty = false
    Qt.callLater(root.refresh)
  }

  function scriptPath() {
    return decodeURIComponent(Qt.resolvedUrl("fetch_scores.py").toString()).replace(/^file:\/\//, "")
  }

  function refresh() {
    if (boardProc.running) return
    // Rebuild the command every run: the process line
    // freezes startup arguments and would ignore new favorites.
    boardProc.command = ["python3", root.scriptPath(), "--favorites", root.favSetting, "--leagues", root.leaguesSetting]
    boardProc.running = true
  }

  function runTeams() {
    if (teamsProc.running) return
    teamsProc.command = ["python3", root.scriptPath(), "--teams", "--leagues", root.leaguesSetting]
    teamsProc.running = true
  }

  // If leagues or favorites change in settings, reload right away:
  // the team catalog follows leagues, the bar follows favorites.
  onLeaguesSettingChanged: {
    root.runTeams()
    root.refresh()
  }
  onFavSettingChanged: root.refresh()

  function refreshSummary() {
    if (!root.selected || summaryProc.running) return
    root.summaryLoading = true
    summaryProc.command = ["python3", root.scriptPath(), "--summary", root.selected.league, root.selected.id]
    summaryProc.running = true
  }

  function pickMatch(m) {
    root.selected = m
    root.refreshSummary()
  }

  function onBoardData(data) {
    root.liveMatches = data.live || []
    root.upcoming = data.upcoming || []
    root.results = data.results || []
    root.news = data.news || []
    root.errorText = data.error || ""
    root.loading = false
    // Keep the live match selected (or the first one) and refresh stats.
    var sel = null
    if (root.selected) {
      var want = root.selected.id
      sel = (root.liveMatches || []).filter(function (m) { return m.id === want })[0] || null
    }
    if (!sel) sel = root.firstLive
    root.selected = sel
    if (!root.scoreArmed && !root.loading) root.scoreArmed = true
    if (sel && root.tab === "live") root.refreshSummary()
  }

  // ------------------------------------------------------------ processes
  Process {
    id: boardProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.onBoardData(JSON.parse(text || "{}"))
        } catch (e) {
          root.loading = false
          root.errorText = "parse-error"
        }
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if ((text || "").trim() !== "") console.warn("live-scores:", text.trim().slice(0, 300))
    }
    onExited: function (code) {
      root.loading = false
      if (code !== 0 && (root.liveMatches || []).length === 0 && root.errorText === "") {
        root.errorText = "fetch-failed-" + code
        console.warn("live-scores: fetch exited with code", code)
      }
    }
  }

  Process {
    id: summaryProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.summaryLoading = false
        try {
          var data = JSON.parse(text || "{}")
          root.summaryStats = data.stats || []
          root.summaryTimeline = data.timeline || []
          root.summaryLineups = data.lineups || []
          root.summaryCommentary = data.commentary || []
        } catch (e) { console.warn("live-scores: summary parse error") }
      }
    }
    stderr: StdioCollector {
    }
    onExited: root.summaryLoading = false
  }

  Process {
    id: teamsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.teams = (JSON.parse(text || "{}")).teams || []
          console.log("live-scores: catalogo", root.teams.length, "squadre per", root.leaguesSetting)
        } catch (e) { root.teams = [] }
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if ((text || "").trim() !== "") console.warn("live-scores teams:", text.trim().slice(0, 500))
    }
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  IpcHandler {
    enabled: !root.manageIpc && root.ipcTarget !== ""
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refresh(); return "ok" }
    function setTab(t: string): string {
      var tabs = ["live", "upcoming", "news", "teams"]
      if (tabs.indexOf(t) !== -1) {
        if (t === "teams") root.syncPending()
        root.tab = t
        if (t === "live" && root.selected) root.refreshSummary()
        return "ok"
      }
      return "bad-tab"
    }
    function search(q: string): string {
      root.searchText = q
      return String(root.searchHits.length)
    }
  }

  // ------------------------------------------------------------ bar: live
  Item {
    id: liveItem
    visible: root.hasLive
    implicitWidth: liveRow.implicitWidth + Style.space(10)
    implicitHeight: Math.max(Style.font.body * 1.5, Style.space(22))

    function triggerPress(button) {
      if (root.bar) root.bar.hideTooltip(liveItem)
      if (button === Qt.RightButton) root.refresh()
      else root.toggle()
    }

    Row {
      id: liveRow
      anchors.centerIn: parent
      spacing: Style.space(5)

      Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(7)
        height: width
        radius: width / 2
        color: root.urgent
      }

      Image {
        anchors.verticalCenter: parent.verticalCenter
        width: Style.font.body * 1.2
        height: width
        visible: root.firstLive && root.firstLive.home.logo !== ""
        source: visible ? root.firstLive.home.logo : ""
        fillMode: Image.PreserveAspectFit
        mipmap: true
        cache: true
      }

      Text {
        id: barScore
        anchors.verticalCenter: parent.verticalCenter
        transformOrigin: Item.Center
        text: root.firstLive ? root.scoreText(root.firstLive) : ""
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
      }

      Image {
        anchors.verticalCenter: parent.verticalCenter
        width: Style.font.body * 1.2
        height: width
        visible: root.firstLive && root.firstLive.away.logo !== ""
        source: visible ? root.firstLive.away.logo : ""
        fillMode: Image.PreserveAspectFit
        mipmap: true
        cache: true
      }

      Text {
        anchors.verticalCenter: parent.verticalCenter
        text: root.firstLive ? root.liveLabel(root.firstLive) : ""
        textFormat: Text.PlainText
        color: root.urgent
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
      }

      Text {
        anchors.verticalCenter: parent.verticalCenter
        visible: root.extraLive > 0
        text: "+" + root.extraLive
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      hoverEnabled: true
      onClicked: function (mouse) { liveItem.triggerPress(mouse.button) }
      onContainsMouseChanged: {
        if (!root.bar) return
        if (containsMouse) root.bar.showTooltip(liveItem, root.tooltipText)
        else root.bar.hideTooltip(liveItem)
      }
      Component.onCompleted: if (root.bar && root.bar.registerClickTarget) root.bar.registerClickTarget(liveItem)
      Component.onDestruction: if (root.bar && root.bar.unregisterClickTarget) root.bar.unregisterClickTarget(liveItem)
    }

    // Goal animation: the score pulses when the result changes.
    SequentialAnimation {
      id: goalPulse
      ScaleAnimator { target: barScore; from: 1; to: 1.35; duration: 180; easing.type: Easing.OutCubic }
      ScaleAnimator { target: barScore; from: 1.35; to: 1; duration: 280; easing.type: Easing.InOutQuad }
    }
  }

  // ------------------------------------------------------- bar: no live
  BarIconButton {
    id: idleButton
    visible: !root.hasLive
    anchors.fill: parent
    bar: root.bar
    text: ""
    tooltipText: root.errorText !== "" ? "Live Scores — offline, retrying on its own" : "Live Scores — no live match"
    active: false
    onPressed: function (buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else {
        root.tab = "live"
        root.toggle()
      }
    }
  }

  // ------------------------------------------------------- panel anchor
  Item {
    id: panelAnchor
    anchors.right: parent.right
    width: 1
    height: parent.height
  }

  // -------------------------------------------------------------- panel
  KeyboardPanel {
    id: panel
    anchorItem: panelAnchor
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: Style.space(380)
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(600))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onActivateRequested: root.refresh()
      onCloseRequested: root.close()
      onTextKey: function (t) {
        if (t === "r" || t === "R") root.refresh()
        else if (t === "1") root.tab = "live"
        else if (t === "2") root.tab = "upcoming"
        else if (t === "3") root.tab = "news"
        else if (t === "4") { root.tab = "teams"; root.syncPending() }
      }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          width: panelFlick.width
          spacing: Style.space(12)

          // Hero.
          Item {
            width: parent.width
            implicitHeight: Math.max(heroIcon.implicitHeight, heroLabels.implicitHeight)

            Text {
              id: heroIcon
              text: root.hasLive ? "\uf1e3" : "\uf1e3"
              textFormat: Text.PlainText
              color: root.hasLive ? root.urgent : root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.display
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
            }

            Column {
              id: heroLabels
              anchors.left: heroIcon.right
              anchors.leftMargin: Style.space(14)
              anchors.right: parent.right
              spacing: Style.space(2)

              Text {
                width: parent.width
                text: "Live Scores"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.title
                font.bold: true
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                text: root.heroCaption
                textFormat: Text.PlainText
                color: Qt.darker(root.foreground, 1.4)
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 1.2
                elide: Text.ElideRight
              }
            }
          }

          // Tab.
          Row {
            width: parent.width
            spacing: Style.space(6)

            Button {
              text: "Live"
              selected: root.tab === "live"
              leftAlign: false
              onClicked: root.tab = "live"
            }
            Button {
              text: "Upcoming"
              selected: root.tab === "upcoming"
              onClicked: root.tab = "upcoming"
            }
            Button {
              text: "News"
              selected: root.tab === "news"
              onClicked: root.tab = "news"
            }
            Button {
              text: "Teams"
              selected: root.tab === "teams"
              onClicked: { root.tab = "teams"; root.syncPending() }
            }
          }

          // ------------------------------------------------- Live tab
          Column {
            width: parent.width
            spacing: Style.space(10)
            visible: root.tab === "live"

            Text {
              width: parent.width
              visible: root.loading
              text: "Loading scores…"
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Text {
              width: parent.width
              visible: !root.loading && !root.hasLive && root.errorText === ""
              text: "No live match right now. Your teams’ upcoming games are below — open Teams to change them."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Text {
              width: parent.width
              visible: !root.loading && root.errorText !== ""
              text: "Can’t reach the data (offline?). Retrying on its own — press R to retry now."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.urgent
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Repeater {
              model: root.hasLive ? root.liveMatches : []

              Column {
                id: matchBlock
                required property var modelData
                required property int index
                width: parent.width
                spacing: Style.space(8)

                // Clickable row: select the match and load its stats.
                Rectangle {
                  width: parent.width
                  implicitHeight: headRow.implicitHeight + Style.space(14)
                  radius: Style.space(8)
                  color: root.selected && root.selected.id === matchBlock.modelData.id
                    ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.14) : "transparent"
                  border.color: root.selected && root.selected.id === matchBlock.modelData.id
                    ? root.accent : "transparent"

                  Row {
                    id: headRow
                    anchors.centerIn: parent
                    spacing: Style.space(8)

                    Image {
                      anchors.verticalCenter: parent.verticalCenter
                      width: Style.font.title * 1.4
                      height: width
                      visible: matchBlock.modelData.home.logo !== ""
                      source: visible ? matchBlock.modelData.home.logo : ""
                      fillMode: Image.PreserveAspectFit
                      mipmap: true
                      cache: true
                    }
                    Text {
                      anchors.verticalCenter: parent.verticalCenter
                      text: root.scoreText(matchBlock.modelData)
                      textFormat: Text.PlainText
                      color: root.foreground
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.title
                      font.bold: true
                    }
                    Image {
                      anchors.verticalCenter: parent.verticalCenter
                      width: Style.font.title * 1.4
                      height: width
                      visible: matchBlock.modelData.away.logo !== ""
                      source: visible ? matchBlock.modelData.away.logo : ""
                      fillMode: Image.PreserveAspectFit
                      mipmap: true
                      cache: true
                    }
                    Text {
                      anchors.verticalCenter: parent.verticalCenter
                      text: root.liveLabel(matchBlock.modelData)
                      textFormat: Text.PlainText
                      color: root.urgent
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: true
                    }
                  }

                  MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.pickMatch(matchBlock.modelData)
                  }
                }

                Text {
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  text: matchBlock.modelData.leagueName + " · " + matchBlock.modelData.home.name + " – " + matchBlock.modelData.away.name
                  textFormat: Text.PlainText
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }
              }
            }

            // FlashScore-style stats for the selected match.
            Column {
              width: parent.width
              spacing: Style.space(6)
              visible: root.hasLive && root.selected !== null

              Text {
                width: parent.width
                text: "Stats"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                font.bold: true
              }

              Text {
                width: parent.width
                visible: root.summaryLoading
                text: "Loading stats…"
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }

              Repeater {
                model: root.summaryLoading ? [] : root.summaryStats

                StatRow {
                  required property var modelData
                  label: modelData.label
                  homeValue: String(modelData.home)
                  awayValue: String(modelData.away)
                  homeAbbr: root.selected ? root.selected.home.abbr : ""
                  awayAbbr: root.selected ? root.selected.away.abbr : ""
                }
              }

              // Goal and card timeline.
              Repeater {
                model: root.summaryLoading ? [] : root.summaryTimeline

                Text {
                  required property var modelData
                  width: parent.width
                  text: (modelData.kind === "goal" || modelData.kind === "penalty" ? "⚽ " : modelData.kind === "card" ? "🟨 " : "· ") + modelData.text + (modelData.team !== "" ? " (" + modelData.team + ")" : "")
                  textFormat: Text.PlainText
                  wrapMode: Text.WordWrap
                  color: modelData.kind === "goal" || modelData.kind === "penalty" ? root.foreground : root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }
              }

              Row {
                width: parent.width
                spacing: Style.space(8)

                Button {
                  text: "Open on FlashScore"
                  onClicked: Qt.openUrlExternally("https://www.flashscore.it/")
                }
                Button {
                  visible: root.selected && (root.selected.espnLink || "").indexOf("https://") === 0
                  text: "Gamecast ESPN"
                  onClicked: Qt.openUrlExternally(root.selected ? root.selected.espnLink : "")
                }
              }

              // Lineups (when available).
              Column {
                width: parent.width
                spacing: Style.space(6)
                visible: !root.summaryLoading && (root.summaryLineups || []).length > 0

                Text {
                  width: parent.width
                  text: "Lineups"
                  textFormat: Text.PlainText
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }

                Row {
                  width: parent.width
                  spacing: Style.space(10)

                  Repeater {
                    model: root.summaryLineups

                    Column {
                      required property var modelData
                      width: (parent.width - Style.space(10)) / 2
                      spacing: Style.space(2)

                      Text {
                        width: parent.width
                        text: modelData.team
                        textFormat: Text.PlainText
                        color: root.accent
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                        font.bold: true
                      }

                      Repeater {
                        model: modelData.players

                        Text {
                          required property var modelData
                          width: parent.width
                          text: (modelData.num !== "" ? modelData.num + " " : "") + modelData.name + (modelData.pos !== "" ? " (" + modelData.pos + ")" : "")
                          textFormat: Text.PlainText
                          color: root.dim
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                          elide: Text.ElideRight
                        }
                      }
                    }
                  }
                }
              }

              // Text commentary (play-by-play, ESPN English).
              Column {
                width: parent.width
                spacing: Style.space(4)
                visible: !root.summaryLoading && (root.summaryCommentary || []).length > 0

                Text {
                  width: parent.width
                  text: "Commentary"
                  textFormat: Text.PlainText
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }

                Repeater {
                  model: root.summaryCommentary

                  Text {
                    required property var modelData
                    width: parent.width
                    text: (modelData.clock !== "" ? modelData.clock + " — " : "") + modelData.text
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                  }
                }
              }
            }

            // When there is no live match: upcoming preview.
            Column {
              width: parent.width
              spacing: Style.space(4)
              visible: !root.hasLive && (root.upcoming || []).length > 0

              Text {
                width: parent.width
                text: "Upcoming matches"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                font.bold: true
              }

              Repeater {
                model: root.upcoming.slice(0, 4)

                Text {
                  required property var modelData
                  width: parent.width
                  text: modelData.home.abbr + " – " + modelData.away.abbr + "  ·  " + root.fmtDate(modelData.date)
                  textFormat: Text.PlainText
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  elide: Text.ElideRight
                }
              }
            }
          }

          // --------------------------------------------- Upcoming tab
          Column {
            width: parent.width
            spacing: Style.space(6)
            visible: root.tab === "upcoming"

            Text {
              width: parent.width
              text: "Upcoming matches"
              textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              font.bold: true
            }

            Text {
              width: parent.width
              visible: (root.upcoming || []).length === 0
              text: root.loading ? "Loading…" : "No upcoming matches for your teams."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Repeater {
              model: root.upcoming

              Column {
                required property var modelData
                width: parent.width
                spacing: Style.space(2)

                Text {
                  width: parent.width
                  text: modelData.home.abbr + " – " + modelData.away.abbr
                  textFormat: Text.PlainText
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  elide: Text.ElideRight
                }
                Text {
                  width: parent.width
                  text: root.fmtDate(modelData.date) + "  ·  " + root.leagueLabel(modelData.league)
                  textFormat: Text.PlainText
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
            }

            // Past results (favorites only).
            Text {
              width: parent.width
              visible: (root.results || []).length > 0
              text: "Results"
              textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              font.bold: true
            }

            Repeater {
              model: root.results

              Text {
                required property var modelData
                width: parent.width
                text: modelData.home.abbr + " " + modelData.home.score + "–" + modelData.away.score + " " + modelData.away.abbr + "  ·  " + (modelData.detail !== "" ? modelData.detail + "  ·  " : "") + root.leagueLabel(modelData.league)
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
              }
            }
          }

          // ------------------------------------------------ News tab
          Column {
            width: parent.width
            spacing: Style.space(8)
            visible: root.tab === "news"

            Text {
              width: parent.width
              visible: (root.news || []).length === 0
              text: root.loading ? "Loading…" : "No news right now."
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Repeater {
              model: root.news

              Column {
                required property var modelData
                width: parent.width
                spacing: Style.space(2)

                Text {
                  width: parent.width
                  text: modelData.headline
                  textFormat: Text.PlainText
                  wrapMode: Text.WordWrap
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
                Text {
                  width: parent.width
                  visible: (modelData.description || "") !== ""
                  text: modelData.description
                  textFormat: Text.PlainText
                  wrapMode: Text.WordWrap
                  maximumLineCount: 2
                  elide: Text.ElideRight
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
                Text {
                  width: parent.width
                  visible: (modelData.link || "") !== ""
                  text: (modelData.league || "") !== "" ? modelData.league + " · open ↗" : "open ↗"
                  textFormat: Text.PlainText
                  color: root.accent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption

                  MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if ((modelData.link || "").indexOf("https://") === 0) Qt.openUrlExternally(modelData.link)
                  }
                }
              }
            }
          }

          // ------------------------------------------------ Teams tab
          Column {
            width: parent.width
            spacing: Style.space(8)
            visible: root.tab === "teams"

            Text {
              width: parent.width
              text: "Your teams (" + root.pendingFavs.length + ")"
              textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              font.bold: true
            }

            Flow {
              width: parent.width
              spacing: Style.space(6)

              Repeater {
                model: root.pendingFavs

                Button {
                  required property var modelData
                  text: "✕ " + root.teamLabel(modelData)
                  selected: true
                  onClicked: root.toggleFav(modelData)
                }
              }
            }

            Text {
              width: parent.width
              visible: root.pendingFavs.length === 0
              text: "No teams yet: search for one below."
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Text {
              width: parent.width
              text: "Add more: type to search Serie A, Premier, Liga, Bundesliga, Ligue 1, Eredivisie, cups, national teams, NBA, EuroLeague, LBA Serie A and NHL."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              font.bold: true
            }

            TextField {
              id: teamSearch
              width: parent.width
              placeholderText: "Search teams… (e.g. real, lakers, inter)"
              maximumLength: 120
              text: root.searchText
              onTextChanged: root.searchText = text
              onAccepted: {
                if (root.searchHits.length > 0) {
                  root.toggleFav(String(root.searchHits[0].id))
                  root.searchText = ""
                }
              }
            }

            Text {
              width: parent.width
              visible: root.searchText.trim().length >= 2 && root.searchHits.length === 0
              text: "No team found: try another name or enable more leagues in settings."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Repeater {
              model: root.searchHits

              Row {
                required property var modelData
                width: parent.width
                spacing: Style.space(8)

                Image {
                  anchors.verticalCenter: parent.verticalCenter
                  width: Style.font.title * 1.2
                  height: width
                  visible: (modelData.logo || "") !== ""
                  source: visible ? modelData.logo : ""
                  fillMode: Image.PreserveAspectFit
                  mipmap: true
                  cache: true
                }

                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  visible: (modelData.logo || "") === ""
                  text: ""
                  textFormat: Text.PlainText
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }

                Column {
                  width: parent.width - Style.space(110)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(1)

                  Text {
                    width: parent.width
                    text: modelData.label
                    textFormat: Text.PlainText
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                    elide: Text.ElideRight
                  }
                  Text {
                    width: parent.width
                    text: root.leagueLabel(modelData.league)
                    textFormat: Text.PlainText
                    color: root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                  }
                }

                Button {
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.isFav(String(modelData.id)) ? "✓" : "＋"
                  selected: root.isFav(String(modelData.id))
                  onClicked: root.toggleFav(String(modelData.id))
                }
              }
            }

            Button {
              text: root.favsDirty ? "Save favorites" : "Saved ✓"
              selected: root.favsDirty
              onClicked: if (root.favsDirty) root.saveFavs()
            }
          }
        }
      }
    }
  }

  // FlashScore-style stat row: home value, dual bar, away value.
  component StatRow: Item {
    id: statRow
    property string label: ""
    property string homeValue: ""
    property string awayValue: ""
    property string homeAbbr: ""
    property string awayAbbr: ""
    width: parent ? parent.width : 0
    implicitHeight: statCol.implicitHeight + Style.space(4)

    function num(v) {
      var n = parseFloat(String(v).replace(",", "."))
      return isFinite(n) ? n : NaN
    }

    readonly property real h: statRow.num(statRow.homeValue)
    readonly property real a: statRow.num(statRow.awayValue)
    readonly property real ratio: {
      if (!isFinite(statRow.h) && !isFinite(statRow.a)) return 0.5
      var hh = isFinite(statRow.h) ? statRow.h : 0
      var aa = isFinite(statRow.a) ? statRow.a : 0
      if (hh + aa <= 0) return 0.5
      return hh / (hh + aa)
    }

    Column {
      id: statCol
      width: parent.width
      spacing: Style.space(3)

      Text {
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        text: statRow.label
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Row {
        width: parent.width
        spacing: Style.space(6)

        Text {
          width: Style.space(44)
          horizontalAlignment: Text.AlignRight
          anchors.verticalCenter: parent.verticalCenter
          text: statRow.homeValue
          textFormat: Text.PlainText
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Item {
          width: parent.width - Style.space(44) * 2 - Style.space(12)
          height: Style.space(6)
          anchors.verticalCenter: parent.verticalCenter

          Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
          }
          Rectangle {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            height: parent.height
            width: Math.round(parent.width * statRow.ratio)
            radius: height / 2
            color: root.accent
          }
        }

        Text {
          width: Style.space(44)
          anchors.verticalCenter: parent.verticalCenter
          text: statRow.awayValue
          textFormat: Text.PlainText
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }
      }
    }
  }

  Component.onCompleted: {
    root.syncPending()
    root.runTeams()
  }
}
