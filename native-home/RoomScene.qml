import QtQuick 2.12
import "SpriteLogic.js" as SpriteLogic
import "Config.js" as Config

Item {
    id: room
    property bool motionActive: false
    property int frame: 0
    property int sceneVariant: 0
    property var environment: ({phase:"night", hour:20, kind:"unknown", wind:0, cloud:0})
    readonly property real sceneScale: Math.min(width / 480, height / 270)
    implicitWidth: 480
    implicitHeight: 270
    clip: true

    onSceneVariantChanged: frame = 0

    Item {
        id: pixels
        width: 480
        height: 270
        anchors.centerIn: parent
        scale: room.sceneScale

        Image {
            anchors.fill: parent
            source: "file:///media/developer/native-home/assets/sprites/night.png"
            smooth: false; mipmap: false
        }
        Image {
            anchors.fill: parent
            source: "file:///media/developer/native-home/assets/sprites/day.png"
            opacity: SpriteLogic.dayBlend(room.environment.phase)
            smooth: false; mipmap: false
        }
        Rectangle {
            anchors.fill: parent
            color: "#d5a075"
            opacity: room.environment.phase === "morning" ? 0.04 : room.environment.phase === "dusk" ? 0.07 : 0
        }
        SpriteAtlas {
            id: weatherSprites
            objectName: "roomWeatherSprites"
            x: 0; y: 0
            atlasFile: "weather.png"
            columns: 8; rows: 2; cellWidth: 208; cellHeight: 105
            visible: room.environment.kind === "rain" || room.environment.kind === "storm" || room.environment.kind === "snow"
            frameIndex: (room.environment.kind === "snow" ? 8 : 0) + Math.floor(room.frame / (room.environment.wind > 20 ? 1 : 2)) % 8
        }
        Repeater {
            model: [30,120]
            Rectangle {
                x: modelData; y: 19; width: 81; height: 79
                color: room.environment.kind === "fog" ? "#b9cbd0" : "#dbe5da"
                opacity: room.environment.kind === "fog" ? 0.16 : room.environment.kind === "storm" && room.frame % 320 === 1 ? 0.10 : 0
            }
        }
        Rectangle {
            x: 249; y: 214; width: 49; height: 9
            radius: 24; color: "#0a0f17"; opacity: 0.34
        }
        Rectangle {
            x: 360; y: 222; width: 31; height: 7
            radius: 16; color: "#0a0f17"; opacity: 0.28
        }
        SpriteAtlas {
            x: 293; y: 108
            atlasFile: "props.png"
            columns: 6; rows: 2; cellWidth: 40; cellHeight: 40
            frameIndex: Math.floor(room.frame * 3 / 4) % 6
        }
        SpriteAtlas {
            x: 135; y: 86
            atlasFile: "props.png"
            columns: 6; rows: 2; cellWidth: 40; cellHeight: 40
            frameIndex: 6 + Math.floor(room.frame * 3 / 8) % 6
        }
        SpriteAtlas {
            id: character
            visible: Config.showCharacters
            objectName: "roomCharacterSprite"
            x: 224; y: 130
            atlasFile: "characters.png"
            columns: 6; rows: 4; cellWidth: 100; cellHeight: 100
            frameIndex: room.sceneVariant * 6 + SpriteLogic.pose(room.sceneVariant, room.frame)
        }
        SpriteAtlas {
            id: cat
            objectName: "roomCyborgCat"
            x: 350; y: 176
            atlasFile: "cyborg-cat.png"
            columns: 4; rows: 2; cellWidth: 64; cellHeight: 56
            frameIndex: SpriteLogic.catPose(room.frame)
        }
    }

    Timer {
        interval: 125
        repeat: true
        running: room.motionActive && room.visible
        onTriggered: room.frame = (room.frame + 1) % 240000
    }
}
