from .. import get_current_time, TIMEZONE, redis_client
from ..models import Weather, db
from datetime import datetime, timedelta
import requests
import os


class WeatherService:
    RATE_LIMIT_KEY = "weather_api_last_call"
    RATE_LIMIT_SECONDS = 300  # 5 minutes

    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHER_API_KEY')
        self.lat = os.environ.get('WEATHER_LAT')
        self.lon = os.environ.get('WEATHER_LON')
        self.base_url = "https://api.openweathermap.org/data/3.0/onecall"

    def can_fetch_weather(self):
        """Check if enough time has passed since last API call"""
        last_call = redis_client.get(self.RATE_LIMIT_KEY)
        if not last_call:
            return True
        
        last_call_time = datetime.fromtimestamp(float(last_call), tz=TIMEZONE)
        time_passed = get_current_time() - last_call_time
        
        return time_passed.total_seconds() >= self.RATE_LIMIT_SECONDS

    def update_last_fetch_time(self):
        """Update the timestamp of last API call"""
        redis_client.set(
            self.RATE_LIMIT_KEY, 
            get_current_time().timestamp(), 
            ex=self.RATE_LIMIT_SECONDS
        )

    def fetch_weather_data(self):
        """Fetches weather data from OpenWeatherMap API with rate limiting"""
        if not self.can_fetch_weather():
            print("[WEATHER] Rate limit in effect, skipping fetch")
            return None

        params = {
            'lat': self.lat,
            'lon': self.lon,
            'exclude': 'current,daily,alerts',
            'lang': 'de',
            'units': 'metric',
            'appid': self.api_key
        }

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            self.update_last_fetch_time()
            return response.json()
        except requests.RequestException as e:
            print(f"[WEATHER] Error fetching weather data: {e}")
            return None

    def convert_timestamp(self, unix_timestamp):
        """Convert Unix timestamp to datetime with correct timezone"""
        return datetime.fromtimestamp(unix_timestamp, tz=TIMEZONE)

    def process_minutely(self, minutely_data):
        """Process minutely precipitation data with correct timezone"""
        records = []
        for minute in minutely_data:
            weather = Weather(
                timestamp=self.convert_timestamp(minute['dt']),
                forecast_type='minutely',
                precipitation=minute['precipitation']
            )
            records.append(weather)
        return records

    def process_hourly(self, hourly_data):
        """Process hourly weather data with correct timezone"""
        records = []
        for hour in hourly_data:
            rain = hour.get('rain', {}).get('1h', 0)
            snow = hour.get('snow', {}).get('1h', 0)
            total_precipitation = rain + snow

            weather = Weather(
                timestamp=self.convert_timestamp(hour['dt']),
                forecast_type='hourly',
                total_precipitation=total_precipitation,
                pop=hour['pop'],
                weather_icon=hour['weather'][0]['icon']
            )
            records.append(weather)
        return records

    def cleanup_old_records(self):
        """Remove weather records older than 24 hours"""
        cutoff_time = get_current_time() - timedelta(hours=24)
        Weather.query.filter(Weather.timestamp < cutoff_time).delete()
        db.session.commit()

    def update_weather(self):
        """Main method to fetch and store weather data"""
        data = self.fetch_weather_data()
        if not data:
            return False

        try:
            # Clean up old records first
            self.cleanup_old_records()

            # Process and store minutely data
            if 'minutely' in data:
                minutely_records = self.process_minutely(data['minutely'])
                db.session.bulk_save_objects(minutely_records)

            # Process and store hourly data
            if 'hourly' in data:
                hourly_records = self.process_hourly(data['hourly'])
                db.session.bulk_save_objects(hourly_records)

            db.session.commit()
            return True

        except Exception as e:
            print(f"[WEATHER] Error storing weather data: {e}")
            db.session.rollback()
            return False
