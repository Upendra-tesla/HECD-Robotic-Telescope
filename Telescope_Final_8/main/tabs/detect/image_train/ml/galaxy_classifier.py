# widgets/tabs/detect/image_train/ml/galaxy_classifier.py
"""Galaxy morphology classifier"""

import cv2
import numpy as np
from typing import Dict


class GalaxyMorphologyClassifier:
    def classify(self, galaxy_crop: np.ndarray) -> Dict:
        if galaxy_crop is None or galaxy_crop.size == 0:
            return {'morphology': 'Unknown', 'confidence': 0}
        
        gray = cv2.cvtColor(galaxy_crop, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        M = cv2.moments(gray)
        if M['m00'] == 0:
            return {'morphology': 'Unknown', 'confidence': 0}
        
        cx, cy = M['m10'] / M['m00'], M['m01'] / M['m00']
        asymmetry = self._calculate_asymmetry(gray, cx, cy)
        elongation = self._calculate_elongation(gray)
        
        if asymmetry < 0.2 and elongation > 1.5:
            morphology, confidence = "Spiral", 0.85
        elif asymmetry < 0.15 and elongation < 1.3:
            morphology, confidence = "Elliptical", 0.80
        else:
            morphology, confidence = "Irregular", 0.70
        
        return {'morphology': morphology, 'confidence': confidence, 'asymmetry': asymmetry, 'elongation': elongation}
    
    def _calculate_asymmetry(self, image: np.ndarray, cx: float, cy: float) -> float:
        h, w = image.shape
        cx_int, cy_int = int(cx), int(cy)
        
        left = image[cy_int:, :cx_int] if cx_int > 0 else np.array([])
        right = image[cy_int:, cx_int:] if cx_int < w else np.array([])
        
        if left.size == 0 or right.size == 0:
            return 1.0
        
        min_h, min_w = min(left.shape[0], right.shape[0]), min(left.shape[1], right.shape[1])
        left, right = left[:min_h, :min_w], right[:min_h, :min_w]
        
        return np.mean(np.abs(left - np.fliplr(right))) / 255.0
    
    def _calculate_elongation(self, image: np.ndarray) -> float:
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 1.0
        
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        return w / h if h > 0 else 1.0