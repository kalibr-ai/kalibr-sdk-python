"""
Unified test app demonstrating both SDK and tracing capabilities
"""
from kalibr import Kalibr, trace
import time

# Create Kalibr app for multi-model integration
app = Kalibr(title="Unified Test API", version="1.0.30")

# Use @trace decorator for observability
@trace(operation="weather_lookup", provider="custom", model="local-v1")
def fetch_weather_data(city: str):
    """Simulate weather data fetch with tracing"""
    time.sleep(0.1)  # Simulate API call
    return {"city": city, "temp": 72, "condition": "sunny"}

# Register as Kalibr action for multi-model schema generation
@app.action("get_weather", "Get current weather for a city")
def get_weather(city: str, units: str = "fahrenheit") -> dict:
    """
    Get weather data for a specified city.
    
    Args:
        city: Name of the city
        units: Temperature units (fahrenheit or celsius)
    
    Returns:
        Weather data including temperature and conditions
    """
    # Use traced function internally
    data = fetch_weather_data(city)
    
    # Convert units if needed
    if units == "celsius":
        data["temp"] = int((data["temp"] - 32) * 5/9)
    
    return {
        "location": city,
        "temperature": data["temp"],
        "units": units,
        "condition": data["condition"],
        "timestamp": time.time()
    }

@app.action("health_check", "Check API health status")
def health_check() -> dict:
    """Check if the API is healthy"""
    return {
        "status": "healthy",
        "version": "1.0.30",
        "features": ["tracing", "multi-model", "deployment"]
    }

if __name__ == "__main__":
    print("🚀 Starting Unified Kalibr Test API")
    print("✅ Tracing enabled")
    print("✅ Multi-model schemas enabled")
    app.run()
