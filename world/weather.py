import json

import atomic
import os
import time
import urllib.request
import urllib.parse
import logger

# Open-Meteo, no key. Hourly temp, humidity, precipitation, weather code for
# Tokyo. Cached to disk and refreshed on an interval so a restart or a sim run
# does not hammer the API. In sim mode the requested date may be outside the
# forecast window; the fallback is a month-typical Tokyo day so the director
# still gets a plausible sky.

WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "snow showers", 95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"
}

# (temp_c high, temp_c low, humidity, sky) per month, Tokyo climatology
FALLBACK = {
    1: (10, 2, 50, "clear"), 2: (11, 2, 52, "clear"), 3: (14, 5, 57, "partly cloudy"),
    4: (19, 10, 62, "partly cloudy"), 5: (23, 15, 68, "partly cloudy"), 6: (26, 19, 76, "rain"),
    7: (30, 23, 77, "overcast"), 8: (31, 24, 74, "mostly clear"), 9: (27, 21, 74, "partly cloudy"),
    10: (22, 15, 68, "partly cloudy"), 11: (17, 9, 62, "clear"), 12: (12, 4, 55, "clear")
}


class Weather:
    def __init__(self, config, clock):
        self.config = config
        self.clock = clock
        self.enabled = config.world.weather_enabled
        self.lat = config.world.weather_latitude
        self.lon = config.world.weather_longitude
        self.cache_path = config.world.weather_cache_path
        self.refresh = config.world.weather_refresh_minutes * 60
        self._data = None
        self._fetched_wall = 0
        # `enabled` stopped the fetch and not the reading: the cache file is
        # shared by every character on this machine, so a character with no
        # body still opened it and reported the first character's city back as
        # her own weather. Off means nothing to read as well as nothing to
        # fetch.
        if self.enabled:
            self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    blob = json.load(f)
                self._data = blob.get("data")
                self._fetched_wall = blob.get("fetched_wall", 0)
            except Exception:
                self._data = None

    def _save_cache(self):
        atomic.write_json(self.cache_path,
                          {"fetched_wall": self._fetched_wall, "data": self._data})

    def _fetch(self):
        params = {
            "latitude": self.lat, "longitude": self.lon,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code,apparent_temperature",
            "daily": "sunrise,sunset,temperature_2m_max,temperature_2m_min",
            "timezone": self.config.world.character_timezone,
            "past_days": 1, "forecast_days": 7
        }
        url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                self._data = json.loads(r.read().decode("utf-8"))
            self._fetched_wall = time.time()
            self._save_cache()
            logger.log("[weather] refreshed from open-meteo")
        except Exception as e:
            logger.log(f"[weather] fetch failed: {e}")

    def _ensure(self):
        if not self.enabled:
            return
        if self._data is None or (time.time() - self._fetched_wall) > self.refresh:
            self._fetch()

    def current(self, dt=None):
        """Returns dict: temp, feels, humidity, precip_mm, sky, sunrise, sunset, source.

        Empty when there is no weather for this character. `describe` already
        refused honestly and this did not: with the feed off it fell through to
        the climatology table below and returned a plausible invented Tokyo,
        which reached a character with no body and no world through two readers
        that test the object rather than the flag. Her prompt read "you are
        inside, 24.9C" and her director's "about 24.1C (outside 21.1C, feels
        21.1C, humidity 74%, partly cloudy)" -- a month lookup and a cosine,
        presented to her as the sky outside her window. Every caller either
        guards on the section's own flag or uses `.get`, so nothing needs a
        number here that nobody measured."""
        if not self.enabled:
            return {}
        dt = dt or self.clock.now()
        self._ensure()
        key = dt.strftime("%Y-%m-%dT%H:00")
        if self._data:
            hourly = self._data.get("hourly", {})
            times = hourly.get("time", [])
            if key in times:
                i = times.index(key)
                out = {
                    "temp": hourly["temperature_2m"][i],
                    "feels": hourly.get("apparent_temperature", hourly["temperature_2m"])[i],
                    "humidity": hourly["relative_humidity_2m"][i],
                    "precip_mm": hourly["precipitation"][i],
                    "sky": WMO.get(hourly["weather_code"][i], "unknown"),
                    "source": "open-meteo"
                }
                daily = self._data.get("daily", {})
                dkey = dt.strftime("%Y-%m-%d")
                if dkey in daily.get("time", []):
                    j = daily["time"].index(dkey)
                    out["sunrise"] = daily["sunrise"][j][-5:]
                    out["sunset"] = daily["sunset"][j][-5:]
                    out["high"] = daily["temperature_2m_max"][j]
                    out["low"] = daily["temperature_2m_min"][j]
                return out
        hi, lo, hum, sky = FALLBACK[dt.month]
        # crude diurnal curve: low at 05:00, high at 15:00
        h = dt.hour + dt.minute / 60
        import math
        frac = (math.cos((h - 15) / 24 * 2 * math.pi) + 1) / 2
        temp = round(lo + (hi - lo) * frac, 1)
        return {"temp": temp, "feels": temp, "humidity": hum, "precip_mm": 0.0, "sky": sky,
                "sunrise": "05:00", "sunset": "18:30", "high": hi, "low": lo, "source": "climatology"}

    def describe(self, dt=None):
        # weather is a live reading of the present. `current()` keeps its shape
        # for the handful of callers that index into it, but the sentence
        # people read should not invent a sky for a character nobody is
        # fetching one for. Two ways it comes to be off and the reason is not
        # the same: no body to be out in it, or a body in no present to read.
        if not self.enabled:
            return ("off: she has no body to be out in it"
                    if not self.config.character.existence.embodied else
                    "off: nobody is fetching one, and there is no present for her to read it from")
        w = self.current(dt)
        s = f"{w['sky']}, {w['temp']}C (feels {w['feels']}C), humidity {w['humidity']}%"
        if w.get("precip_mm", 0) > 0:
            s += f", {w['precip_mm']}mm rain this hour"
        if w.get("sunrise"):
            s += f". sunrise {w['sunrise']} sunset {w['sunset']}, high {w.get('high')} low {w.get('low')}"
        return s
