from kalibr import Kalibr
import httpx
import time

app = Kalibr(title="Travel Planner")

@app.action("plan_trip", "Plan a trip to a city")
def plan_trip(city: str, days: int = 3):
    # Simulate planning time
    time.sleep(0.1)
    
    # Call Weather Service (Agent 1)
    try:
        response = httpx.post(
            "http://localhost:8100/proxy/get_weather",
            json={"city": city},
            headers={"Content-Type": "application/json"}
        )
        weather = response.json()
    except Exception as e:
        print(f"Weather service error: {e}")
        weather = {"temp": 72, "condition": "Unknown"}
    
    # Build trip plan
    plan = {
        "destination": city,
        "duration_days": days,
        "weather_forecast": weather,
        "recommended_activities": [],
        "estimated_cost": days * 150
    }
    
    # Add activities based on weather
    if weather.get("temp", 0) > 75:
        plan["recommended_activities"] = ["Beach", "Outdoor dining", "Swimming"]
    elif weather.get("temp", 0) > 60:
        plan["recommended_activities"] = ["Walking tours", "Museums", "Parks"]
    else:
        plan["recommended_activities"] = ["Indoor museums", "Shopping", "Restaurants"]
    
    return plan

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8200)
