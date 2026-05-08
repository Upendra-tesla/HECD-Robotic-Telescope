# widgets/tabs/detect/image_train/classical/color_detector.py
"""HSV color-based detection for celestial objects"""

import cv2
import numpy as np
from typing import Optional, Dict, List


class ColorDetector:
    """Detect celestial objects based on color signatures"""
    
    def __init__(self, config):
        self.config = config
        
        # Extended color ranges for celestial objects
        self.color_ranges = {
            'sun': {
                'hue': [(0, 30), (350, 360)],  # Yellow-orange-red
                'saturation': (50, 255),
                'value': (200, 255)
            },
            'mars': {
                'hue': [(0, 15), (350, 360)],  # Red
                'saturation': (100, 255),
                'value': (80, 200)
            },
            'jupiter': {
                'hue': [(0, 10), (350, 360)],  # Orange-brown
                'saturation': (50, 255),
                'value': (100, 255)
            },
            'saturn': {
                'hue': [(20, 40)],  # Yellow-gold
                'saturation': (50, 200),
                'value': (150, 255)
            },
            'venus': {
                'hue': [(15, 30)],  # Yellow-white
                'saturation': (30, 150),
                'value': (180, 255)
            },
            'moon': {
                'hue': [(20, 60)],  # Grayish
                'saturation': (0, 80),
                'value': (120, 255)
            },
            'nebula': {
                'hue': [(0, 180)],  # Any color, low saturation
                'saturation': (0, 50),
                'value': (200, 255)
            },
            'galaxy': {
                'hue': [(0, 180)],  # Diffuse, low saturation
                'saturation': (0, 40),
                'value': (100, 200)
            }
        }
    
    def detect_by_color(self, image: np.ndarray) -> Optional[str]:
        """
        Detect object type based on dominant color in image
        
        Returns:
            Object type string or None
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        results = []
        
        for obj_name, ranges in self.color_ranges.items():
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            
            # Apply hue ranges
            for hue_range in ranges['hue']:
                h_min, h_max = hue_range
                h_mask = cv2.inRange(
                    hsv,
                    (h_min, ranges['saturation'][0], ranges['value'][0]),
                    (h_max, ranges['saturation'][1], ranges['value'][1])
                )
                mask = cv2.bitwise_or(mask, h_mask)
            
            # Calculate coverage
            coverage = cv2.countNonZero(mask) / (image.shape[0] * image.shape[1])
            
            if coverage > 0.15:  # At least 15% of image matches color
                results.append((obj_name, coverage))
        
        if results:
            best = max(results, key=lambda x: x[1])
            return best[0]
        
        return None
    
    def get_color_signature(self, image: np.ndarray, bbox: List[int]) -> Dict:
        """Get color signature of a specific region"""
        x, y, w, h = bbox
        x, y = max(0, x), max(0, y)
        w = min(w, image.shape[1] - x)
        h = min(h, image.shape[0] - y)
        
        if w <= 0 or h <= 0:
            return {}
        
        roi = image[y:y+h, x:x+w]
        if roi.size == 0:
            return {}
        
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Calculate average HSV
        avg_h = np.mean(hsv[:, :, 0])
        avg_s = np.mean(hsv[:, :, 1])
        avg_v = np.mean(hsv[:, :, 2])
        
        return {
            'avg_hue': float(avg_h),
            'avg_saturation': float(avg_s),
            'avg_value': float(avg_v),
            'dominant_color': self._hue_to_color_name(avg_h)
        }
    
    def _hue_to_color_name(self, hue: float) -> str:
        """Convert hue value to color name"""
        if hue < 10 or hue > 350:
            return 'Red'
        elif hue < 30:
            return 'Orange'
        elif hue < 60:
            return 'Yellow'
        elif hue < 90:
            return 'Yellow-Green'
        elif hue < 150:
            return 'Green'
        elif hue < 210:
            return 'Cyan'
        elif hue < 270:
            return 'Blue'
        elif hue < 330:
            return 'Purple'
        else:
            return 'Pink'