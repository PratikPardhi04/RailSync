import json
import time
import urllib.request
from datetime import datetime

_CACHE: dict = {"data": None, "at": 0.0}
_CACHE_TTL = 600.0

SECTION_POINTS = {
    "shivajinagar": (18.5314, 73.8446),
}


def _point_for(section: str or None):
    if not section:
        return (18.5314, 73.8446)
    key = section.lower()
    for name, point in SECTION_POINTS.items():
        if name in key:
            return point
    return (18.5314, 73.8446)


def _fallback(section: str) -> dict:
    day = datetime.utcnow().day
    seed = (day * 31 + (len(section or "") * 7)) % 100
    precip = 20 + seed  # deterministic pseudo-weather
    temp = 24 + (seed % 8)
    return {
        "source": "fallback",
        "temperature_c": temp,
        "precipitation_probability": min(100, precip),
        "wind_kmh": 8 + (seed % 12),
        "condition": "Rain likely" if precip > 60 else ("Overcast" if precip > 40 else "Partly cloudy"),
        "retrieved_at": datetime.utcnow().isoformat(),
    }


def get_weather(section: str = "Shivajinagar - Khadki") -> dict:
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["at"]) < _CACHE_TTL:
        return _CACHE["data"]

    data = _try_open_meteo(section)

    if not data:
        data = _fallback(section)

    _CACHE["data"] = data
    _CACHE["at"] = now
    return data


def _try_open_meteo(section: str) -> dict:
    lat, lon = _point_for(section)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=precipitation_probability_max,temperature_2m_max,wind_speed_10m_max"
        "&timezone=Asia%2FKolkata&forecast_days=2"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "raillink-ai/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        daily = (payload.get("daily") or {})
        probs = daily.get("precipitation_probability_max") or []
        temps = daily.get("temperature_2m_max") or []
        winds = daily.get("wind_speed_10m_max") or []
        precip = int(probs[1]) if len(probs) > 1 else (int(probs[0]) if probs else 0)
        temp = float(temps[1]) if len(temps) > 1 else (float(temps[0]) if temps else 26.0)
        wind = float(winds[1]) if len(winds) > 1 else (float(winds[0]) if winds else 10.0)
        return {
            "source": "open-meteo",
            "temperature_c": round(temp, 1),
            "precipitation_probability": precip,
            "wind_kmh": round(wind, 1),
            "condition": "Rain likely" if precip > 60 else ("Overcast" if precip > 40 else "Partly cloudy"),
            "retrieved_at": datetime.utcnow().isoformat(),
        }
    except Exception:
        return None


def weather_blocks() -> bool:
    w = get_weather()
    return (w.get("precipitation_probability") or 0) > 60