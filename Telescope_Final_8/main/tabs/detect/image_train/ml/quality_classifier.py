# widgets/tabs/detect/image_train/ml/quality_classifier.py
"""Image quality assessment"""

import cv2
import numpy as np
from typing import Dict


class QualityClassifier:
    def classify(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        contrast = gray.std()
        noise = self._estimate_noise(gray)
        
        if laplacian_var > 500 and contrast > 50 and noise < 20:
            quality, score = "Excellent", 4
        elif laplacian_var > 200 and contrast > 30 and noise < 30:
            quality, score = "Good", 3
        elif laplacian_var > 100 and contrast > 20:
            quality, score = "Moderate", 2
        else:
            quality, score = "Poor", 1
        
        return {
            'quality': quality, 'score': score,
            'focus_score': float(laplacian_var),
            'contrast': float(contrast),
            'noise': float(noise)
        }
    
    def _estimate_noise(self, gray: np.ndarray) -> float:
        median = np.median(gray)
        mad = np.median(np.abs(gray - median))
        return mad / 0.6745