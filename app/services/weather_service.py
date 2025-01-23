from .. import WEEKDAY_MAPPING, get_current_time, get_current_date, TIMEZONE, redis_client
from ..models import db, Weather, WeatherCalculation, WalkingBus, WalkingBusSchedule
from datetime import datetime, timedelta, time
from flask import current_app as app
import requests
import os
import pytz
import json


WEATHER_ICON_MAP = {
    "day": {
        "200": "thunderstorms-day-rain",
        "201": "thunderstorms-day-rain",
        "202": "thunderstorms-day-overcast-rain",
        "210": "thunderstorms-day",
        "211": "thunderstorms",
        "212": "thunderstorms-overcast",
        "221": "thunderstorms-overcast",
        "230": "thunderstorms-day-rain",
        "231": "thunderstorms-day-rain",
        "232": "thunderstorms-day-rain",
        "300": "partly-cloudy-day-drizzle",
        "301": "partly-cloudy-day-drizzle",
        "302": "overcast-day-drizzle",
        "310": "overcast-day-drizzle",
        "311": "drizzle",
        "312": "overcast-drizzle",
        "313": "overcast-drizzle",
        "314": "overcast-rain",
        "321": "overcast-rain",
        "500": "partly-cloudy-day-rain",
        "501": "partly-cloudy-day-rain",
        "502": "overcast-day-rain",
        "503": "overcast-day-rain",
        "504": "overcast-rain",
        "511": "sleet",
        "520": "partly-cloudy-day-rain",
        "521": "partly-cloudy-day-rain",
        "522": "overcast-day-rain",
        "531": "overcast-day-rain",
        "600": "partly-cloudy-day-snow",
        "601": "partly-cloudy-day-snow",
        "602": "overcast-day-snow",
        "611": "partly-cloudy-day-sleet",
        "612": "partly-cloudy-day-sleet",
        "613": "overcast-day-sleet",
        "615": "partly-cloudy-day-sleet",
        "616": "partly-cloudy-day-sleet",
        "620": "partly-cloudy-day-snow",
        "621": "partly-cloudy-day-snow",
        "622": "overcast-snow",
        "701": "mist",
        "711": "partly-cloudy-day-smoke",
        "721": "haze-day",
        "731": "dust-day",
        "741": "fog-day",
        "751": "dust-day",
        "761": "dust-day",
        "762": "overcast-smoke",
        "771": "wind",
        "781": "tornado",
        "800": "clear-day",
        "801": "partly-cloudy-day",
        "802": "partly-cloudy-day",
        "803": "overcast-day",
        "804": "overcast-day"
    },
    "night": {
        "200": "thunderstorms-night-rain",
        "201": "thunderstorms-night-rain",
        "202": "thunderstorms-night-overcast-rain",
        "210": "thunderstorms-night",
        "211": "thunderstorms",
        "212": "thunderstorms-overcast",
        "221": "thunderstorms-overcast",
        "230": "thunderstorms-night-rain",
        "231": "thunderstorms-night-rain",
        "232": "thunderstorms-night-rain",
        "300": "partly-cloudy-night-drizzle",
        "301": "partly-cloudy-night-drizzle",
        "302": "overcast-night-drizzle",
        "310": "overcast-night-drizzle",
        "311": "drizzle",
        "312": "overcast-drizzle",
        "313": "overcast-drizzle",
        "314": "overcast-rain",
        "321": "overcast-rain",
        "500": "partly-cloudy-night-rain",
        "501": "partly-cloudy-night-rain",
        "502": "overcast-night-rain",
        "503": "overcast-night-rain",
        "504": "overcast-rain",
        "511": "sleet",
        "520": "partly-cloudy-night-rain",
        "521": "partly-cloudy-night-rain",
        "522": "overcast-night-rain",
        "531": "overcast-night-rain",
        "600": "partly-cloudy-night-snow",
        "601": "partly-cloudy-night-snow",
        "602": "overcast-night-snow",
        "611": "partly-cloudy-night-sleet",
        "612": "partly-cloudy-night-sleet",
        "613": "overcast-night-sleet",
        "615": "partly-cloudy-night-sleet",
        "616": "partly-cloudy-night-sleet",
        "620": "partly-cloudy-night-snow",
        "621": "partly-cloudy-night-snow",
        "622": "overcast-snow",
        "701": "mist",
        "711": "partly-cloudy-night-smoke",
        "721": "haze-night",
        "731": "dust-night",
        "741": "fog-night",
        "751": "dust-night",
        "761": "dust-night",
        "762": "overcast-smoke",
        "771": "wind",
        "781": "tornado",
        "800": "clear-night",
        "801": "partly-cloudy-night",
        "802": "partly-cloudy-night",
        "803": "overcast-night",
        "804": "overcast-night"
    }
}


class WeatherService:
    RATE_LIMIT_KEY = "weather_api_last_call"
    RATE_LIMIT_SECONDS = 120

    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHER_API_KEY')
        self.lat = os.environ.get('WEATHER_LAT')
        self.lon = os.environ.get('WEATHER_LON')
        self.base_url = "https://api.openweathermap.org/data/3.0/onecall"

    def can_fetch_weather(self):
        """Check if enough time has passed since last API call"""
        print("[WEATHER] Checking rate limit")
        last_call = redis_client.get(self.RATE_LIMIT_KEY)
        print(f"[WEATHER] Last call timestamp: {last_call}")
        
        # Always update timestamp when checking
        current_timestamp = get_current_time().timestamp()
        
        if not last_call:
            print("[WEATHER] No previous call found, setting initial timestamp")
            redis_client.set(
                self.RATE_LIMIT_KEY,
                current_timestamp,
                ex=self.RATE_LIMIT_SECONDS * 2
            )
            return True, 0
        
        last_call_time = datetime.fromtimestamp(float(last_call), tz=TIMEZONE)
        time_passed = get_current_time() - last_call_time
        seconds_remaining = max(0, self.RATE_LIMIT_SECONDS - time_passed.total_seconds())
        print(f"[WEATHER] Time remaining: {seconds_remaining} seconds")
        
        can_fetch = time_passed.total_seconds() >= self.RATE_LIMIT_SECONDS
        print(f"[WEATHER] Can fetch weather: {can_fetch}")
        
        # Update timestamp if we're allowing the fetch
        if can_fetch:
            redis_client.set(
                self.RATE_LIMIT_KEY,
                current_timestamp,
                ex=self.RATE_LIMIT_SECONDS * 2
            )
        
        return can_fetch, round(seconds_remaining)

    def update_last_fetch_time(self):
        """Update the timestamp of last API call"""
        current_timestamp = get_current_time().timestamp()
        redis_client.set(
            self.RATE_LIMIT_KEY,
            current_timestamp,
            ex=self.RATE_LIMIT_SECONDS * 2
        )
        # Notify frontend only here, after successful data processing
        redis_client.publish('status_updates', json.dumps({
            "type": "weather_update",
            "timestamp": get_current_time().isoformat(),
            "status": "success"
        }))

    def fetch_weather_data(self):
        """Fetches weather data from OpenWeatherMap API with rate limiting"""
        app.logger.info("[WEATHER] Starting weather data fetch")
        
        # Rate limiting check moved to update_weather()
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
            app.logger.info("[WEATHER] API request successful")
            return response.json()
        except requests.RequestException as e:
            app.logger.error(f"[WEATHER] Error fetching weather data: {str(e)}")
            return None

    def update_weather(self):
        LOCK_KEY = "weather_update_lock"
        LOCK_TIMEOUT = 10  # seconds
        
        print("[WEATHER] Starting weather update process")
        
        # Keep the lock mechanism for API rate limiting
        lock_acquired = redis_client.set(
            LOCK_KEY,
            'locked',
            ex=LOCK_TIMEOUT,
            nx=True
        )
        
        if not lock_acquired:
            print("[WEATHER] Another process is updating weather data")
            return {"success": False, "message": "Another update is in progress"}
            
        try:
            # Process raw weather data as before
            can_fetch, seconds_remaining = self.can_fetch_weather()
            if not can_fetch:
                print("[WEATHER] Rate limit in effect, skipping update")
                return {
                    "success": False, 
                    "message": f"Rate limit in effect. Please wait {seconds_remaining} seconds before updating"
                }

            data = self.fetch_weather_data()
            if not data:
                print("[WEATHER] No data received from API")
                return {"success": False, "message": "No data received from weather API"}

            # Clean and save raw weather records
            self.cleanup_old_records()
            self.cleanup_old_calculations()
            records_to_save = []
            for data_type in ['minutely', 'hourly', 'daily']:
                if data_type in data:
                    processor = getattr(self, f'process_{data_type}')
                    records = processor(data[data_type])
                    print(f"[WEATHER] Processed {len(records)} {data_type} records")
                    records_to_save.extend(records)

            if records_to_save:
                print(f"[WEATHER] Saving {len(records_to_save)} total records")
                db.session.bulk_save_objects(records_to_save)
                db.session.commit()

            # New: Calculate and store weather for each walking bus
            print("[WEATHER] Starting weather calculations for walking buses")
            buses = WalkingBus.query.all()
            calculations_to_save = []
            
            print("[WEATHER] Cleaning up existing calculations")
            for bus in buses:
                current_date = get_current_date()
                end_date = current_date + timedelta(days=6)
                WeatherCalculation.query.filter(
                    WeatherCalculation.walking_bus_id == bus.id,
                    WeatherCalculation.date >= current_date,
                    WeatherCalculation.date <= end_date
                ).delete()
            db.session.commit()

            for bus in buses:
                print(f"[WEATHER] Processing calculations for bus {bus.id}")
                schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=bus.id).first()
                
                # Calculate for next 6 days
                current_date = get_current_date()
                for i in range(6):
                    target_date = current_date + timedelta(days=i)
                    
                    # Get weather calculation
                    weather_data = self.get_weather_for_timeframe(target_date, schedule, include_details=True)
                    if not weather_data:
                        continue

                    print(f"[WEATHER CALC] Saving calculation for date {target_date}: "
                        f"type={weather_data['calculation_details']['coverage_type']}, "
                        f"precip={weather_data['result']['precipitation']}")
                    
                    # Create or update calculation record
                    calc = WeatherCalculation.query.filter_by(
                        walking_bus_id=bus.id,
                        date=target_date
                    ).first()
                    
                    if not calc:
                        calc = WeatherCalculation(
                            walking_bus_id=bus.id,
                            date=target_date
                        )
                    
                    # Store calculation results
                    calc.icon = weather_data['result']['icon']
                    calc.precipitation = weather_data['result']['precipitation']
                    calc.pop = weather_data['result']['pop']
                    calc.calculation_type = weather_data['calculation_details']['coverage_type']
                    calc.last_updated = get_current_time()
                    
                    if not calc.id:  # New record
                        calculations_to_save.append(calc)
            
            # Bulk save all calculations
            if calculations_to_save:
                print(f"[WEATHER] Saving {len(calculations_to_save)} weather calculations")
                for calc in calculations_to_save:
                    print(f"Bus {calc.walking_bus_id}, Date {calc.date}: {calc.calculation_type}")
                db.session.bulk_save_objects(calculations_to_save)
                db.session.commit()

            # Verify and notify
            self._verify_database_state()
            self._verify_calculations_state()  # New verification method
            
            redis_client.set(
                self.RATE_LIMIT_KEY,
                get_current_time().timestamp(),
                ex=self.RATE_LIMIT_SECONDS * 2
            )
            
            redis_client.publish('status_updates', json.dumps({
                "type": "weather_update",
                "timestamp": get_current_time().isoformat(),
                "status": "success"
            }))

            return {"success": True, "message": "Weather data updated successfully"}

        except Exception as e:
            print(f"[WEATHER] Error during update: {str(e)}")
            db.session.rollback()
            return {"success": False, "message": f"Error during update: {str(e)}"}
            
        finally:
            redis_client.delete(LOCK_KEY)

    def cleanup_old_calculations(self):
        """Remove outdated weather calculations"""
        cutoff_date = get_current_date() - timedelta(days=1)
        WeatherCalculation.query.filter(
            WeatherCalculation.date < cutoff_date
        ).delete()
        db.session.commit()

    def _verify_database_state(self):
        """Helper method for database state verification"""
        current_records = Weather.query.all()
        verification = {
            'minutely': [r for r in current_records if r.forecast_type == 'minutely'],
            'hourly': [r for r in current_records if r.forecast_type == 'hourly'],
            'daily': [r for r in current_records if r.forecast_type == 'daily']
        }

        print("[WEATHER] Database verification results:")
        for forecast_type, records in verification.items():
            print(f"[WEATHER] {forecast_type.capitalize()} records: {len(records)}")
            if records:
                latest = records[-1]
                print(f"[WEATHER] Latest {forecast_type} record: {latest.timestamp}")
                print(f"[WEATHER] Sample icon: {latest.weather_icon}")

        total_saved = sum(len(records) for records in verification.values())
        print(f"[WEATHER] Final database record count: {total_saved}")

    def _verify_calculations_state(self):
        """Verify the state of weather calculations"""
        current_date = get_current_date()
        calculations = WeatherCalculation.query.all()
        buses = WalkingBus.query.count()
        
        # Count calculations for current date
        current_date_calcs = [c for c in calculations if c.date == current_date]
        
        print("[WEATHER CALC] Weather calculations verification:")
        print(f"[WEATHER CALC] Total calculations: {len(calculations)}")
        print(f"[WEATHER CALC] Active walking buses: {buses}")
        print(f"[WEATHER CALC] Calculations per bus: {len(calculations)/buses if buses > 0 else 0}")
        print(f"[WEATHER CALC] Calculations for current date ({current_date}): {len(current_date_calcs)}")
        
        # Verify latest calculations
        latest = WeatherCalculation.query.order_by(WeatherCalculation.last_updated.desc()).first()
        if latest:
            print(f"[WEATHER CALC] Latest calculation: {latest.date} for bus {latest.walking_bus_id}")
            print(f"[WEATHER CALC] Calculation type: {latest.calculation_type}")

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
            
            # Get the corresponding hourly record by rounding down to the hour
            hourly_timestamp = local_timestamp.replace(minute=0)
            hourly_record = Weather.query.filter(
                Weather.timestamp == hourly_timestamp,
                Weather.forecast_type == 'hourly'
            ).first()
            
            # Use hourly PoP if available, otherwise fallback to binary calculation
            pop = hourly_record.pop if hourly_record else (1.0 if minute['precipitation'] > 0 else 0.0)
            
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
        print(f"[WEATHER] Processing {len(hourly_data)} hourly records") # Immediate feedback
        
        for hour in hourly_data:
            local_timestamp = self.convert_timestamp(hour['dt'])
            print(f"[WEATHER] Processing hour: {local_timestamp}")  # Debug timestamp
            
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'hourly'
            ).first()
            
            if existing:
                print(f"[WEATHER] Skipping duplicate hourly record for {local_timestamp}")
                continue

            weather_code = str(hour['weather'][0]['id'])
            is_night = hour['weather'][0]['icon'].endswith('n')
            time_of_day = "night" if is_night else "day"
            
            # Now using SVG icon names
            icon_name = WEATHER_ICON_MAP[time_of_day].get(
                weather_code,
                "clear-night" if is_night else "clear-day"
            )
            print(f"[WEATHER] Mapped weather code {weather_code} to icon {icon_name}")

            rain = hour.get('rain', {}).get('1h', 0)
            snow = hour.get('snow', {}).get('1h', 0)
            total_precipitation = rain + snow

            # Set pop to 0 if no precipitation
            pop = 0.0 if total_precipitation == 0 else hour['pop']

            weather = Weather(
                timestamp=local_timestamp,
                forecast_type='hourly',
                total_precipitation=total_precipitation,
                pop=pop,
                weather_icon=icon_name  # Using mapped SVG icon name
            )
            records.append(weather)
            print(f"[WEATHER] Created hourly record with icon {icon_name}")
        
        return records

    def process_daily(self, daily_data):
        records = []
        print(f"[WEATHER] Processing {len(daily_data)} daily records")
        
        for day in daily_data:
            local_timestamp = self.convert_timestamp(day['dt'])
            print(f"[WEATHER] Processing day: {local_timestamp}")
            
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'daily'
            ).first()
            
            if existing:
                print(f"[WEATHER] Skipping duplicate daily record for {local_timestamp}")
                continue
            
            weather_code = str(day['weather'][0]['id'])
            icon_name = WEATHER_ICON_MAP['day'].get(weather_code, "clear-day")
            print(f"[WEATHER] Mapped weather code {weather_code} to icon {icon_name}")

            rain = day.get('rain', 0)
            snow = day.get('snow', 0)
            total_precipitation = rain + snow

            pop = 0.0 if total_precipitation == 0 else day['pop']

            weather = Weather(
                timestamp=local_timestamp,
                forecast_type='daily',
                total_precipitation=total_precipitation,
                pop=pop,
                weather_icon=icon_name
            )
            records.append(weather)
            print(f"[WEATHER] Created daily record with icon {icon_name}")
        
        return records

    def cleanup_old_records(self):
        """Remove weather records older than 1 hour"""
        cutoff_time = get_current_time() - timedelta(hours=12)
        Weather.query.filter(Weather.timestamp < cutoff_time).delete()
        db.session.commit()

    def get_weather_for_timeframe(self, date, schedule, include_details=False):
        """Calculate weather data for a specific timeframe with daily fallback"""
        weekday = WEEKDAY_MAPPING[date.weekday()]
        
        # Check if schedule is active for this day
        is_active = getattr(schedule, weekday, False)
        if not is_active:
            print(f"[WEATHER] Schedule inactive for {weekday}, using daily data")
            # Use daily data directly when schedule is inactive
            daily_record = Weather.query.filter(
                Weather.timestamp == datetime.combine(date, time(12, 0)),
                Weather.forecast_type == 'daily'
            ).first()
            
            if daily_record:
                print(f"[WEATHER] Found daily record for inactive day: precipitation={daily_record.total_precipitation}, pop={daily_record.pop}")
                result = {
                    'icon': daily_record.weather_icon,
                    'pop': daily_record.pop,
                    'precipitation': round(daily_record.total_precipitation, 2)
                }
                
                if include_details:
                    return {
                        'available': True,
                        'date': date.strftime('%Y-%m-%d'),
                        'calculation_details': {
                            'coverage_type': 'daily',
                            'data_type': 'daily',
                            'daily_used': {
                                'timestamp': daily_record.timestamp.strftime('%Y-%m-%d'),
                                'total_precipitation': daily_record.total_precipitation,
                                'pop': daily_record.pop
                            }
                        },
                        'result': result
                    }
                return result
                
            return None
        
        # Get schedule times
        start_time = getattr(schedule, f"{weekday}_start")
        end_time = getattr(schedule, f"{weekday}_end")
        
        # Create datetime objects
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)
        
        print(f"[WEATHER] Checking weather from {start_datetime} to {end_datetime}")
        
        # Calculate expected number of minutes
        duration_minutes = int((end_datetime - start_datetime).total_seconds() / 60)
        
        # First try minutely data
        minutely_records = Weather.query.filter(
            Weather.timestamp.between(start_datetime, end_datetime),
            Weather.forecast_type == 'minutely'
        ).order_by(Weather.timestamp).all()

        print(f"[WEATHER] Found {len(minutely_records)} minutely records for {duration_minutes} minutes needed")

        # If we have sufficient minutely coverage, use it
        if len(minutely_records) >= duration_minutes:
            print(f"[WEATHER] Using minutely data ({len(minutely_records)} records)")
            
            # Get hourly record for the icon
            hourly_record = Weather.query.filter(
                Weather.timestamp == start_datetime.replace(minute=0),
                Weather.forecast_type == 'hourly'
            ).first()
            
            total_precipitation = sum(record.precipitation / 60 for record in minutely_records)
            result = {
                'icon': hourly_record.weather_icon if hourly_record else None,
                'pop': max((record.pop for record in minutely_records), default=0),
                'precipitation': round(total_precipitation, 2)
            }
            
            if include_details:
                return {
                    'available': True,
                    'date': date.strftime('%Y-%m-%d'),
                    'startTime': start_time.strftime('%H:%M'),
                    'endTime': end_time.strftime('%H:%M'),
                    'calculation_details': {
                        'coverage_type': 'minutely',
                        'data_type': 'minutely',  # Add this line to match frontend expectations
                        'minutely_used': [{
                            'timestamp': record.timestamp.strftime('%H:%M'),
                            'precipitation': record.precipitation,
                            'contribution': record.precipitation / 60
                        } for record in minutely_records[:duration_minutes]]  # Only use needed records
                    },
                    'result': result
                }
            return result
        else:
            print("[WEATHER] Insufficient minutely coverage, checking hourly data")

        # Try hourly data
        print(f"[WEATHER] Checking hourly records for {date}")
        hourly_records = Weather.query.filter(
            Weather.timestamp.between(
                start_datetime.replace(minute=0),
                end_datetime.replace(minute=0) + timedelta(hours=1)
            ),
            Weather.forecast_type == 'hourly'
        ).order_by(Weather.timestamp).all()

        if not hourly_records:
            print(f"[WEATHER] No hourly records found for {date}, falling back to daily")

        if hourly_records:
            print("[WEATHER] Using hourly data")
            max_pop = 0
            total_precipitation = 0
            hourly_details = []
            
            for record in hourly_records:
                hour_start = record.timestamp
                hour_end = hour_start + timedelta(hours=1)
                
                # Only process if there's a valid overlap
                if hour_end > start_datetime and hour_start < end_datetime:
                    overlap_start = max(start_datetime, hour_start)
                    overlap_end = min(end_datetime, hour_end)
                    
                    # Calculate overlap only if end time is greater than start
                    if overlap_end > overlap_start:
                        overlap_minutes = int((overlap_end - overlap_start).total_seconds() / 60)
                        
                        contribution = 0
                        if record.total_precipitation:
                            contribution = record.total_precipitation * (overlap_minutes / 60)
                            total_precipitation += contribution
                        
                        if record.pop > max_pop:
                            max_pop = record.pop
                        
                        hourly_details.append({
                            'timestamp': record.timestamp.strftime('%H:%M'),
                            'total_precipitation': record.total_precipitation,
                            'overlap_minutes': overlap_minutes,
                            'contribution': contribution
                        })

            result = {
                'icon': hourly_records[0].weather_icon,
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
                        'coverage_type': 'hourly',
                        'hourly_used': hourly_details,
                        'data_type': 'hourly'
                    },
                    'result': result
                }
            return result

        # Use daily data as fallback
        print(f"[WEATHER] Checking daily record for {date}")
        daily_record = Weather.query.filter(
            Weather.timestamp == datetime.combine(date, time(12, 0)),
            Weather.forecast_type == 'daily'
        ).first()

        if not daily_record:
            print(f"[WEATHER] No daily record found for {date}")

        if daily_record:
            print(f"[WEATHER] Found daily record: precipitation={daily_record.total_precipitation}, pop={daily_record.pop}")
            result = {
                'icon': daily_record.weather_icon,
                'pop': daily_record.pop,
                'precipitation': round(daily_record.total_precipitation, 2)
            }
            
            if include_details:
                return {
                    'available': True,
                    'date': date.strftime('%Y-%m-%d'),
                    'startTime': start_time.strftime('%H:%M'),
                    'endTime': end_time.strftime('%H:%M'),
                    'calculation_details': {
                        'coverage_type': 'daily',
                        'data_type': 'daily',
                        'daily_used': {
                            'timestamp': daily_record.timestamp.strftime('%Y-%m-%d'),
                            'total_precipitation': daily_record.total_precipitation,
                            'pop': daily_record.pop
                        }
                    },
                    'result': result
                }
            return result

        return None


