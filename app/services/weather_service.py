from .. import WEEKDAY_MAPPING, get_current_time, TIMEZONE, redis_client
from ..models import Weather, db
from datetime import datetime, timedelta, time
from flask import current_app as app
import requests
import os
import pytz


class WeatherService:
    RATE_LIMIT_KEY = "weather_api_last_call"
    RATE_LIMIT_SECONDS = 5  # 5 minutes, 300 seconds

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
        app.logger.info("[WEATHER] Starting weather data fetch")
        if not self.can_fetch_weather():
            app.logger.info("[WEATHER] Rate limit in effect, skipping fetch")
            return None

        params = {
            'lat': self.lat,
            'lon': self.lon,
            'exclude': 'current,alerts',
            'lang': 'de',
            'units': 'metric',
            'appid': self.api_key
        }
        app.logger.debug(f"[WEATHER] Request parameters: lat={self.lat}, lon={self.lon}")

        try:
            app.logger.info("[WEATHER] Making API request")
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            self.update_last_fetch_time()
            app.logger.info("[WEATHER] API request successful")
            return response.json()
        except requests.RequestException as e:
            app.logger.error(f"[WEATHER] Error fetching weather data: {str(e)}")
            return None

    def update_weather(self):
        """Main method to fetch and store weather data"""
        app.logger.info("[WEATHER] Starting weather update process")
        data = self.fetch_weather_data()
        if not data:
            app.logger.info("[WEATHER] No data received from API")
            return False

        try:
            app.logger.info("[WEATHER] Cleaning up old records")
            self.cleanup_old_records()

            if 'minutely' in data:
                app.logger.info("[WEATHER] Processing minutely data")
                minutely_records = self.process_minutely(data['minutely'])
                app.logger.info(f"[WEATHER] Created {len(minutely_records)} minutely records")
                if minutely_records:
                    db.session.bulk_save_objects(minutely_records)
                    app.logger.info(f"[WEATHER] Saved {len(minutely_records)} minutely records to database")

            if 'hourly' in data:
                app.logger.info("[WEATHER] Processing hourly data")
                hourly_records = self.process_hourly(data['hourly'])
                app.logger.info(f"[WEATHER] Created {len(hourly_records)} hourly records")
                if hourly_records:
                    db.session.bulk_save_objects(hourly_records)
                    app.logger.info(f"[WEATHER] Saved {len(hourly_records)} hourly records to database")

            if 'daily' in data:
                app.logger.info("[WEATHER] Processing daily data")
                daily_records = self.process_daily(data['daily'])
                app.logger.info(f"[WEATHER] Created {len(daily_records)} daily records")
                if daily_records:
                    db.session.bulk_save_objects(daily_records)
                    app.logger.info(f"[WEATHER] Saved {len(daily_records)} daily records to database")

            db.session.commit()
            
            # Verify actual database content
            all_records = Weather.query.all()
            minutely = [r for r in all_records if r.forecast_type == 'minutely']
            hourly = [r for r in all_records if r.forecast_type == 'hourly']
            daily = [r for r in all_records if r.forecast_type == 'daily']
            
            app.logger.info(f"[WEATHER] Database verification:")
            app.logger.info(f"[WEATHER] Minutely records: {len(minutely)}")
            app.logger.info(f"[WEATHER] Sample minutely timestamps: {[r.timestamp for r in minutely[:5]]}")
            app.logger.info(f"[WEATHER] Hourly records: {len(hourly)}")
            app.logger.info(f"[WEATHER] Daily records: {len(daily)}")
            
            return True
            
        except Exception as e:
            app.logger.error(f"[WEATHER] Error: {str(e)}")
            db.session.rollback()
        return False


    def convert_timestamp(self, unix_timestamp):
        """Convert UTC unix timestamp to local datetime once and for all"""
        utc_time = datetime.fromtimestamp(unix_timestamp, tz=pytz.UTC)
        local_time = utc_time.astimezone(TIMEZONE)
        # Return naive datetime after conversion
        return local_time.replace(tzinfo=None)


    def process_minutely(self, minutely_data):
        """Process minutely precipitation data with local timezone"""
        records = []
        for minute in minutely_data:
            local_timestamp = self.convert_timestamp(minute['dt'])
            
            # Check for existing record
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'minutely'
            ).first()
            
            if existing:
                app.logger.debug(f"[WEATHER] Skipping duplicate minutely record for {local_timestamp}")
                continue
            
            # Calculate PoP based on precipitation
            pop = 1.0 if minute['precipitation'] > 0 else 0.0
            
            weather = Weather(
                timestamp=local_timestamp,
                forecast_type='minutely',
                precipitation=minute['precipitation'],
                pop=pop
            )
            records.append(weather)
            
            app.logger.debug(f"[WEATHER] Created new minutely record: timestamp={local_timestamp}, "
                            f"precipitation={minute['precipitation']}, pop={pop}")
        return records


    def process_hourly(self, hourly_data):
        records = []
        for hour in hourly_data:
            local_timestamp = self.convert_timestamp(hour['dt'])
            
            # Check for existing record
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'hourly'
            ).first()
            
            if existing:
                app.logger.debug(f"[WEATHER] Skipping duplicate hourly record for {local_timestamp}")
                continue

            rain = hour.get('rain', {}).get('1h', 0)
            snow = hour.get('snow', {}).get('1h', 0)
            total_precipitation = rain + snow

            weather = Weather(
                timestamp=local_timestamp,
                forecast_type='hourly',
                total_precipitation=total_precipitation,
                pop=hour['pop'],
                weather_icon=hour['weather'][0]['icon']
            )
            records.append(weather)
        return records

    def process_daily(self, daily_data):
        """Process daily weather data with local timezone"""
        records = []
        for day in daily_data:
            local_timestamp = self.convert_timestamp(day['dt'])
            
            # Check for existing record before creating new one
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'daily'
            ).first()
            
            if existing:
                app.logger.debug(f"[WEATHER] Skipping duplicate daily record for {local_timestamp}")
                continue
                
            rain = day.get('rain', 0)
            snow = day.get('snow', 0)
            total_precipitation = rain + snow

            weather = Weather(
                timestamp=local_timestamp,
                forecast_type='daily',
                total_precipitation=total_precipitation,
                pop=day['pop'],
                weather_icon=day['weather'][0]['icon']
            )
            records.append(weather)
            app.logger.debug(f"[WEATHER] Created new daily record for {local_timestamp}")
            
        return records


    def cleanup_old_records(self):
        """Remove weather records older than 1 hour"""
        cutoff_time = get_current_time().replace(tzinfo=None)  # Remove timezone info
        Weather.query.filter(Weather.timestamp < cutoff_time).delete()
        db.session.commit()



    def get_weather_for_timeframe(self, date, schedule, include_details=False):
        """Calculate weather data for a specific timeframe using hourly records with partial hour handling"""
        weekday = WEEKDAY_MAPPING[date.weekday()]
        
        start_time = getattr(schedule, f"{weekday}_start")
        end_time = getattr(schedule, f"{weekday}_end")
        
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)
        
        app.logger.debug(f"[WEATHER] Checking weather from {start_datetime} to {end_datetime}")
        
        weather_records = Weather.query.filter(
            Weather.timestamp >= start_datetime.replace(minute=0),
            Weather.timestamp <= end_datetime.replace(minute=0),
            Weather.forecast_type == 'hourly'
        ).order_by(Weather.timestamp).all()
        
        if not weather_records:
            return None
            
        # Initialize aggregated values
        max_pop = 0
        total_precipitation = 0
        hourly_details = []
        
        for record in weather_records:
            hour_start = record.timestamp
            hour_end = hour_start + timedelta(hours=1)
            
            # Calculate overlap duration in minutes
            overlap_start = max(start_datetime, hour_start)
            overlap_end = min(end_datetime, hour_end)
            overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
            
            # Calculate precipitation contribution based on overlap
            precipitation_contribution = (record.total_precipitation or 0) * (overlap_minutes / 60)
            total_precipitation += precipitation_contribution
            
            # Track maximum probability
            max_pop = max(max_pop, record.pop)
            
            hourly_details.append({
                'timestamp': record.timestamp.strftime('%H:%M'),
                'total_precipitation': record.total_precipitation,
                'overlap_minutes': overlap_minutes,
                'contribution': precipitation_contribution,
                'pop': record.pop
            })
        
        result = {
            'icon': weather_records[0].weather_icon,
            'pop': max_pop,
            'precipitation': round(total_precipitation, 2)
        }
        
        if include_details:
            return {
                'available': True,
                'date': date.strftime('%Y-%m-%d'),
                'startTime': start_time.strftime('%H:%M'),
                'endTime': end_time.strftime('%H:%M'),
                'calculation_details': {
                    'hourly_used': hourly_details
                },
                'result': result
            }
        
        return result




