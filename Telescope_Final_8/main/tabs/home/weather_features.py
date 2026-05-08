#!/usr/bin/env python3
# weather_features.py
"""
Weather Features with Corrected Moon Phase Calculation
Uses proper phase angle formula for illumination
"""

import datetime
import math
import json
import os
import sys
import numpy as np
from astropy.time import Time
from astropy.coordinates import get_body, EarthLocation, AltAz, get_sun
from astropy.coordinates import solar_system_ephemeris
import astropy.units as u
from PyQt5.QtCore import QThread, pyqtSignal


class WeatherFeatures(QThread):
    """Weather and astronomy features using Astropy"""
    
    data_updated = pyqtSignal()
    apod_updated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # Load coordinates from settings
        self.latitude = 32.0415   # Default latitude (Nanjing)
        self.longitude = 118.7878  # Default longitude (Nanjing)
        self.load_coordinates()
        
        # Set up solar system ephemeris
        solar_system_ephemeris.set('builtin')
        
        self.current_apod_data = None
        
        # Lunar cycle constant (synodic month in days)
        self.lunar_cycle = 29.53058867
        
        # Number of moon phase images (0 to 27 = 28 images)
        self.num_moon_images = 28
        
        # New moon reference dates for 2026 (UTC)
        self.new_moon_dates = [
            Time('2026-01-18T19:52:00'),
            Time('2026-02-17T12:01:00'),
            Time('2026-03-19T01:23:00'),  # March 19, 2026 at 01:23 UTC
            Time('2026-04-17T11:55:00'),
            Time('2026-05-16T22:01:00'),
            Time('2026-06-15T08:18:00'),
            Time('2026-07-14T18:55:00'),
            Time('2026-08-13T06:33:00'),
            Time('2026-09-11T17:22:00'),
            Time('2026-10-11T04:56:00'),
            Time('2026-11-09T16:38:00'),
            Time('2026-12-09T04:52:00'),
        ]
        
        print("✅ WeatherFeatures initialized with corrected moon phase calculation")
    
    def load_coordinates(self):
        """Load coordinates from settings file"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tabs_dir = os.path.dirname(current_dir)
        main_dir = os.path.dirname(tabs_dir)
        settings_file = os.path.join(main_dir, "settings.json")
        config_settings = os.path.join(main_dir, "config", "settings.json")
        
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.longitude = settings.get('longitude', self.longitude)
                    self.latitude = settings.get('latitude', self.latitude)
                    print(f"📍 Loaded coordinates from settings.json: Lat={self.latitude}, Lon={self.longitude}")
            elif os.path.exists(config_settings):
                with open(config_settings, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.longitude = settings.get('longitude', self.longitude)
                    self.latitude = settings.get('latitude', self.latitude)
                    print(f"📍 Loaded coordinates from config/settings.json: Lat={self.latitude}, Lon={self.longitude}")
            else:
                print(f"⚠️ Settings file not found, using defaults: Lat={self.latitude}, Lon={self.longitude}")
        except Exception as e:
            print(f"⚠️ Error loading coordinates: {e}")
    
    def reload_coordinates(self):
        """Reload coordinates from settings"""
        self.load_coordinates()
        return True
    
    def get_last_new_moon_date(self, current_time):
        """Find the most recent new moon date before current time"""
        last_new_moon = None
        for nm_date in self.new_moon_dates:
            if nm_date < current_time:
                last_new_moon = nm_date
            else:
                break
        return last_new_moon
    
    def calculate_phase_angle(self, sun_ra_rad, sun_dec_rad, moon_ra_rad, moon_dec_rad):
        """
        Calculate the phase angle (angle between sun and moon as seen from Earth)
        
        Phase angle formula: cos(ϕ) = sin(δs) sin(δm) + cos(δs) cos(δm) cos(αs - αm)
        where:
        - ϕ = phase angle
        - δs, δm = declination of sun and moon
        - αs, αm = right ascension of sun and moon
        
        Returns phase angle in radians (0 to π)
        """
        # Cosine of angular separation
        cos_sep = (math.sin(sun_dec_rad) * math.sin(moon_dec_rad) +
                   math.cos(sun_dec_rad) * math.cos(moon_dec_rad) *
                   math.cos(sun_ra_rad - moon_ra_rad))
        
        # Clamp to valid range [-1, 1] due to floating point errors
        cos_sep = max(-1, min(1, cos_sep))
        
        # Phase angle (angular separation)
        phase_angle = math.acos(cos_sep)
        
        return phase_angle
    
    def calculate_illumination(self, phase_angle_rad):
        """
        Calculate illuminated fraction of the moon
        
        Formula: k = (1 - cos(ϕ)) / 2
        where ϕ is the phase angle
        
        Returns illuminated fraction (0 to 1)
        """
        # Correct formula: illuminated fraction = (1 - cos(phase_angle)) / 2
        illuminated_fraction = (1 - math.cos(phase_angle_rad)) / 2
        
        # Clamp to valid range
        illuminated_fraction = max(0, min(1, illuminated_fraction))
        
        return illuminated_fraction
    
    def calculate_moon_age(self, current_time):
        """
        Calculate moon age in days since last new moon
        Using proper new moon reference dates
        """
        last_new_moon = self.get_last_new_moon_date(current_time)
        
        if last_new_moon is None:
            # Fallback: use March 19, 2026 as reference
            last_new_moon = Time('2026-03-19T01:23:00')
        
        # Calculate days since last new moon
        moon_age = (current_time - last_new_moon).to_value('day')
        
        # Ensure within lunar cycle
        moon_age = moon_age % self.lunar_cycle
        
        return moon_age
    
    def get_phase_name(self, moon_age_days):
        """
        Determine moon phase name based on age in days
        """
        if moon_age_days < 1.8:
            return "New Moon"
        elif moon_age_days < 5.5:
            return "Waxing Crescent"
        elif moon_age_days < 7.4:
            return "First Quarter"
        elif moon_age_days < 11.1:
            return "Waxing Gibbous"
        elif moon_age_days < 13.8:
            return "Full Moon"
        elif moon_age_days < 17.5:
            return "Waning Gibbous"
        elif moon_age_days < 19.5:
            return "Last Quarter"
        elif moon_age_days < 23.2:
            return "Waning Crescent"
        else:
            return "Waning Crescent"
    
    def get_moon_phase_info(self):
        """
        Calculate accurate moon phase using proper astronomical formulas
        Uses:
        - Phase angle calculation for illumination
        - New moon reference dates for age
        - 28 images (0-27) for visualization
        """
        # Current time in UTC
        now = Time.now()
        
        # Get observer location
        location = EarthLocation(lat=self.latitude*u.deg, lon=self.longitude*u.deg)
        
        # Get sun and moon positions
        sun = get_body('sun', now, location)
        moon = get_body('moon', now, location)
        
        # Extract coordinates in radians
        sun_ra_rad = sun.ra.radian
        sun_dec_rad = sun.dec.radian
        moon_ra_rad = moon.ra.radian
        moon_dec_rad = moon.dec.radian
        
        # === CALCULATE PHASE ANGLE ===
        phase_angle_rad = self.calculate_phase_angle(
            sun_ra_rad, sun_dec_rad, 
            moon_ra_rad, moon_dec_rad
        )
        
        # === CALCULATE ILLUMINATION ===
        illuminated_fraction = self.calculate_illumination(phase_angle_rad)
        illumination_percent = illuminated_fraction * 100
        
        # === CALCULATE MOON AGE ===
        moon_age = self.calculate_moon_age(now)
        
        # === DETERMINE PHASE NAME ===
        phase_name = self.get_phase_name(moon_age)
        
        # === CALCULATE IMAGE INDEX (0-27) ===
        # Each image represents ~1.0546 days (29.53 / 28)
        days_per_image = self.lunar_cycle / self.num_moon_images
        image_index = int(round(moon_age / days_per_image))
        
        # Ensure index is within valid range 0-27
        if image_index >= self.num_moon_images:
            image_index = self.num_moon_images - 1
        if image_index < 0:
            image_index = 0
        
        # Log detailed debug information
        print("\n" + "=" * 60)
        print("🌙 MOON PHASE CALCULATION (Corrected)")
        print("=" * 60)
        print(f"   Date: {now.datetime.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"   Location: {self.latitude:.4f}°, {self.longitude:.4f}°")
        print(f"\n   📐 Phase Angle: {math.degrees(phase_angle_rad):.1f}°")
        print(f"   💡 Illuminated Fraction: {illuminated_fraction:.4f}")
        print(f"   💡 Illumination: {illumination_percent:.1f}%")
        print(f"\n   ⏰ Moon Age: {moon_age:.2f} days")
        print(f"   📅 Phase: {phase_name}")
        print(f"   🖼️  Image Index: {image_index:02d} (moon_{image_index:02d}.png)")
        print(f"   📏 Days per Image: {days_per_image:.3f} days")
        print("=" * 60)
        
        return {
            'image_index': image_index,
            'phase_name': phase_name,
            'illumination': illumination_percent,
            'age_days': moon_age,
            'phase_angle_deg': round(math.degrees(phase_angle_rad), 1)
        }
    
    def get_weather_data(self):
        """Get simulated weather data"""
        import random
        conditions = ["Excellent", "Good", "Fair", "Poor"]
        temps = ["12°C", "15°C", "18°C", "21°C", "24°C"]
        humidities = ["45%", "55%", "65%", "75%", "85%"]
        
        return {
            "sky_quality": random.choice(conditions),
            "temperature": random.choice(temps),
            "humidity": random.choice(humidities)
        }
    
    def get_observation_data(self):
        """Get astronomical observation conditions using Astropy"""
        now = Time.now()
        location = EarthLocation(lat=self.latitude*u.deg, lon=self.longitude*u.deg)
        
        sun = get_sun(now)
        altaz_frame = AltAz(obstime=now, location=location)
        sun_altaz = sun.transform_to(altaz_frame)
        sun_altitude = sun_altaz.alt.degree
        
        if sun_altitude < 0:
            sun_position_text = f"{abs(sun_altitude):.1f}° below horizon"
        else:
            sun_position_text = f"{sun_altitude:.1f}° above horizon"
        
        # Sky visibility based on moon illumination
        moon_phase = self.get_moon_phase_info()
        
        if moon_phase['illumination'] < 10:
            sky_visibility = "Excellent 🌟"
        elif moon_phase['illumination'] < 50:
            sky_visibility = "Good ⭐"
        elif moon_phase['illumination'] < 90:
            sky_visibility = "Fair ☁️"
        else:
            sky_visibility = "Poor 🌕"
        
        if sun_altitude < 0 and moon_phase['illumination'] < 30:
            recommendation = "Optimal for deep sky observation"
        elif sun_altitude < 0 and moon_phase['illumination'] < 70:
            recommendation = "Good for bright targets (planets, double stars)"
        elif sun_altitude < 0:
            recommendation = "Moon bright - lunar observation recommended"
        else:
            recommendation = "Daytime - no astronomical observation"
        
        return {
            "sun_position": sun_position_text,
            "sky_visibility": sky_visibility,
            "recommendation": recommendation
        }
    
    def get_visible_planets(self):
        """Get planets currently visible using get_body"""
        now = Time.now()
        location = EarthLocation(lat=self.latitude*u.deg, lon=self.longitude*u.deg)
        altaz_frame = AltAz(obstime=now, location=location)
        
        planets = ['mercury', 'venus', 'mars', 'jupiter', 'saturn']
        visible_planets = []
        
        for planet_name in planets:
            try:
                planet = get_body(planet_name, now, location)
                planet_altaz = planet.transform_to(altaz_frame)
                if planet_altaz.alt.degree > 10:
                    visible_planets.append(planet_name.capitalize())
            except Exception as e:
                print(f"⚠️ Could not get position for {planet_name}: {e}")
                pass
        
        return visible_planets
    
    def get_planet_display_text(self, planet_name):
        """Format planet display text with emoji"""
        emojis = {
            "Mercury": "☿️", "Venus": "♀️", "Mars": "♂️", 
            "Jupiter": "♃", "Saturn": "♄"
        }
        emoji = emojis.get(planet_name, "🪐")
        return f"  {emoji} {planet_name}"
    
    def get_space_fact(self):
        """Return interesting space fact"""
        facts = [
            "🌌 The Sun contains 99.86% of the Solar System's mass",
            "📅 One day on Venus is longer than one year on Earth",
            "🌳 There are more trees on Earth than stars in the Milky Way",
            "🚀 The Great Red Spot on Jupiter is twice the size of Earth",
            "💧 Europa has a global ocean with more water than Earth",
            "⏰ Neutron stars can spin 600 times per second",
            "🌙 The Moon is moving 3.8cm away from Earth each year"
        ]
        return facts[abs(hash(datetime.datetime.now().strftime("%Y%m%d"))) % len(facts)]
    
    def get_space_tech_update(self):
        """Return space tech update based on current date"""
        updates = [
            "🔭 Hubble captures stunning new nebula image",
            "🛰️ James Webb peers into early universe",
            "🤖 Perseverance finds organic molecules on Mars",
            "🌕 Artemis program preparing for lunar return",
            "🪐 Juno reveals Jupiter's complex interior",
            "✨ Euclid maps dark matter distribution"
        ]
        return updates[datetime.datetime.now().day % len(updates)]
    
    def fetch_apod_data(self):
        """Fetch NASA APOD data"""
        self.current_apod_data = {
            "media_type": "image",
            "image_url": None,
            "thumbnail_url": None
        }
        self.apod_updated.emit(self.current_apod_data)


# Quick test function
def test_moon_phase():
    """Test the moon phase calculation for verification"""
    print("\n" + "=" * 60)
    print("TESTING MOON PHASE CALCULATION")
    print("=" * 60)
    
    features = WeatherFeatures()
    moon_info = features.get_moon_phase_info()
    
    print("\n📊 RESULTS:")
    print(f"   Phase: {moon_info['phase_name']}")
    print(f"   Illumination: {moon_info['illumination']:.1f}%")
    print(f"   Moon Age: {moon_info['age_days']:.2f} days")
    print(f"   Phase Angle: {moon_info['phase_angle_deg']:.1f}°")
    print(f"   Image Index: {moon_info['image_index']:02d}")
    
    # Verify against expected for April 26, 2026
    print("\n🔍 VERIFICATION (April 26, 2026 expected):")
    print(f"   Expected Phase: Waxing Gibbous")
    print(f"   Expected Illumination: ~72%")
    print(f"   Expected Age: ~9.5 days")
    
    return moon_info


if __name__ == "__main__":
    test_moon_phase()