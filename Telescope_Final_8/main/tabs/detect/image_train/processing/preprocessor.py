# widgets/tabs/detect/image_train/processing/preprocessor.py
"""Image preprocessing for astronomical images"""

import cv2
import numpy as np
from typing import Dict


class ImagePreprocessor:
    def __init__(self, config):
        self.config = config
        self.clahe = cv2.createCLAHE(
            clipLimit=config.PREPROCESSING['clahe_clip_limit'],
            tileGridSize=config.PREPROCESSING['clahe_grid_size']
        )
    
    def load_from_path(self, image_path: str) -> np.ndarray:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot load image: {image_path}")
        return image
    
    def preprocess(self, image: np.ndarray) -> np.ndarray:
        if image is None:
            return None
        
        # Denoise
        img_denoised = cv2.fastNlMeansDenoisingColored(
            image, None, self.config.PREPROCESSING['denoise_strength'], 10, 7, 21
        )
        
        # CLAHE for contrast enhancement
        lab = cv2.cvtColor(img_denoised, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        
        # Sharpening
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]) / 5.0
        return cv2.filter2D(enhanced, -1, kernel)
    
    def estimate_quality(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        contrast = gray.std()
        
        median = np.median(gray)
        mad = np.median(np.abs(gray - median))
        noise = mad / 0.6745
        
        if laplacian_var > 500 and contrast > 50 and noise < 20:
            quality = "Excellent"
        elif laplacian_var > 200 and contrast > 30 and noise < 30:
            quality = "Good"
        elif laplacian_var > 100 and contrast > 20:
            quality = "Moderate"
        else:
            quality = "Poor"
        
        return {
            'quality': quality,
            'focus_score': float(laplacian_var),
            'contrast': float(contrast),
            'noise': float(noise)
        }