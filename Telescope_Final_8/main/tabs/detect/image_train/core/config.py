# widgets/tabs/detect/image_train/core/config.py
"""Central configuration for detection pipeline"""

import os
from pathlib import Path


class DetectionConfig:
    """Detection pipeline configuration"""
    
    def __init__(self):
        # Get the base directory (image_train folder)
        self.BASE_DIR = Path(__file__).parent.parent
        self.MODEL_DIR = self.BASE_DIR / "models"
        self.DATA_DIR = self.BASE_DIR / "data"
        self.ANNOTATED_DIR = self.DATA_DIR / "Annotated_Data"
        
        # Create directories
        for d in [self.MODEL_DIR, self.DATA_DIR, self.ANNOTATED_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        
        # YOLO Model settings
        self.YOLO_MODEL_NAME = "yolov8n_celestial.pt"
        self.YOLO_BASE_MODEL = "yolov8n.pt"
        
        # Detection thresholds
        self.CONFIDENCE_THRESHOLD = 0.5
        self.IOU_THRESHOLD = 0.45
        self.MAX_DETECTIONS = 100
        
        # HSV Color ranges
        self.COLOR_RANGES = {
            'jupiter': {
                'hue': [(0, 10), (350, 360)],
                'saturation': (50, 255),
                'value': (100, 255)
            },
            'saturn': {
                'hue': [(20, 40)],
                'saturation': (50, 200),
                'value': (150, 255)
            },
            'moon': {
                'hue': [(20, 40)],
                'saturation': (40, 180),
                'value': (120, 255)
            },
            'nebula': {
                'hue': [(0, 180)],
                'saturation': (0, 30),
                'value': (200, 255)
            },
            'mars': {
                'hue': [(0, 10), (350, 360)],
                'saturation': (100, 255),
                'value': (80, 200)
            }
        }
        
        # Star color classification
        self.STAR_COLORS = {
            'Red': {'r': (200, 255), 'g': (0, 100), 'b': (0, 100)},
            'Orange': {'r': (200, 255), 'g': (100, 180), 'b': (0, 80)},
            'Yellow': {'r': (200, 255), 'g': (180, 255), 'b': (0, 150)},
            'White': {'r': (200, 255), 'g': (200, 255), 'b': (200, 255)},
            'Blue': {'r': (0, 150), 'g': (100, 200), 'b': (200, 255)},
        }
        
        # Spectral types
        self.SPECTRAL_TYPES = {
            'O': {'temp': '>30000K', 'color': 'Blue', 'desc': 'Hottest, massive stars'},
            'B': {'temp': '10000-30000K', 'color': 'Blue-White', 'desc': 'Very hot, bright stars'},
            'A': {'temp': '7500-10000K', 'color': 'White', 'desc': 'White, strong hydrogen lines'},
            'F': {'temp': '6000-7500K', 'color': 'Yellow-White', 'desc': 'Yellow-white stars'},
            'G': {'temp': '5200-6000K', 'color': 'Yellow', 'desc': 'Yellow, like our Sun'},
            'K': {'temp': '3700-5200K', 'color': 'Orange', 'desc': 'Orange giants'},
            'M': {'temp': '<3700K', 'color': 'Red', 'desc': 'Coolest, red dwarfs'},
        }
        
        # Processing settings
        self.IMAGE_SIZE = (640, 640)
        self.PREPROCESSING = {
            'clahe_clip_limit': 2.0,
            'clahe_grid_size': (8, 8),
            'denoise_strength': 10,
            'sharpening': 1.5
        }
        
        # Performance
        self.USE_GPU = False
        self.BATCH_SIZE = 4
        self.NUM_WORKERS = 2


# Create global config instance
config = DetectionConfig()