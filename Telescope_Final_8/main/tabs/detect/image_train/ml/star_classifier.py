# widgets/tabs/detect/image_train/ml/star_classifier.py
"""Star color and spectral type classifiers"""

import cv2
import numpy as np
from typing import Dict


class StarColorClassifier:
    def __init__(self, config):
        self.config = config
    
    def classify(self, star_crop: np.ndarray) -> Dict:
        if star_crop is None or star_crop.size == 0:
            return {'color': 'Unknown', 'confidence': 0}
        
        avg_bgr = np.mean(star_crop, axis=(0, 1))
        b, g, r = avg_bgr
        
        best_match, best_score = None, 0
        for color_name, ranges in self.config.STAR_COLORS.items():
            score = 0
            if ranges['r'][0] <= r <= ranges['r'][1]:
                score += 1
            if ranges['g'][0] <= g <= ranges['g'][1]:
                score += 1
            if ranges['b'][0] <= b <= ranges['b'][1]:
                score += 1
            if score > best_score:
                best_score, best_match = score, color_name
        
        return {
            'color': best_match if best_match else 'Unknown',
            'confidence': best_score / 3.0,
            'rgb': (int(r), int(g), int(b))
        }


class StarSpectralClassifier:
    def __init__(self, config):
        self.config = config
        self._init_spectral_rules()
    
    def _init_spectral_rules(self):
        self.spectral_rules = {
            'O': (0.1, 0.3, 0.6), 'B': (0.2, 0.4, 0.4), 'A': (0.4, 0.4, 0.2),
            'F': (0.5, 0.4, 0.1), 'G': (0.6, 0.3, 0.1), 'K': (0.7, 0.2, 0.1), 'M': (0.8, 0.1, 0.1)
        }
    
    def classify(self, star_crop: np.ndarray) -> Dict:
        if star_crop is None or star_crop.size == 0:
            return {'type': 'Unknown', 'confidence': 0}
        
        avg_bgr = np.mean(star_crop, axis=(0, 1))
        b, g, r = avg_bgr
        total = r + g + b
        if total == 0:
            return {'type': 'Unknown', 'confidence': 0}
        
        r_ratio, g_ratio, b_ratio = r/total, g/total, b/total
        best_match, best_score = None, 0
        
        for spec_type, (rw, gw, bw) in self.spectral_rules.items():
            score = 1.0 - (abs(r_ratio - rw) + abs(g_ratio - gw) + abs(b_ratio - bw)) / 3
            if score > best_score:
                best_score, best_match = score, spec_type
        
        spectral_data = self.config.SPECTRAL_TYPES.get(best_match, {})
        return {
            'type': best_match if best_match else 'Unknown',
            'confidence': best_score,
            'temperature_range': spectral_data.get('temp', 'Unknown'),
            'color': spectral_data.get('color', 'Unknown'),
            'description': spectral_data.get('desc', '')
        }