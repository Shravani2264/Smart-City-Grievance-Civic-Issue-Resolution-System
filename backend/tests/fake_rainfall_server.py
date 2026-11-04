"""Offline stand-in for mcp_servers.rainfall_server: same tool name and shape, fixed data, no network."""
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fake-rainfall", log_level="WARNING")
PEAK = float(os.environ.get("FAKE_RAIN_PEAK", "64"))


@mcp.tool()
def get_rainfall_forecast(lat: float = 19.076, lng: float = 72.8777, hours: int = 3) -> dict:
    """Fixed forecast for tests."""
    series = [PEAK / 2, PEAK, PEAK / 4][:hours]
    return {"source": "fake", "lat": lat, "lng": lng, "hours": hours, "peak_mm_hr": max(series), "mean_mm_hr": sum(series) / len(series),
            "hourly": [{"time": f"t{i}", "mm": v} for i, v in enumerate(series)]}


if __name__ == "__main__":
    mcp.run()
