.pragma library

// Eight display ticks a second, with deliberately uneven pose holds.
var tracks = [
    [[0,500],[1,250],[2,375],[1,250],[0,625],[3,125],[4,625],[5,1250]],
    [[0,1000],[1,375],[2,625],[3,250],[4,375],[5,375],[0,1000]],
    [[0,625],[1,375],[2,500],[3,625],[4,750],[5,1125]],
    [[0,1250],[1,375],[2,500],[3,375],[2,250],[4,625],[5,625]]
];
var catSequence = [0,0,1,1,2,3,3,4,5,6,7,0,0,0,0,0];
function pose(variant, frame) {
    var remaining = (frame % 32) * 125;
    var track = tracks[Math.max(0,Math.min(3,variant))];
    for (var i=0;i<track.length;i++) {
        if (remaining < track[i][1]) return track[i][0];
        remaining -= track[i][1];
    }
    return 0;
}
function catPose(frame) { return catSequence[Math.floor(frame/4) % catSequence.length]; }
function dayBlend(phase) { return phase === "day" ? 1 : phase === "morning" ? 0.65 : phase === "dusk" ? 0.35 : 0; }
