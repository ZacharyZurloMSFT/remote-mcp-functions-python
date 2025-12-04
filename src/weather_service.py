"""Utility module for retrieving weather information for the MCP weather tool."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


class WeatherServiceError(RuntimeError):
    """Represents failures encountered when calling the external weather APIs."""


@dataclass(frozen=True)
class Location:
    name: str
    country: Optional[str]
    latitude: float
    longitude: float


class WeatherService:
    _GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
    _WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, session: Optional[requests.Session] = None, timeout_seconds: int = 10) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout_seconds

    def get_weather(self, city_name: str, country_code: Optional[str] = None) -> Dict[str, Any]:
        """Get weather readings for the supplied city."""

        location = self._resolve_location(city_name, country_code)
        weather_payload = self._fetch_weather(location)

        current = weather_payload.get("current", {})
        units = weather_payload.get("current_units", {})

        return {
            "location": {
                "city": location.name,
                "country": location.country,
                "latitude": location.latitude,
                "longitude": location.longitude,
            },
            "conditions": {
                "temperature": {
                    "value": current.get("temperature_2m"),
                    "unit": units.get("temperature_2m"),
                },
                "relativeHumidity": {
                    "value": current.get("relative_humidity_2m"),
                    "unit": units.get("relative_humidity_2m"),
                },
                "wind": {
                    "speed": {
                        "value": current.get("wind_speed_10m"),
                        "unit": units.get("wind_speed_10m"),
                    },
                    "direction": {
                        "value": current.get("wind_direction_10m"),
                        "unit": units.get("wind_direction_10m"),
                    },
                },
                "precipitation": {
                    "value": current.get("precipitation"),
                    "unit": units.get("precipitation"),
                },
                "weatherCode": current.get("weather_code"),
                "time": current.get("time"),
            },
            "attribution": {
                "source": "Open-Meteo",
                "license": "CC BY 4.0",
                "url": "https://open-meteo.com/",
            },
        }

    def _resolve_location(self, city_name: str, country_code: Optional[str]) -> Location:
        params = {
            "name": city_name,
            "count": 1,
            "language": "en",
            "format": "json",
        }
        if country_code:
            params["country"] = country_code

        payload = self._perform_get(self._GEOCODING_ENDPOINT, params)
        results = payload.get("results") or []
        if not results:
            raise WeatherServiceError(f"No results found for '{city_name}'")

        city = results[0]
        return Location(
            name=city.get("name", city_name),
            country=city.get("country"),
            latitude=float(city["latitude"]),
            longitude=float(city["longitude"]),
        )

    def _fetch_weather(self, location: Location) -> Dict[str, Any]:
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,weather_code",
        }

        payload = self._perform_get(self._WEATHER_ENDPOINT, params)
        if "current" not in payload:
            raise WeatherServiceError("Weather API response missing current conditions")
        return payload

    def _perform_get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            logging.exception("Weather API returned HTTP %s", exc.response.status_code if exc.response else "unknown")
            raise WeatherServiceError("Weather service returned an error response") from exc
        except requests.RequestException as exc:
            logging.exception("Weather API request failed: %s", exc)
            raise WeatherServiceError("Unable to reach the weather service") from exc
        except ValueError as exc:  # JSON decoding error
            logging.exception("Failed to decode weather API response")
            raise WeatherServiceError("Received unexpected data from the weather service") from exc