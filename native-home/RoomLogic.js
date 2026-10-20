.pragma library

.import "Config.js" as Config

function characterIndex(now, offset) {
    return ((Math.floor(now / 600000) + offset) % 4 + 4) % 4;
}

function localHour(now) {
    var d = new Date(now);
    return d.getHours() + d.getMinutes() / 60;
}

function kind(code) {
    if (code === 0) return "clear";
    if (code >= 1 && code <= 3) return "cloudy";
    if (code === 45 || code === 48) return "fog";
    if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
    if (code >= 95 && code <= 99) return "storm";
    return "unknown";
}

function parseWeather(data, now) {
    var c = data && data.current;
    if (!c || typeof c.weather_code !== "number" || kind(c.weather_code) === "unknown" ||
            typeof c.time !== "number" || Math.abs(now - c.time * 1000) > 10800000 ||
            typeof c.temperature_2m !== "number" || !isFinite(c.temperature_2m) ||
            c.temperature_2m < -30 || c.temperature_2m > 60 ||
            typeof c.wind_speed_10m !== "number" || !isFinite(c.wind_speed_10m) ||
            c.wind_speed_10m < 0 || c.wind_speed_10m > 300)
        throw new Error("Incomplete or stale weather response");
    var daily = data.daily || {};
    return {valid:true, fetchedAt:now, observedAt:c.time * 1000,
        temperature:c.temperature_2m, code:c.weather_code,
        wind:c.wind_speed_10m, cloud:typeof c.cloud_cover === "number" ? c.cloud_cover : 50,
        sunrise:daily.sunrise && daily.sunrise[0] ? daily.sunrise[0] * 1000 : 0,
        sunset:daily.sunset && daily.sunset[0] ? daily.sunset[0] * 1000 : 0};
}

function usable(info, now) {
    return !!info && info.valid === true && now >= info.fetchedAt &&
            now - info.fetchedAt <= 7200000 && Math.abs(now - info.observedAt) <= 10800000;
}

function environment(info, now) {
    var fresh = usable(info, now);
    var hour = localHour(now);
    var rise = fresh && info.sunrise ? localHour(info.sunrise) : 6;
    var set = fresh && info.sunset ? localHour(info.sunset) : 18;
    var phase = hour < rise - 0.5 || hour >= set + 0.5 ? "night" :
                hour < rise + 1 ? "morning" : hour >= set - 1 ? "dusk" : "day";
    return {phase:phase, hour:hour, kind:fresh ? kind(info.code) : "unknown",
        wind:fresh ? info.wind : 0, cloud:fresh ? info.cloud : 0};
}

function weatherLabel(info, now) {
    if (!usable(info, now)) return Config.weather.enabled ? Config.weather.label + " · weather unavailable" : "";
    var names = {clear:"clear", cloudy:"cloudy", fog:"fog", rain:"rain", snow:"snow", storm:"thunderstorm"};
    var age = Math.floor((now - info.fetchedAt) / 60000);
    return Config.weather.label + " · " + Math.round(info.temperature) + "° · " + names[kind(info.code)] +
            (age > 60 ? " · saved " + age + "m ago" : "");
}
