import QtQuick 2.12

Item {
    id: sprite
    property string atlasFile: ""
    property int columns: 6
    property int rows: 1
    property int frameIndex: 0
    property int cellWidth: 100
    property int cellHeight: 100
    width: cellWidth
    height: cellHeight
    clip: true

    Image {
        source: "file:///media/developer/native-home/assets/sprites/" + sprite.atlasFile
        x: -(sprite.frameIndex % sprite.columns) * sprite.cellWidth
        y: -Math.floor(sprite.frameIndex / sprite.columns) * sprite.cellHeight
        width: sprite.cellWidth * sprite.columns
        height: sprite.cellHeight * sprite.rows
        smooth: false
        mipmap: false
        cache: true
        asynchronous: false
    }
}
