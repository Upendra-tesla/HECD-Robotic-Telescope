# widgets/tabs/detect/image_train/classical/moon_detector.py
"""Moon-specific detection using circle detection and crater analysis"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional


class MoonDetector:
    """Detect moon and estimate phase"""
    
    def __init__(self):
        self.min_radius_ratio = 0.05
        self.max_radius_ratio = 0.4
        
    def detect_moon(self, image: np.ndarray) -> Optional[Dict]:
        """
        Detect moon using Hough Circle Transform
        
        Returns:
            Dictionary with moon detection results or None
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        
        # Detect circles
        min_radius = int(height * self.min_radius_ratio)
        max_radius = int(height * self.max_radius_ratio)
        
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=height // 3,
            param1=100,
            param2=30,
            minRadius=min_radius,
            maxRadius=max_radius
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            # Take the largest circle (most likely the moon)
            best_circle = max(circles, key=lambda c: c[2])
            x, y, r = best_circle
            
            # Validate moon characteristics
            moon_roi = gray[max(0, y-r):min(height, y+r), max(0, x-r):min(width, x+r)]
            if moon_roi.size > 0:
                avg_brightness = np.mean(moon_roi)
                brightness_std = np.std(moon_roi)
                
                # Moons are bright with moderate contrast
                if avg_brightness > 100 and brightness_std < 80:
                    return {
                        'detected': True,
                        'x': x,
                        'y': y,
                        'radius': r,
                        'bbox': [x - r, y - r, 2 * r, 2 * r],
                        'avg_brightness': float(avg_brightness),
                        'confidence': min(0.95, avg_brightness / 255)
                    }
        
        return {'detected': False}
    
    def estimate_moon_phase(self, moon_roi: np.ndarray) -> Dict:
        """Estimate moon phase from ROI"""
        if moon_roi is None or moon_roi.size == 0:
            return {'phase': 'Unknown', 'confidence': 0}
        
        gray = cv2.cvtColor(moon_roi, cv2.COLOR_BGR2GRAY)
        
        # Find the illuminated portion
        _, bright_mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        # Calculate asymmetry
        h, w = bright_mask.shape
        left_half = bright_mask[:, :w//2]
        right_half = bright_mask[:, w//2:]
        
        left_bright = np.sum(left_half > 0)
        right_bright = np.sum(right_half > 0)
        total_bright = left_bright + right_bright
        
        if total_bright == 0:
            return {'phase': 'New Moon', 'illumination': 0, 'confidence': 0.7}
        
        illumination = total_bright / (h * w) * 100
        
        # Determine phase based on asymmetry
        if left_bright > right_bright * 1.5:
            phase = "Waxing" if illumination < 50 else "Waxing Gibbous"
        elif right_bright > left_bright * 1.5:
            phase = "Waning" if illumination < 50 else "Waning Gibbous"
        else:
            if illumination < 10:
                phase = "New Moon"
            elif illumination < 40:
                phase = "Crescent"
            elif illumination < 60:
                phase = "Quarter"
            elif illumination < 90:
                phase = "Gibbous"
            else:
                phase = "Full Moon"
        
        return {
            'phase': phase,
            'illumination': round(illumination, 1),
            'confidence': 0.8
        }