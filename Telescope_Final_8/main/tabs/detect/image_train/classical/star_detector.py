# widgets/tabs/detect/image_train/classical/star_detector.py
"""Star detection using blob detection and brightness analysis"""

import cv2
import numpy as np
from typing import List, Dict, Tuple


class StarDetector:
    """Detect stars using multiple techniques"""
    
    def __init__(self):
        self.min_star_area = 3
        self.max_star_area = 100
        self.brightness_threshold = 200
        
    def detect_stars(self, image: np.ndarray) -> List[Dict]:
        """
        Detect stars in the image
        
        Returns:
            List of star detections with position, brightness, and size
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # Method 1: Simple threshold for bright spots
        _, bright_mask = cv2.threshold(gray, self.brightness_threshold, 255, cv2.THRESH_BINARY)
        
        # Method 2: Laplacian for point sources
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_norm = cv2.normalize(laplacian, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, laplacian_mask = cv2.threshold(laplacian_norm, 200, 255, cv2.THRESH_BINARY)
        
        # Combine methods
        combined_mask = cv2.bitwise_or(bright_mask, laplacian_mask)
        
        # Remove noise with morphological operations
        kernel = np.ones((3, 3), np.uint8)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        stars = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_star_area <= area <= self.max_star_area:
                # Get centroid
                M = cv2.moments(contour)
                if M['m00'] > 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    
                    # Get bounding box
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Calculate brightness (peak intensity)
                    star_roi = gray[max(0, cy-5):min(height, cy+5), max(0, cx-5):min(width, cx+5)]
                    peak_brightness = np.max(star_roi) if star_roi.size > 0 else 0
                    
                    stars.append({
                        'x': cx,
                        'y': cy,
                        'width': w,
                        'height': h,
                        'area': area,
                        'brightness': peak_brightness,
                        'bbox': [x, y, w, h]
                    })
        
        # Sort by brightness (brightest first)
        stars.sort(key=lambda s: s['brightness'], reverse=True)
        
        return stars
    
    def detect_star_field(self, image: np.ndarray, min_stars: int = 5) -> Dict:
        """Detect if the image contains a star field"""
        stars = self.detect_stars(image)
        
        return {
            'is_star_field': len(stars) >= min_stars,
            'star_count': len(stars),
            'stars': stars[:10]  # Return top 10 brightest
        }