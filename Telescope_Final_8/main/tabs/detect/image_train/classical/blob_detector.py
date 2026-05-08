# widgets/tabs/detect/image_train/classical/blob_detector.py
"""Multi-threshold blob detection"""

import cv2
import numpy as np
from typing import List, Dict


class BlobDetector:
    """Multi-threshold blob detection for various celestial objects"""
    
    def detect_blobs(self, image: np.ndarray) -> List[Dict]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        params = cv2.SimpleBlobDetector_Params()
        params.filterByArea = True
        params.minArea = 50
        params.maxArea = 5000
        params.filterByCircularity = True
        params.minCircularity = 0.5
        params.filterByConvexity = True
        params.minConvexity = 0.8
        params.filterByInertia = True
        params.minInertiaRatio = 0.5
        
        detector = cv2.SimpleBlobDetector_create(params)
        all_blobs = []
        
        for threshold in [50, 100, 150, 200]:
            _, thresh_img = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
            keypoints = detector.detect(thresh_img)
            
            for kp in keypoints:
                all_blobs.append({
                    'x': kp.pt[0],
                    'y': kp.pt[1],
                    'size': kp.size,
                    'threshold': threshold
                })
        
        return self._remove_duplicates(all_blobs)
    
    def _remove_duplicates(self, blobs: List[Dict], distance_threshold: int = 20) -> List[Dict]:
        if not blobs:
            return []
        
        unique = []
        for blob in blobs:
            is_duplicate = False
            for existing in unique:
                dist = np.sqrt((blob['x'] - existing['x'])**2 + (blob['y'] - existing['y'])**2)
                if dist < distance_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(blob)
        return unique