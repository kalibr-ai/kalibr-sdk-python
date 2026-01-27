"""Basic Kalibr example - Simple weather API"""

from kalibr import Kalibr

app = Kalibr(title="Weather API")


@app.action("get_weather", "Get current weather for a location")
def get_weather(location: str, units: str = "celsius") -> dict:
    """
    Get current weather for a location.
    
    Args:
        location: City name or coordinates
        units: Temperature units (celsius or fahrenheit)
    
    Returns:
        Weather information including temperature and conditions
    """
    # Mock weather data for demo
    temperature = 22 if units == "celsius" else 72
    
    return {
        "location": location,
        "temperature": temperature,
        "units": units,
        "condition": "Partly Cloudy",
        "humidity": 65,
        "wind_speed": 15
    }


@app.action("get_forecast", "Get weather forecast for next 7 days")
def get_forecast(location: str, days: int = 7) -> dict:
    """
    Get weather forecast.
    
    Args:
        location: City name
        days: Number of days (1-7)
    
    Returns:
        Forecast data
    """
    forecast = []
    for day in range(min(days, 7)):
        forecast.append({
            "day": day + 1,
            "high": 25 + day,
            "low": 15 + day,
            "condition": "Sunny" if day % 2 == 0 else "Cloudy"
        })
    
    return {
        "location": location,
        "forecast": forecast
    }


if __name__ == "__main__":
    app.run()
