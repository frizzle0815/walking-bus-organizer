import requests
import logging
from typing import Tuple, Optional

class GeocodingService:
    """Service für Geocoding von Adressen mit OpenStreetMap Nominatim"""
    
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.logger = logging.getLogger(__name__)
    
    def geocode_address(self, address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Geocodiert eine Adresse und gibt Koordinaten zurück
        
        Args:
            address: Die zu geocodierende Adresse
            
        Returns:
            Tuple von (latitude, longitude, geocoded_address) oder (None, None, None)
        """
        try:
            params = {
                'q': address,
                'format': 'json',
                'addressdetails': 1,
                'limit': 1,
                'countrycodes': 'DE'  # Beschränke auf Deutschland
            }
            
            headers = {
                'User-Agent': 'WalkingBusOrganizer/1.0 (registration-app)'
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    lat = float(result['lat'])
                    lon = float(result['lon'])
                    display_name = result.get('display_name', address)
                    
                    self.logger.info(f"Geocoding erfolgreich für '{address}': {lat}, {lon}")
                    return lat, lon, display_name
                else:
                    self.logger.warning(f"Keine Geocoding-Ergebnisse für '{address}'")
                    return None, None, None
            else:
                self.logger.error(f"Geocoding-API Fehler: {response.status_code}")
                return None, None, None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Geocoding-Request Fehler: {str(e)}")
            return None, None, None
        except Exception as e:
            self.logger.error(f"Geocoding-Fehler: {str(e)}")
            return None, None, None
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Reverse Geocoding - Koordinaten zu Adresse
        
        Args:
            lat: Breitengrad
            lon: Längengrad
            
        Returns:
            Adresse als String oder None
        """
        try:
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'WalkingBusOrganizer/1.0 (registration-app)'
            }
            
            response = requests.get(
                f"{self.base_url}/reverse",
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('display_name')
            else:
                self.logger.error(f"Reverse Geocoding-API Fehler: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Reverse Geocoding-Fehler: {str(e)}")
            return None
