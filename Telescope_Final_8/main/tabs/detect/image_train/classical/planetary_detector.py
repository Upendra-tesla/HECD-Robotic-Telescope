# widgets/tabs/detect/image_train/classical/planetary_detector.py
"""Planetary feature detection (Jupiter bands, Saturn rings)"""

import cv2
import numpy as np
from typing import Dict, Tuple, List, Optional


class PlanetaryDetector:
    """Detect planets and their distinctive features"""
    
    def __init__(self):
        self.planet_colors = {
            'jupiter': {'hue_range': [(0, 10), (350, 360)], 'sat_range': (50, 255)},
            'mars': {'hue_range': [(0, 15), (350, 360)], 'sat_range': (100, 255)},
            'saturn': {'hue_range': [(20, 40)], 'sat_range': (50, 200)},
            'venus': {'hue_range': [(15, 30)], 'sat_range': (30, 150)},
        }
    
    def detect_planet(self, image: np.ndarray) -> Optional[Dict]:
        """Detect if image contains a planet"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # Detect circular objects
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1, minDist=height//4,
            param1=50, param2=20, minRadius=int(height*0.02), 
            maxRadius=int(height*0.3)
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for x, y, r in circles[:3]:  # Check top 3 circles
                # Get ROI for color analysis
                x1, y1 = max(0, x - r), max(0, y - r)
                x2, y2 = min(width, x + r), min(height, y + r)
                roi = image[y1:y2, x1:x2]
                
                if roi.size > 0:
                    # Determine planet type by color
                    planet_type = self._classify_planet_by_color(roi)
                    
                    return {
                        'detected': True,
                        'type': planet_type,
                        'x': x,
                        'y': y,
                        'radius': r,
                        'bbox': [x - r, y - r, 2 * r, 2 * r],
                        'confidence': 0.85
                    }
        
        return {'detected': False}
    
    def _classify_planet_by_color(self, roi: np.ndarray) -> str:
        """Classify planet based on average color"""
        avg_bgr = np.mean(roi, axis=(0, 1))
        b, g, r = avg_bgr
        
        # Convert to approximate HSV
        if r > g and r > b:
            if r > 200 and g < 150:
                return 'mars'
            elif r > 180:
                return 'jupiter'
        elif g > r and g > b:
            return 'saturn'
        elif b > r and b > g:
            return 'neptune'
        
        return 'planet'
    
    def detect_jupiter_bands(self, image: np.ndarray, bbox: Tuple) -> Dict:
        """Detect Jupiter's atmospheric bands"""
        x, y, w, h = [int(v) for v in bbox]
        x, y = max(0, x), max(0, y)
        w = min(w, image.shape[1] - x)
        h = min(h, image.shape[0] - y)
        
        if w <= 0 or h <= 0:
            return {'bands_detected': False, 'band_count': 0}
        
        planet_roi = image[y:y+h, x:x+w]
        
        if planet_roi.size == 0:
            return {'bands_detected': False, 'band_count': 0}
        
        gray = cv2.cvtColor(planet_roi, cv2.COLOR_BGR2GRAY)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Detect horizontal edges (bands)
        sobel_y = cv2.Sobel(enhanced, cv2.CV_64F, 0, 1, ksize=3)
        sobel_y = np.abs(sobel_y)
        
        # Project onto vertical axis
        vertical_projection = np.mean(sobel_y, axis=1)
        
        # Find peaks (bands)
        peaks = self._find_peaks(vertical_projection, np.percentile(vertical_projection, 70))
        band_count = len(peaks)
        
        return {
            'bands_detected': band_count >= 2,
            'band_count': band_count,
            'description': f"Detected {band_count} atmospheric bands" if band_count >= 2 else "No distinct bands"
        }
    
    def detect_saturn_rings(self, image: np.ndarray, bbox: Tuple) -> Dict:
        """Detect Saturn's ring system"""
        x, y, w, h = [int(v) for v in bbox]
        
        # Expand region to include potential rings
        margin = int(w * 0.5)
        x_start, y_start = max(0, x - margin), max(0, y - margin)
        x_end = min(image.shape[1], x + w + margin)
        y_end = min(image.shape[0], y + h + margin)
        
        region = image[y_start:y_end, x_start:x_end]
        if region.size == 0:
            return {'rings_detected': False}
        
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # Look for elliptical structures (rings)
        # Use Hough Circle with larger radius range to detect ring system
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1, minDist=region.shape[0]//3,
            param1=50, param2=30, minRadius=int(region.shape[0]//4),
            maxRadius=int(region.shape[0]//2)
        )
        
        rings_detected = circles is not None and len(circles[0]) >= 1
        
        # Also check for ring-like shape using edge detection
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                # Rings have moderate circularity
                if 0.3 < circularity < 0.7 and area > 500:
                    rings_detected = True
                    break
        
        return {
            'rings_detected': rings_detected,
            'description': "Ring system detected" if rings_detected else "No rings detected"
        }
    
    def _find_peaks(self, data: np.ndarray, height: float = 0) -> List[int]:
        """Find peaks in 1D array"""
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1] and data[i] > height:
                peaks.append(i)
        return peaks