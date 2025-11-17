"""Weather tool using OpenWeatherMap API."""

from typing import Any, Dict, Optional

import aiohttp

from app.tools.base import BaseTool
from app.utils.config import settings
from app.utils.logger import logger


class WeatherTool(BaseTool):
    """Tool for getting weather information using OpenWeatherMap API."""

    def __init__(self):
        super().__init__(
            name="weather",
            description="Get current weather information for any city. Returns temperature, conditions, humidity, wind speed, etc. Supports converting to Celsius or Fahrenheit.",
        )
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g., 'London', 'New York', 'Kanpur')",
                },
                "country": {
                    "type": "string",
                    "description": "Optional country code (e.g., 'US', 'GB', 'IN')",
                },
                "units": {
                    "type": "string",
                    "description": "Temperature units: 'celsius', 'fahrenheit', or 'kelvin' (default: celsius)",
                    "enum": ["celsius", "fahrenheit", "kelvin"],
                    "default": "celsius",
                },
            },
            "required": ["city"],
        }

    async def execute(
        self,
        city: str,
        country: Optional[str] = None,
        units: str = "celsius",
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute weather lookup."""
        # Check if API key is configured
        api_key = settings.openweather_api_key
        
        if not api_key:
            logger.warning("OpenWeatherMap API key not configured, attempting to scrape weather data")
            return await self._fallback_scrape_weather(city, units)
        
        try:
            # Build location query
            location = f"{city},{country}" if country else city
            
            # Map units to OpenWeatherMap API parameter
            unit_map = {
                "celsius": "metric",
                "fahrenheit": "imperial",
                "kelvin": "standard",
            }
            api_units = unit_map.get(units.lower(), "metric")
            
            # Build API URL
            params = {
                "q": location,
                "appid": api_key,
                "units": api_units,
            }
            
            logger.info(f"Fetching weather for: {location} in {units}")
            
            # Make API request
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.base_url, params=params) as response:
                    status = response.status
                    data = await response.json()
                    
                    if status != 200:
                        error_msg = data.get("message", "Unknown error")
                        logger.error(f"Weather API error: {error_msg}")
                        
                        # If API key is invalid, fall back to scraping
                        if status == 401:
                            logger.warning("Invalid API key, falling back to web scraping")
                            return await self._fallback_scrape_weather(city, units)
                        
                        return {
                            "success": False,
                            "error": f"Weather API error ({status}): {error_msg}",
                            "result": None,
                        }
            
            # Parse response
            temp_symbol = {"celsius": "°C", "fahrenheit": "°F", "kelvin": "K"}[units.lower()]
            
            weather_data = {
                "city": data["name"],
                "country": data["sys"].get("country"),
                "temperature": {
                    "current": data["main"]["temp"],
                    "feels_like": data["main"]["feels_like"],
                    "min": data["main"]["temp_min"],
                    "max": data["main"]["temp_max"],
                    "unit": units,
                    "symbol": temp_symbol,
                },
                "conditions": {
                    "main": data["weather"][0]["main"],
                    "description": data["weather"][0]["description"],
                },
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind": {
                    "speed": data["wind"]["speed"],
                    "direction": data["wind"].get("deg"),
                },
                "visibility": data.get("visibility"),
                "clouds": data["clouds"].get("all"),
            }
            
            # Format a nice summary
            summary = (
                f"Weather in {weather_data['city']}, {weather_data['country']}: "
                f"{weather_data['temperature']['current']}{temp_symbol} "
                f"({weather_data['conditions']['description']}). "
                f"Feels like {weather_data['temperature']['feels_like']}{temp_symbol}. "
                f"Humidity: {weather_data['humidity']}%."
            )
            
            logger.info(f"Weather data retrieved successfully: {summary}")
            
            return {
                "success": True,
                "result": {
                    "summary": summary,
                    "data": weather_data,
                },
            }
            
        except Exception as e:
            logger.error(f"Weather lookup failed: {e}", exc_info=True)
            # Try fallback scraping on any error
            return await self._fallback_scrape_weather(city, units)
    
    async def _fallback_scrape_weather(self, city: str, units: str = "celsius") -> Dict[str, Any]:
        """Fallback method to scrape weather from wttr.in (a free weather service)."""
        try:
            logger.info(f"Using fallback weather service for: {city}")
            
            # wttr.in is a free, no-API-key weather service
            url = f"https://wttr.in/{city}?format=j1"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"Could not retrieve weather data. Please configure OpenWeatherMap API key in .env file (OPENWEATHER_API_KEY=your_key)",
                            "result": None,
                        }
                    
                    data = await response.json()
            
            # Parse wttr.in response
            current = data["current_condition"][0]
            
            # Convert temperature based on units
            temp_c = float(current["temp_C"])
            if units.lower() == "fahrenheit":
                temp = (temp_c * 9/5) + 32
                temp_symbol = "°F"
            elif units.lower() == "kelvin":
                temp = temp_c + 273.15
                temp_symbol = "K"
            else:  # celsius
                temp = temp_c
                temp_symbol = "°C"
            
            weather_data = {
                "city": city,
                "temperature": {
                    "current": round(temp, 1),
                    "unit": units,
                    "symbol": temp_symbol,
                },
                "conditions": {
                    "description": current["weatherDesc"][0]["value"],
                },
                "humidity": current["humidity"],
                "wind": {
                    "speed": current["windspeedKmph"],
                },
                "source": "wttr.in (fallback)",
            }
            
            summary = (
                f"Weather in {city}: "
                f"{weather_data['temperature']['current']}{temp_symbol} "
                f"({weather_data['conditions']['description']}). "
                f"Humidity: {weather_data['humidity']}%."
            )
            
            logger.info(f"Weather data retrieved via fallback: {summary}")
            
            return {
                "success": True,
                "result": {
                    "summary": summary,
                    "data": weather_data,
                    "note": "Using fallback weather service. For more accurate data, configure OpenWeatherMap API key.",
                },
            }
            
        except Exception as e:
            logger.error(f"Fallback weather lookup failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Weather lookup failed: {str(e)}. Please configure OpenWeatherMap API key in .env file (OPENWEATHER_API_KEY=your_key) or check your internet connection.",
                "result": None,
            }








