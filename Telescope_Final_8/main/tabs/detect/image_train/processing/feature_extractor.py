# widgets/tabs/detect/image_train/processing/feature_extractor.py
"""Feature extraction helpers"""

import cv2
import numpy as np
from typing import List, Dict


class FeatureExtractor:
    @staticmethod
    def extract_star_crops(image: np.ndarray, detections: list) -> list:
        star_crops = []
        for det in detections:
            if det.get('class') == 'star' and 'bbox' in det:
                x, y, w, h = [int(v) for v in det['bbox']]
                crop = image[y:y+h, x:x+w]
                if crop.size > 0:
                    star_crops.append({'crop': crop, 'position': (x, y, w, h)})
        return star_crops
    
    @staticmethod
    def extract_galaxy_crops(image: np.ndarray, detections: list) -> list:
        galaxy_crops = []
        for det in detections:
            if det.get('class') in ['galaxy', 'nebula'] and 'bbox' in det:
                x, y, w, h = [int(v) for v in det['bbox']]
                crop = image[y:y+h, x:x+w]
                if crop.size > 0:
                    galaxy_crops.append({'crop': crop, 'position': (x, y, w, h)})
        return galaxy_crops
    
    @staticmethod
    def calculate_brightness(image: np.ndarray) -> float:
        return np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    
    @staticmethod
    def detect_saturated_stars(image: np.ndarray, threshold: int = 250) -> int:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return len([c for c in contours if cv2.contourArea(c) > 5])