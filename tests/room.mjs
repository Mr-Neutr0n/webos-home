import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const base = new URL('../native-home/', import.meta.url);
function qmlJS(name, context) {
  vm.runInContext(fs.readFileSync(new URL(name, base), 'utf8').replace(/^\.(?:pragma|import).*$/gm, ''), context);
}
const config = vm.createContext({});
qmlJS('Config.js', config);
assert.equal(config.greetingNames.length, 0);
assert.equal(config.weather.enabled, false);
assert.equal(config.weather.url, '');
assert.equal(config.apps.length, 4);
assert.match(config.quoteText, /men will begin to think like computers/);
assert.equal(config.quoteAuthor, 'Sydney J. Harris');
const logic = vm.createContext({Date, Math, isFinite, Error, Config: config});
qmlJS('RoomLogic.js', logic);
assert.equal(logic.weatherLabel({valid: false}, Date.now()), '');
const now = Date.now();
const current = {time: now / 1000, weather_code: 61, temperature_2m: 22, wind_speed_10m: 13};
const weather = logic.parseWeather({current}, now);
assert.equal(logic.environment(weather, now).kind, 'rain');
assert.equal(logic.environment(weather, now + 7200001).kind, 'unknown');
for (const invalid of [{...current, time: now / 1000 - 12000}, {...current, temperature_2m: Infinity}, {...current, weather_code: 999}]) {
  assert.throws(() => logic.parseWeather({current: invalid}, now));
}
for (let i = 0; i < 8; i++) assert.equal(logic.characterIndex(i * 600000, 0), i % 4);
const sprites = vm.createContext({Math});
qmlJS('SpriteLogic.js', sprites);
for (let who = 0; who < 4; who++) {
  assert.equal(sprites.tracks[who].reduce((sum, entry) => sum + entry[1], 0), 4000);
  for (let frame = 0; frame < 256; frame++) {
    assert.ok(sprites.pose(who, frame) >= 0 && sprites.pose(who, frame) < 6);
    assert.equal(sprites.pose(who, frame), sprites.pose(who, frame + 32));
  }
}
for (let frame = 0; frame < 128; frame++) assert.ok(sprites.catPose(frame) >= 0 && sprites.catPose(frame) < 8);
const sizes = {'characters.png':[600,400], 'cyborg-cat.png':[256,112], 'props.png':[240,80], 'weather.png':[1664,210], 'day.png':[480,270], 'night.png':[480,270]};
for (const [name, [w,h]] of Object.entries(sizes)) {
  const bytes = fs.readFileSync(new URL('assets/sprites/' + name, base));
  assert.equal(bytes.readUInt32BE(16), w, name);
  assert.equal(bytes.readUInt32BE(20), h, name);
}
console.log('Room checks passed: private defaults, weather expiry, sprite bounds and atlas dimensions.');
