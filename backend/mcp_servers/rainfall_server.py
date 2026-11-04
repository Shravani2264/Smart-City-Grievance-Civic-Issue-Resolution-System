"""MCP server: rainfall forecast for the Predictive Intelligence agent.

Speaks the Model Context Protocol over stdio, so CivicPulse (or any MCP client, e.g. Claude Desktop)
can call it. Data comes from Open-Meteo's free forecast API (no key needed).

Run standalone:   cd backend && python -m mcp_servers.rainfall_server
"""
import json
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("civic-rainfall", log_level="WARNING")
API = "https://api.open-meteo.com/v1/forecast"


@mcp.tool()
def get_rainfall_forecast(lat: float = 19.076, lng: float = 72.8777, hours: int = 3) -> dict:
    """Hourly precipitation forecast (mm/h) for the next `hours` hours at a point. Defaults to central Mumbai.

    Returns peak and mean mm/h plus the hourly series, so a caller can plan for the worst hour.
    """
    hours = max(1, min(48, int(hours)))
    q = urllib.parse.urlencode({"latitude": round(lat, 4), "longitude": round(lng, 4), "hourly": "precipitation",
                                "forecast_hours": hours, "timezone": "Asia/Kolkata"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "CivicPulse-rainfall-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.load(r)
    series = [float(v or 0.0) for v in data["hourly"]["precipitation"]][:hours]
    times = data["hourly"]["time"][:hours]
    return {"source": "open-meteo.com", "lat": lat, "lng": lng, "hours": hours, "units": "mm/h",
            "peak_mm_hr": round(max(series, default=0.0), 2),
            "mean_mm_hr": round(sum(series) / len(series), 2) if series else 0.0,
            "hourly": [{"time": t, "mm": v} for t, v in zip(times, series)]}


if __name__ == "__main__":
    mcp.run()  # stdio transport
