import requests
import logging
import math
import os
from typing import Tuple, Optional

class GeocodingService:
    """Service für Geocoding von Adressen mit OpenStreetMap Nominatim"""
    
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.logger = logging.getLogger(__name__)
        
        # Schul-Koordinaten und Radius aus Umgebungsvariablen
        school_coords = os.getenv('SCHOOL_COORDINATES', '52.5200,13.4050').split(',')
        self.school_lat = float(school_coords[0])
        self.school_lon = float(school_coords[1])
        self.max_radius_km = float(os.getenv('SCHOOL_RADIUS', '30'))  # Standard: 30km
    
    def geocode_address(self, address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Geocodiert eine Adresse und gibt Koordinaten zurück
        
        Args:
            address: Die zu geocodierende Adresse
            
        Returns:
            Tuple von (latitude, longitude, geocoded_address) oder (None, None, error_message)
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
                    
                    # Radius-Validierung
                    distance_km = self.calculate_distance(lat, lon, self.school_lat, self.school_lon)
                    if distance_km > self.max_radius_km:
                        error_msg = f"Die Adresse ist {distance_km:.1f}km von der Schule entfernt. Maximal erlaubt sind {self.max_radius_km}km."
                        self.logger.warning(f"Adresse '{address}' ist {distance_km:.1f}km entfernt (max. {self.max_radius_km}km)")
                        return None, None, error_msg
                    
                    self.logger.info(f"Geocoding erfolgreich für '{address}': {lat}, {lon} ({distance_km:.1f}km entfernt)")
                    return lat, lon, display_name
                else:
                    self.logger.warning(f"Keine Geocoding-Ergebnisse für '{address}'")
                    return None, None, "Adresse konnte nicht gefunden werden. Bitte überprüfen Sie die Eingabe."
            else:
                self.logger.error(f"Geocoding-API Fehler: {response.status_code}")
                return None, None, "Fehler beim Suchen der Adresse. Bitte versuchen Sie es später erneut."
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Geocoding-Request Fehler: {str(e)}")
            return None, None, "Netzwerkfehler beim Suchen der Adresse. Bitte überprüfen Sie Ihre Internetverbindung."
        except Exception as e:
            self.logger.error(f"Geocoding-Fehler: {str(e)}")
            return None, None, "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut."
    
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
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Berechnet die Entfernung zwischen zwei Koordinaten in Kilometern (Haversine-Formel)
        
        Args:
            lat1, lon1: Koordinaten Punkt 1
            lat2, lon2: Koordinaten Punkt 2
            
        Returns:
            Entfernung in Kilometern
        """
        # Radius der Erde in km
        R = 6371.0
        
        # Koordinaten in Radiant konvertieren
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine-Formel
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
