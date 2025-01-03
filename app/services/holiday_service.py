import requests
from flask import current_app
from datetime import datetime, date, timedelta
from ..models import SchoolHoliday, db
import os


class HolidayService:
    def __init__(self):
        self.base_url = "https://openholidaysapi.org/"
        self.country = os.getenv('HOLIDAY_COUNTRY', 'DE')
        self.subdivision = os.getenv('HOLIDAY_SUBDIVISION', 'NW')

    def update_holiday_cache(self):
        """
        Updates holiday cache for next 12 months and cleans up old entries
        """
        today = date.today()
        first_of_month = today.replace(day=1)
        
        current_app.logger.info(f"Starting holiday cache update for {today}")
        
        # Delete all holidays from past months
        first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)
        deleted_count = SchoolHoliday.query.filter(SchoolHoliday.end_date < first_of_last_month).delete()
        current_app.logger.info(f"Deleted {deleted_count} outdated holiday entries")
        
        # Check if we need to update current data
        latest_update = db.session.query(SchoolHoliday.last_update)\
            .order_by(SchoolHoliday.last_update.desc())\
            .first()
        
        current_app.logger.info(f"Latest update was: {latest_update[0] if latest_update else 'Never'}")
            
        if latest_update and latest_update[0] == first_of_month:
            current_app.logger.info("Cache is up to date, skipping update")
            return
            
        # Clear existing future holidays
        future_deleted = SchoolHoliday.query.filter(SchoolHoliday.start_date >= today).delete()
        current_app.logger.info(f"Deleted {future_deleted} future holiday entries")
        
        # Calculate date range for API request
        start_date = today.strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=365)).strftime('%Y-%m-%d')
        
        # First: Get School Holidays
        url = f"{self.base_url}/SchoolHolidays"
        params = {
            'countryIsoCode': self.country,
            'validFrom': start_date,
            'validTo': end_date,
            'languageIsoCode': self.country,
            'subdivisionCode': f'{self.country}-{self.subdivision}'
        }
        
        current_app.logger.info(f"Requesting school holidays with params: {params}")
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            holidays = response.json()
            current_app.logger.info(f"Retrieved {len(holidays)} school holidays")
            
            for holiday in holidays:
                start = datetime.strptime(holiday['startDate'], '%Y-%m-%d').date()
                end = datetime.strptime(holiday['endDate'], '%Y-%m-%d').date()
                name = next((n['text'] for n in holiday['name'] if n['language'] == 'DE'), 'Unbekannte Ferien')
                
                if end >= today:
                    new_holiday = SchoolHoliday(
                        start_date=start,
                        end_date=end,
                        name=name,
                        last_update=first_of_month
                    )
                    db.session.add(new_holiday)
                    current_app.logger.info(f"Added school holiday: {name} ({start} to {end})")
            
            # Second: Get Public Holidays
            url = f"{self.base_url}/PublicHolidays"
            current_app.logger.info(f"Requesting public holidays with params: {params}")
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            public_holidays = response.json()
            current_app.logger.info(f"Retrieved {len(public_holidays)} public holidays")
            
            for holiday in public_holidays:
                start = datetime.strptime(holiday['startDate'], '%Y-%m-%d').date()
                end = datetime.strptime(holiday['endDate'], '%Y-%m-%d').date()
                name = next((n['text'] for n in holiday['name'] if n['language'] == 'DE'), 'Unbekannter Feiertag')
                
                # Check for overlap with existing holidays
                existing_holiday = SchoolHoliday.query\
                    .filter(SchoolHoliday.start_date <= end)\
                    .filter(SchoolHoliday.end_date >= start)\
                    .first()
                
                if not existing_holiday and end >= today:
                    new_holiday = SchoolHoliday(
                        start_date=start,
                        end_date=end,
                        name=name,
                        last_update=first_of_month
                    )
                    db.session.add(new_holiday)
                    current_app.logger.info(f"Added public holiday: {name} ({start} to {end})")
            
            db.session.commit()
            current_app.logger.info("Successfully committed all holiday updates to database")
            
        except Exception as e:
            current_app.logger.error(f"Error updating holiday cache: {str(e)}")
            db.session.rollback()
            raise

  
    def is_school_holiday(self, date):
        """
        Check if given date is during school holidays using cached data
        """
        try:
            current_app.logger.info(f"Checking holiday status for {date}")
            self.update_holiday_cache()
            
            holiday = SchoolHoliday.query\
                .filter(SchoolHoliday.start_date <= date)\
                .filter(SchoolHoliday.end_date >= date)\
                .first()
                
            if holiday:
                current_app.logger.info(f"Found holiday: {holiday.name}")
                return True, holiday.name
            
            current_app.logger.info("No holiday found for this date")
            return False, None
        except Exception as e:
            current_app.logger.error(f"Error in is_school_holiday: {str(e)}")
            return False, None
