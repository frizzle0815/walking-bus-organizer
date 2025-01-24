from .. import WEEKDAY_MAPPING, get_current_time, get_current_date, TIMEZONE, redis_client
from ..models import db, Weather, WeatherCalculation, WalkingBus, WalkingBusSchedule
from datetime import datetime, timedelta, time
from flask import current_app as app
from sqlalchemy.dialects.postgresql import insert as pg_insert
import requests
import os
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

    def verify_weather_data_available(self, retries=3, delay=0.5):
        """Verify weather data is available in database with retry mechanism"""
        for attempt in range(retries):
            count = Weather.query.count()
            print(f"[WEATHER][VERIFY] Attempt {attempt + 1}: Found {count} records")
            if count > 0:
                return True
            time.sleep(delay)
        return False

    def update_weather(self):
        """Main function to fetch and store weather data"""
        print("[WEATHER][UPDATE] Starting weather update process")
        
        try:
            # First cleanup old records
            self.cleanup_old_records()
            self.cleanup_old_calculations()

            # Check rate limit
            can_fetch, seconds_remaining = self.can_fetch_weather()
            if not can_fetch:
                return {
                    "success": False, 
                    "message": f"Rate limit in effect. Please wait {seconds_remaining} seconds"
                }

            # Fetch new data
            data = self.fetch_weather_data()
            if not data:
                return {"success": False, "message": "No data received from weather API"}

            # Process weather data
            records_to_save = []
            print(f"[WEATHER][UPDATE] Processing new weather data")
            
            # Process minutely data
            if 'minutely' in data:
                for minute in data['minutely']:
                    local_timestamp = datetime.fromtimestamp(minute['dt'])
                    weather = Weather(
                        timestamp=local_timestamp,
                        forecast_type='minutely',
                        precipitation=minute['precipitation'],
                        pop=1.0 if minute['precipitation'] > 0 else 0.0
                    )
                    records_to_save.append(weather)
                print(f"[WEATHER][UPDATE] Processed {len(data['minutely'])} minutely records")

            # Process hourly data
            if 'hourly' in data:
                for hour in data['hourly']:
                    local_timestamp = datetime.fromtimestamp(hour['dt'])
                    weather_code = str(hour['weather'][0]['id'])
                    is_night = hour['weather'][0]['icon'].endswith('n')
                    time_of_day = "night" if is_night else "day"
                    
                    icon_name = WEATHER_ICON_MAP[time_of_day].get(
                        weather_code,
                        "clear-night" if is_night else "clear-day"
                    )

                    rain = hour.get('rain', {}).get('1h', 0)
                    snow = hour.get('snow', {}).get('1h', 0)
                    total_precipitation = rain + snow
                    pop = 0.0 if total_precipitation == 0 else hour['pop']

                    weather = Weather(
                        timestamp=local_timestamp,
                        forecast_type='hourly',
                        total_precipitation=total_precipitation,
                        pop=pop,
                        weather_icon=icon_name
                    )
                    records_to_save.append(weather)
                print(f"[WEATHER][UPDATE] Processed {len(data['hourly'])} hourly records")

            # Process daily data
            if 'daily' in data:
                for day in data['daily']:
                    local_timestamp = datetime.fromtimestamp(day['dt'])
                    weather_code = str(day['weather'][0]['id'])
                    icon_name = WEATHER_ICON_MAP['day'].get(weather_code, "clear-day")

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
                    records_to_save.append(weather)
                print(f"[WEATHER][UPDATE] Processed {len(data['daily'])} daily records")

            # Save weather records
            if records_to_save:
                print(f"[WEATHER][UPDATE] Merging {len(records_to_save)} total records")
                for record in records_to_save:
                    db.session.merge(record)
                db.session.commit()
                
                # Verify database state
                if self.verify_weather_data_available():
                    self._verify_database_state()
                    self.update_last_fetch_time()
                    return {"success": True, "message": "Weather data updated successfully"}
                return {"success": False, "message": "Weather data verification failed"}

            return {"success": False, "message": "No weather records to save"}

        except Exception as e:
            print(f"[WEATHER][UPDATE] Error during update: {str(e)}")
            db.session.rollback()
            return {"success": False, "message": f"Error during update: {str(e)}"}

    def update_weather_calculations(self):
        """Process and update weather calculations for all walking buses"""
        try:
            calculations_to_save = []
            buses = WalkingBus.query.all()
            
            print("[WEATHER][CALC] Starting calculations update")
            
            for bus in buses:
                schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=bus.id).first()
                current_date = get_current_date()
                
                for i in range(6):
                    target_date = current_date + timedelta(days=i)
                    weather_data = self.get_weather_for_timeframe(target_date, schedule, include_details=True)
                    
                    if weather_data:
                        calc = WeatherCalculation(
                            walking_bus_id=bus.id,
                            date=target_date,
                            icon=weather_data['result']['icon'],
                            precipitation=weather_data['result']['precipitation'],
                            pop=weather_data['result']['pop'],
                            calculation_type=weather_data['calculation_details']['coverage_type'],
                            last_updated=get_current_time()
                        )
                        calculations_to_save.append(calc)

            if calculations_to_save:
                print(f"[WEATHER][CALC] Updating {len(calculations_to_save)} weather calculations")
                for calc in calculations_to_save:
                    stmt = pg_insert(WeatherCalculation).values(
                        walking_bus_id=calc.walking_bus_id,
                        date=calc.date,
                        icon=calc.icon,
                        precipitation=calc.precipitation,
                        pop=calc.pop,
                        calculation_type=calc.calculation_type,
                        last_updated=calc.last_updated
                    ).on_conflict_do_update(
                        index_elements=['walking_bus_id', 'date'],
                        set_=dict(
                            icon=calc.icon,
                            precipitation=calc.precipitation,
                            pop=calc.pop,
                            calculation_type=calc.calculation_type,
                            last_updated=calc.last_updated
                        )
                    )
                    db.session.execute(stmt)
                
                db.session.commit()
                self._verify_calculations_state()
                return {"success": True, "message": "Calculations updated successfully"}
                
            return {"success": False, "message": "No calculations to update"}

        except Exception as e:
            print(f"[WEATHER][CALC] Error updating calculations: {str(e)}")
            db.session.rollback()
            return {"success": False, "message": f"Error updating calculations: {str(e)}"}

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

    def process_minutely(self, minutely_data):
        records = []
        print(f"[WEATHER][MINUTELY] Processing {len(minutely_data)} records")
        
        updated = 0
        created = 0
        for minute in minutely_data:
            local_timestamp = datetime.fromtimestamp(minute['dt'])
            
            # Suche existierenden Eintrag
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'minutely'
            ).first()
            
            if existing:
                # Update existierenden Eintrag
                existing.precipitation = minute['precipitation']
                existing.pop = 1.0 if minute['precipitation'] > 0 else 0.0
                updated += 1
            else:
                # Erstelle neuen Eintrag
                weather = Weather(
                    timestamp=local_timestamp,
                    forecast_type='minutely',
                    precipitation=minute['precipitation'],
                    pop=1.0 if minute['precipitation'] > 0 else 0.0
                )
                records.append(weather)
                created += 1

        print(f"[WEATHER][MINUTELY] Completed: {created} created, {updated} updated")
        return records

    def process_hourly(self, hourly_data):
        records = []
        app.logger.info(f"[WEATHER][HOURLY] Processing {len(hourly_data)} records")
        
        skipped = 0
        for hour in hourly_data:
            local_timestamp = datetime.fromtimestamp(hour['dt'])
            
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'hourly'
            ).first()
            
            if existing:
                skipped += 1
                continue

            weather_code = str(hour['weather'][0]['id'])
            is_night = hour['weather'][0]['icon'].endswith('n')
            time_of_day = "night" if is_night else "day"
            
            icon_name = WEATHER_ICON_MAP[time_of_day].get(
                weather_code,
                "clear-night" if is_night else "clear-day"
            )

            rain = hour.get('rain', {}).get('1h', 0)
            snow = hour.get('snow', {}).get('1h', 0)
            total_precipitation = rain + snow
            pop = 0.0 if total_precipitation == 0 else hour['pop']

            weather = Weather(
                timestamp=local_timestamp,
                forecast_type='hourly',
                total_precipitation=total_precipitation,
                pop=pop,
                weather_icon=icon_name
            )
            records.append(weather)

        app.logger.info(f"[WEATHER][HOURLY] Completed: {len(records)} created, {skipped} skipped")
        return records

    def process_daily(self, daily_data):
        records = []
        app.logger.info(f"[WEATHER][DAILY] Processing {len(daily_data)} records")
        
        skipped = 0
        for day in daily_data:
            local_timestamp = datetime.fromtimestamp(day['dt'])
            
            existing = Weather.query.filter(
                Weather.timestamp == local_timestamp,
                Weather.forecast_type == 'daily'
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            weather_code = str(day['weather'][0]['id'])
            icon_name = WEATHER_ICON_MAP['day'].get(weather_code, "clear-day")

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

        app.logger.info(f"[WEATHER][DAILY] Completed: {len(records)} created, {skipped} skipped")
        return records

    def cleanup_old_records(self):
        """Remove weather records older than 1 hour"""
        cutoff_time = get_current_time() - timedelta(hours=12)
        deleted_count = Weather.query.filter(Weather.timestamp < cutoff_time).delete()
        db.session.commit()
        app.logger.info(f"[WEATHER][CLEANUP] Removed {deleted_count} weather records older than {cutoff_time}")

    def cleanup_old_calculations(self):
        """Remove outdated weather calculations"""
        cutoff_date = get_current_date() - timedelta(days=1)
        deleted_count = WeatherCalculation.query.filter(
            WeatherCalculation.date < cutoff_date
        ).delete()
        db.session.commit()
        print(f"[WEATHER][CLEANUP] Removed {deleted_count} calculations older than {cutoff_date}")

    def get_weather_for_timeframe(self, date, schedule, include_details=False):
        """Calculate weather data for a specific timeframe with daily fallback"""
        weekday = WEEKDAY_MAPPING[date.weekday()]
        logger = app.logger
        logger.info(f"[WEATHER][TIMEFRAME] Processing {date.strftime('%Y-%m-%d')} ({weekday})")
        
        is_active = getattr(schedule, weekday, False)
        if not is_active:
            logger.info(f"[WEATHER][TIMEFRAME] Schedule inactive, using daily data")
            daily_record = Weather.query.filter(
                Weather.timestamp == datetime.combine(date, time(12, 0)),
                Weather.forecast_type == 'daily'
            ).first()
            
            if daily_record:
                logger.info("[WEATHER][TIMEFRAME] Found daily record for inactive day")
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

        start_time = getattr(schedule, f"{weekday}_start")
        end_time = getattr(schedule, f"{weekday}_end")
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)
        duration_minutes = int((end_datetime - start_datetime).total_seconds() / 60)

        logger.info(f"[WEATHER][TIMEFRAME] Time window: {start_datetime.strftime('%H:%M')} - {end_datetime.strftime('%H:%M')}")

        minutely_records = Weather.query.filter(
            Weather.timestamp.between(start_datetime, end_datetime),
            Weather.forecast_type == 'minutely'
        ).order_by(Weather.timestamp).all()

        if len(minutely_records) >= duration_minutes:
            logger.info(f"[WEATHER][TIMEFRAME] Using minutely data ({len(minutely_records)}/{duration_minutes} records)")
            
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
                        'data_type': 'minutely',
                        'minutely_used': [{
                            'timestamp': record.timestamp.strftime('%H:%M'),
                            'precipitation': record.precipitation,
                            'contribution': record.precipitation / 60
                        } for record in minutely_records[:duration_minutes]]
                    },
                    'result': result
                }
            return result
        else:
            logger.info("[WEATHER][TIMEFRAME] Insufficient minutely data, trying hourly")

        hourly_records = Weather.query.filter(
            Weather.timestamp.between(
                start_datetime.replace(minute=0),
                end_datetime.replace(minute=0) + timedelta(hours=1)
            ),
            Weather.forecast_type == 'hourly'
        ).order_by(Weather.timestamp).all()

        if hourly_records:
            logger.info(f"[WEATHER][TIMEFRAME] Using hourly data ({len(hourly_records)} records)")
            max_pop = 0
            total_precipitation = 0
            hourly_details = []
            
            for record in hourly_records:
                hour_start = record.timestamp
                hour_end = hour_start + timedelta(hours=1)
                
                if hour_end > start_datetime and hour_start < end_datetime:
                    overlap_start = max(start_datetime, hour_start)
                    overlap_end = min(end_datetime, hour_end)
                    
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

        logger.info("[WEATHER][TIMEFRAME] No hourly data, falling back to daily")
        daily_record = Weather.query.filter(
            Weather.timestamp == datetime.combine(date, time(12, 0)),
            Weather.forecast_type == 'daily'
        ).first()

        if daily_record:
            logger.info("[WEATHER][TIMEFRAME] Using daily data as fallback")
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

        logger.warning(f"[WEATHER][TIMEFRAME] No weather data available for {date.strftime('%Y-%m-%d')}")
        return None
