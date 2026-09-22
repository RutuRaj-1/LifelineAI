import math

import httpx

from ..config import get_settings


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


async def eta_minutes(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Google Distance Matrix (live traffic) when a key is set; otherwise road-distance estimate at ~25 km/h."""
    key = get_settings().google_maps_api_key
    if key:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get("https://maps.googleapis.com/maps/api/distancematrix/json", params={
                    "origins": f"{lat1},{lng1}", "destinations": f"{lat2},{lng2}",
                    "departure_time": "now", "key": key})
            el = r.json()["rows"][0]["elements"][0]
            if el.get("status") == "OK":
                return max(1, round((el.get("duration_in_traffic") or el["duration"])["value"] / 60))
        except Exception:  # noqa: BLE001 - fall through to the estimate
            pass
    return max(1, round(haversine_km(lat1, lng1, lat2, lng2) * 1.35 / 25 * 60))
