import QtQuick 2.12
import "file:///media/developer/native-home/RoomLogic.js" as RoomLogic
import "file:///media/developer/native-home/Config.js" as Config

FocusScope {
    id: root

    property var main
    property alias shelfList: shelfListCompat
    property alias shelfListContainer: shelfListContainerCompat
    property alias topArea: topAreaCompat
    property alias editMenu: editMenuCompat
    property alias recents: recentsCompat
    property alias settingPopup: settingsPanel
    property alias appListArea: appDock
    property alias editMenuLoaderStatus: editMenuLoader.status
    property bool isHalfMode: uiController.isHalfMode
    property bool showFooterButton: false
    property bool needResetModel: false
    property var styleSheet: styleSheetCompat
    property int topAreaYPos: 0
    property int topAreaHeight: 0
    property bool launching: false
    property bool wasShown: false
    property bool ambientMode: false
    property bool roomMotion: true
    property int selectedApp: 0
    readonly property var greetingNames: Config.greetingNames
    property int greetingIndex: 0
    readonly property bool homeActive: root.visible && rootWindow.active && uiController.homeShown && !uiController.isHiddenMode
    property string launchStatus: ""
    property date currentDate: new Date()
    property int sceneOffset: 0
    readonly property int sceneIndex: RoomLogic.characterIndex(currentDate.getTime(), sceneOffset)
    property var weatherInfo: ({valid:false})
    property var weatherRequest: null
    property bool weatherSettled: false
    property double nextWeatherAttempt: 0
    readonly property var roomEnvironment: RoomLogic.environment(weatherInfo, currentDate.getTime())
    property real designScale: Math.min(width / 1280, height / 720)

    signal hideTransitonFinished()
    signal setShelfListModel(var viewState)
    signal resetShelves()
    signal clearShelfModel()
    signal allShelfListUpdate()

    focus: true
    anchors.fill: parent

    onHomeActiveChanged: {
        weatherSettled = false;
        if (homeActive) {
            if (weatherResume) weatherResume.restart();
        } else {
            var request = weatherRequest;
            weatherRequest = null;
            if (weatherResume) weatherResume.stop();
            if (weatherTimeout) weatherTimeout.stop();
            if (request) {
                // Navigation cancellation is not a server failure.
                nextWeatherAttempt = Math.min(nextWeatherAttempt, Date.now() + 1000);
                request.abort();
            }
        }
    }

    QtObject {
        id: styleSheetCompat
        function getRValue(value) { return value * root.designScale; }
    }

    Item {
        id: shelfListContainerCompat
        state: "native"
        property bool transitionShelfListRunning: false
        property bool processingWheel: false
    }

    Item {
        id: shelfListCompat
        property int currentIndex: 0
        property int count: 0
        property var model: ({ count: 0 })
    }

    Item {
        id: topAreaCompat
        property int currentIndex: 0
        property int count: 0
        property var model: ({ count: 0 })
        property bool topShelfLoaded: true
    }

    Item {
        id: recentsCompat
        visible: false
    }

    Item {
        id: editMenuCompat
        property var shelfListEditPage: editShelfCompat
        function createSettingPopup() { root.showOptionMenu(); }
        function closeSettingPopup() { root.closeSettingPopup(); }
        function runVoiceEdit() { root.startEdit("voice"); }
    }

    Item {
        id: editShelfCompat
        function createSettingPopup() { root.showOptionMenu(); }
    }

    Loader {
        id: editMenuLoader
        // UIController gates editMenu on Loader.Ready. This Home has no editor.
        active: false
        sourceComponent: Component { Item {} }
        visible: false
    }

    Rectangle { anchors.fill: parent; color: "#15151e" }

    Item {
        id: designCanvas
        width: 1280; height: 720
        scale: root.designScale
        anchors.centerIn: parent
        visible: !root.ambientMode

        Text {
            x: 48; y: 42; width: 820; height: 46
            text: root.greetingNames.length ? "Welcome home, " + root.greetingNames[root.greetingIndex] + "." : "Welcome home."
            color: "#eee7da"
            font.family: "Droid Serif"; font.pixelSize: 32
            verticalAlignment: Text.AlignVCenter
        }
        Text {
            x: 970; y: 45; width: 262; height: 34
            text: Qt.formatTime(root.currentDate, "hh:mm")
            color: "#eee7da"
            font.family: "LG Smart UI"; font.pixelSize: 28
            horizontalAlignment: Text.AlignRight
        }
        Text {
            x: 970; y: 84; width: 262; height: 22
            text: Qt.formatDate(root.currentDate, "ddd, d MMM")
            color: "#b4afbf"
            font.family: "LG Smart UI"; font.pixelSize: 15
            horizontalAlignment: Text.AlignRight
        }
        Text {
            x: 48; y: 98; width: 840; height: 24
            text: RoomLogic.weatherLabel(root.weatherInfo, root.currentDate.getTime())
            color: "#9997a7"
            font.family: "LG Smart UI"; font.pixelSize: 16
            elide: Text.ElideRight
        }

        FocusScope {
            id: roomButton
            objectName: "roomButton"
            x: 48; y: 136; width: 704; height: 396
            KeyNavigation.down: appRepeater.itemAt(0)
            KeyNavigation.right: appRepeater.itemAt(0)

            Rectangle {
                anchors.fill: parent
                color: "#242135"
                radius: 4
                clip: true
                Loader {
                    id: roomScene
                    anchors.fill: parent
                    anchors.margins: 2
                    source: "file:///media/developer/native-home/RoomScene.qml"
                    onLoaded: {
                        item.sceneVariant = Qt.binding(function() { return root.sceneIndex; });
                        item.environment = Qt.binding(function() { return root.roomEnvironment; });
                        item.motionActive = Qt.binding(function() {
                            return root.homeActive && root.roomMotion && !root.ambientMode;
                        });
                    }
                }
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    radius: parent.radius
                    border.color: roomButton.activeFocus ? "#f5ca83" : "#494052"
                    border.width: roomButton.activeFocus ? 3 : 1
                    z: 1
                }
            }
            Keys.onPressed: {
                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Select) {
                    if (!event.isAutoRepeat) root.openAmbient();
                    event.accepted = true;
                } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Right) {
                    root.focusApps();
                    event.accepted = true;
                }
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onEntered: if (root.homeActive) roomButton.forceActiveFocus()
                onClicked: root.openAmbient()
            }
        }

        Item {
            x: 800; y: 136; width: 424; height: 396
            Column {
                width: parent.width
                anchors.verticalCenter: parent.verticalCenter
                spacing: 19
                Text {
                    width: parent.width
                    text: Config.quoteText
                    color: "#f3d2a1"
                    font.family: "Droid Serif"; font.pixelSize: 28
                    wrapMode: Text.WordWrap
                    lineHeight: 1.2
                }
                Text {
                    text: Config.quoteAuthor
                    color: "#a79bb5"
                    font.family: "LG Smart UI"; font.pixelSize: 16
                }
            }
        }

        Item {
            id: appDock
            objectName: "appListArea"
            x: 48; y: 552; width: 1184; height: 145
            Repeater {
                id: appRepeater
                model: Config.apps
                delegate: FocusScope {
                    id: appTile
                    objectName: "appTile_" + index
                    x: index * 300; width: 282; height: 145
                    focus: index === 0
                    onActiveFocusChanged: if (activeFocus) root.selectedApp = index
                    KeyNavigation.left: index > 0 ? appRepeater.itemAt(index - 1) : appTile
                    KeyNavigation.right: index < appRepeater.count - 1 ? appRepeater.itemAt(index + 1) : appTile
                    KeyNavigation.up: roomButton
                    Rectangle {
                        width: parent.width; height: 110
                        color: modelData.color || "#282336"
                        radius: 4
                        clip: true
                        gradient: modelData.appId === "io.strem.tv" ? stremioGradient : null
                        Gradient {
                            id: stremioGradient
                            GradientStop { position: 0.0; color: "#7b5bf5" }
                            GradientStop { position: 0.25; color: "#7b5bf5" }
                            GradientStop { position: 1.0; color: "#1155d9" }
                        }
                        Image {
                            anchors.centerIn: parent
                            visible: !!modelData.image
                            width: modelData.w || 160; height: modelData.h || 80
                            source: modelData.image ? "file:///media/developer/native-home/assets/" + modelData.image : ""
                            fillMode: modelData.crop ? Image.PreserveAspectCrop : Image.PreserveAspectFit
                            smooth: true
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !modelData.image
                            text: modelData.title
                            color: "#eee7da"
                            font.family: "LG Smart UI"; font.pixelSize: 27
                        }
                        // Keep focus visible over the tile face.
                        Rectangle {
                            anchors.fill: parent
                            color: "transparent"
                            radius: parent.radius
                            border.color: appTile.activeFocus ? "#f5ca83" : "#494052"
                            border.width: appTile.activeFocus ? 3 : 1
                            z: 1
                        }
                    }
                    Text {
                        y: 120; width: parent.width; height: 23
                        text: modelData.title
                        color: "#d1c8d8"
                        font.family: "LG Smart UI"; font.pixelSize: 15
                    }
                    Keys.onPressed: {
                        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Select) {
                            if (!event.isAutoRepeat) root.launchApp(modelData.appId, modelData.title);
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
                            var next = Math.max(0, Math.min(appRepeater.count - 1, index + (event.key === Qt.Key_Left ? -1 : 1)));
                            var neighbor = appRepeater.itemAt(next);
                            if (neighbor) neighbor.forceActiveFocus();
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Up) {
                            roomButton.forceActiveFocus();
                            event.accepted = true;
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: if (root.homeActive) appTile.forceActiveFocus()
                        onClicked: {
                            appTile.forceActiveFocus();
                            root.launchApp(modelData.appId, modelData.title);
                        }
                    }
                }
            }
        }
        Text {
            x: 48; y: 704; width: 1184; height: 14
            text: root.launchStatus
            color: "#f5ca83"
            font.family: "LG Smart UI"; font.pixelSize: 12
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }
    }

    FocusScope {
        id: ambientView
        objectName: "ambientView"
        anchors.fill: parent
        visible: root.ambientMode
        focus: visible
        clip: true
        z: 10
        Rectangle { anchors.fill: parent; color: "#15151e" }
        Loader {
            id: ambientScene
            width: parent.width
            height: parent.height
            anchors.centerIn: parent
            active: root.ambientMode
            source: "file:///media/developer/native-home/RoomScene.qml"
            onLoaded: {
                item.sceneVariant = Qt.binding(function() { return root.sceneIndex; });
                item.environment = Qt.binding(function() { return root.roomEnvironment; });
                if (roomScene.item) item.frame = roomScene.item.frame;
                item.motionActive = Qt.binding(function() { return root.homeActive && root.roomMotion && root.ambientMode; });
            }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.45; color: "#00100e1e" }
                GradientStop { position: 1; color: "#e6100e1e" }
            }
        }
        Text {
            x: parent.width * 0.045; y: parent.height * 0.71
            width: parent.width * 0.68; height: parent.height * 0.20
            text: Config.quoteText
            color: "#f3d2a1"
            font.family: "Droid Serif"; font.pixelSize: 24 * root.designScale
            lineHeight: 1.2
            wrapMode: Text.WordWrap
        }
        Text {
            x: parent.width * 0.045; y: parent.height * 0.92
            width: parent.width * 0.68; height: parent.height * 0.035
            text: Config.quoteAuthor
            color: "#a79bb5"
            font.family: "LG Smart UI"; font.pixelSize: 14 * root.designScale
        }
        Text {
            x: parent.width * 0.73; y: parent.height * 0.065
            width: parent.width * 0.23; height: parent.height * 0.08
            text: Qt.formatTime(root.currentDate, "hh:mm")
            color: "#eee7da"
            font.family: "LG Smart UI"; font.pixelSize: 36 * root.designScale
            horizontalAlignment: Text.AlignRight
        }
        Text {
            x: parent.width * 0.045; y: parent.height * 0.96
            width: parent.width * 0.9; height: parent.height * 0.04
            text: RoomLogic.weatherLabel(root.weatherInfo, root.currentDate.getTime())
            color: "#a6a3b0"
            font.family: "LG Smart UI"; font.pixelSize: 15 * root.designScale
            elide: Text.ElideRight
        }
        Keys.onPressed: {
            if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
                if (!event.isAutoRepeat) root.sceneOffset = (root.sceneOffset + (event.key === Qt.Key_Left ? 3 : 1)) % 4;
            } else if (!event.isAutoRepeat && !root.handleMotionKey(event.key)) root.goToTop();
            event.accepted = true;
        }
        MouseArea { anchors.fill: parent; onClicked: root.goToTop() }
    }

    // Compatibility handle for the stock controller. Settings opens directly.
    Item {
        id: settingsPanel
        visible: false
        property bool popupAnimationRunning: false
    }

    Timer {
        interval: 10000
        repeat: true
        running: root.homeActive && !root.ambientMode && root.greetingNames.length > 1
        onTriggered: root.greetingIndex = (root.greetingIndex + 1) % root.greetingNames.length
    }

    Timer {
        id: weatherResume
        interval: 1500
        onTriggered: {
            root.weatherSettled = true;
            root.refreshWeather();
        }
    }

    Timer {
        id: clockTimer
        interval: Math.max(250, 60000 - root.currentDate.getSeconds() * 1000 - root.currentDate.getMilliseconds())
        repeat: true
        triggeredOnStart: true
        running: root.homeActive
        onTriggered: {
            root.currentDate = new Date();
            root.refreshWeather();
        }
    }

    Timer {
        id: weatherTimeout
        interval: 10000
        onTriggered: {
            var request = root.weatherRequest;
            root.weatherRequest = null;
            if (request) request.abort();
        }
    }

    Timer {
        id: launchTimeout
        interval: 8000
        repeat: false
        onTriggered: root.finishLaunch("The TV did not respond.")
    }

    Connections {
        target: uiController
        onIsRecentModeChanged: {
            if (uiController.isRecentMode) {
                uiController.isRecentMode = false;
                root.goToTop();
            }
        }
    }

    // UIController owns this state; mirror the stock view's lifecycle signals
    // and readiness flags without creating the stock shelves or transitions.
    state: uiController.state

    onStateChanged: {
        if (state === "hidden") {
            if (!root.wasShown) return;
            uiController.isRecentMode = false;
            uiController.introRan = false;
            uiController.mainTransitionFinished = false;
            Qt.callLater(function() {
                if (root.state !== "hidden") return;
                root.wasShown = false;
                root.hideTransitonFinished();
                uiController.hideWindow();
            });
        } else if (state === "main") {
            root.wasShown = true;
            uiController.isFullHome = true;
            uiController.introRan = true;
            uiController.mainTransitionFinished = true;
            uiController.isRecentMode = false;
            if (rootWindow.active)
                Qt.callLater(function() { root.focusApps(); });
        } else if (state === "half" || state === "sub") {
            root.wasShown = true;
            uiController.isFullHome = false;
            uiController.introRan = true;
            uiController.mainTransitionFinished = true;
        } else if (state === "editMenu") {
            // Recover if an external controller path assigns editMenu directly.
            Qt.callLater(function() { uiController.goToState("main"); });
        }
    }

    function initialize() {
        ambientMode = false;
        currentDate = new Date();
        if (uiController.interfaces && uiController.interfaces.initApp && uiController.interfaces.initApp.closeAnimation)
            uiController.interfaces.initApp.closeAnimation();
        uiController.isFullHome = true;
        uiController.mainTransitionFinished = state === "main";
        uiController.mainRibbonReady = true;
        uiController.introRan = state === "main";
        if (homeActive) weatherResume.restart();
        Qt.callLater(function() { root.focusApps(); });
    }

    function focusApps() {
        var first = appRepeater.itemAt(root.selectedApp);
        if (first) first.forceActiveFocus();
    }

    function refreshWeather() {
        var now = Date.now();
        if (!Config.weather.enabled || !Config.weather.url || !homeActive || !weatherSettled || weatherRequest || now < nextWeatherAttempt) return;
        // Back off failures for five minutes; successful results last thirty.
        nextWeatherAttempt = now + 300000;
        var request = new XMLHttpRequest();
        weatherRequest = request;
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE || root.weatherRequest !== request) return;
            root.weatherRequest = null;
            weatherTimeout.stop();
            if (request.status !== 200 || request.responseText.length > 65536) return;
            try {
                root.weatherInfo = RoomLogic.parseWeather(JSON.parse(request.responseText), Date.now());
                root.nextWeatherAttempt = Date.now() + 1800000;
            } catch (error) { /* Last good result expires honestly in RoomLogic. */ }
        };
        try {
            request.open("GET", Config.weather.url);
            weatherTimeout.restart();
            request.send();
        } catch (error) {
            weatherRequest = null;
            weatherTimeout.stop();
        }
    }

    function openAmbient() {
        ambientMode = true;
        Qt.callLater(function() { ambientView.forceActiveFocus(); });
    }

    function handleMotionKey(key, repeated) {
        if (key === Qt.Key_MediaPause) { roomMotion = false; return true; }
        if (key === Qt.Key_MediaPlay) { roomMotion = true; return true; }
        if (key === Qt.Key_MediaTogglePlayPause) {
            if (!repeated) roomMotion = !roomMotion;
            return true;
        }
        return false;
    }

    function goToTop() {
        var wasAmbient = ambientMode;
        if (ambientScene.item && roomScene.item) roomScene.item.frame = ambientScene.item.frame;
        if (settingsPanel.visible) {
            closeSettingPopup();
            return;
        }
        ambientMode = false;
        shelfListContainerCompat.state = "native";
        if (wasAmbient) roomButton.forceActiveFocus();
        else root.focusApps();
    }

    function startEdit(startPoint) {
        if (uiController.state === "editMenu") uiController.goToState("main");
    }

    function showOptionMenu() {
        launchApp("com.palm.app.settings", "Settings");
    }

    function closeSettingPopup() { root.focusApps(); }

    function launchApp(appId, title) {
        if (launching)
            return;
        var application = uiController.interfaces ? uiController.interfaces.application : null;
        if (!application || !application.launchApp) {
            launchStatus = "Could not open " + title + ": the TV launch service is unavailable.";
            return;
        }
        launching = true;
        launchStatus = "Opening " + title + "…";
        launchTimeout.restart();
        try {
            application.launchApp(appId, "", {}, "launcher", function(response) {
                if (response && response.returnValue === true)
                    root.finishLaunch("");
                else
                    root.finishLaunch(response && response.errorText ? response.errorText : "The TV did not confirm the launch.");
            });
        } catch (error) {
            finishLaunch(error && error.message ? error.message : "the TV launch service is unavailable.");
        }
    }

    function finishLaunch(error) {
        launchTimeout.stop();
        launching = false;
        launchStatus = error ? "Could not open the app: " + error : "";
    }

    Keys.onPressed: {
        if (handleMotionKey(event.key, event.isAutoRepeat)) { event.accepted = true; return; }
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_Back || event.key === Qt.Key_Backspace) {
            if (settingsPanel.visible) {
                closeSettingPopup();
                event.accepted = true;
            } else if (ambientMode) {
                goToTop();
                event.accepted = true;
            }
        }
    }
}
