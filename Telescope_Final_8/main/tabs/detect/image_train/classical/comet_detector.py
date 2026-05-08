# widgets/tabs/detect/image_train/classical/comet_detector.py
"""Comet and tail detection using morphological operations"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List


class CometDetector:
    """Detect comets and their tails"""
    
    def __init__(self):
        self.min_comet_area = 100
        self.max_comet_area = 5000
        self.tail_angle_threshold = 30  # degrees
    
    def detect_comet(self, image: np.ndarray, bbox: Optional[Tuple] = None) -> Dict:
        """
        Detect comet in image
        
        Returns:
            Dictionary with comet detection results
        """
        if bbox:
            x, y, w, h = [int(v) for v in bbox]
            x, y = max(0, x), max(0, y)
            w = min(w, image.shape[1] - x)
            h = min(h, image.shape[0] - y)
            roi = image[y:y+h, x:x+w]
        else:
            roi = image
        
        if roi.size == 0:
            return {'comet_detected': False}
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Enhance contrast for comet detection
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Detect bright core (coma)
        _, bright_mask = cv2.threshold(enhanced, 200, 255, cv2.THRESH_BINARY)
        
        # Morphological operations to clean up
        kernel = np.ones((3, 3), np.uint8)
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel)
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours for coma
        contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return {'comet_detected': False}
        
        # Find the largest bright region (likely the coma)
        coma = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(coma)
        
        if area < self.min_comet_area or area > self.max_comet_area:
            return {'comet_detected': False}
        
        # Get coma center
        M = cv2.moments(coma)
        if M['m00'] == 0:
            return {'comet_detected': False}
        
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        
        # Detect tail
        tail_detected, tail_angle, tail_length = self._detect_tail(enhanced, (cx, cy))
        
        return {
            'comet_detected': True,
            'tail_detected': tail_detected,
            'tail_angle': tail_angle if tail_detected else None,
            'tail_length': tail_length if tail_detected else 0,
            'coma_center': (cx, cy),
            'coma_area': area,
            'description': f"Comet detected with tail" if tail_detected else "Comet detected (no visible tail)"
        }
    
    def _detect_tail(self, gray: np.ndarray, center: Tuple[int, int]) -> Tuple[bool, float, float]:
        """
        Detect comet tail by analyzing radial intensity profile
        
        Returns:
            Tuple of (tail_detected, tail_angle_degrees, tail_length_pixels)
        """
        h, w = gray.shape
        cx, cy = center
        
        # Analyze intensity in different directions
        angles = np.linspace(0, 360, 36)
        radial_profiles = []
        
        for angle in angles:
            rad = np.radians(angle)
            intensities = []
            
            # Sample along ray from center outward
            for r in range(5, min(w, h) // 2, 5):
                x = int(cx + r * np.cos(rad))
                y = int(cy + r * np.sin(rad))
                if 0 <= x < w and 0 <= y < h:
                    intensities.append(gray[y, x])
                else:
                    break
            
            if intensities:
                # Calculate intensity drop-off
                if len(intensities) > 3:
                    # Look for extended region of brightness
                    tail_candidate = any(i > 150 for i in intensities[2:])
                    avg_intensity = np.mean(intensities[:3]) if len(intensities) >= 3 else 0
                    radial_profiles.append({
                        'angle': angle,
                        'intensities': intensities,
                        'has_tail': tail_candidate and avg_intensity > 100,
                        'length': len(intensities) * 5
                    })
        
        # Find best tail candidate
        tails = [p for p in radial_profiles if p['has_tail']]
        
        if tails:
            best_tail = max(tails, key=lambda x: x['length'])
            return True, best_tail['angle'], best_tail['length']
        
        return False, 0, 0