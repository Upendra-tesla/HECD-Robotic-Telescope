# File: tabs/detect/image_train/core/model_manager.py
# UPDATED: Frozen models as safety net (Section 4.3.1 & 4.3.2)

import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    print("WARNING: ultralytics not installed. Run: pip install ultralytics")

from .config import config


class ModelManager:
    """
    Manages THREE specialized YOLO models with FROZEN safety nets:
    
    1. sun_moon_model (yolov8n_sun_moon.pt) - FROZEN, 3 classes: sun, moon, planet
    2. cosmica_model (yolov8n_cosmica.pt) - FROZEN, 4 classes: comet, galaxy, star, nebula
    3. celestial_model (yolov8n_celestial.pt) - TRAINABLE, expanded classes
    
    Thesis Section 4.3:
    - Frozen models act as safety nets that students cannot degrade
    - Trainable model can be retrained by students
    """
    
    def __init__(self, config_obj, log_callback=None):
        self.config = config_obj
        self.log_callback = log_callback
        
        # Model instances
        self.sun_moon_model = None
        self.cosmica_model = None
        self.celestial_model = None
        
        # Model paths
        self.sun_moon_path = None
        self.cosmica_path = None
        self.celestial_path = None
        
        # FROZEN model classes (Section 4.3.1 & 4.3.2)
        self.sun_moon_classes = {
            0: "sun",
            1: "moon",
            2: "planet"
        }
        
        self.cosmica_classes = {
            0: "comet",
            1: "galaxy",
            2: "star",
            3: "nebula"
        }
        
        # TRAINABLE model classes (Section 4.3.3)
        self.celestial_classes = {
            0: "sun",
            1: "moon",
            2: "planet",
            3: "galaxy",
            4: "nebula",
            5: "comet",
            6: "asteroid",
            7: "star",
            8: "clouds",
            9: "other"
        }
        
        # Track availability
        self.sun_moon_available = False
        self.cosmica_available = False
        self.celestial_available = False
        
        # Track retraining count for trainable model
        self.retraining_count = 0
        
        # Primary model priority: sun_moon (frozen) > cosmica (frozen) > celestial (trainable)
        # This ensures safety net is always available
        self.primary_model_type = "sun_moon"
        
        self._load_models()
    
    def _log(self, message: str):
        if self.log_callback:
            try:
                self.log_callback(message)
            except:
                print(message)
        else:
            print(f"[ModelManager] {message}")
    
    def _get_models_dir(self) -> Path:
        """Get the models directory path from main project folder"""
        current_file = Path(__file__).resolve()
        # Go up to main project directory
        main_dir = current_file.parent.parent.parent.parent.parent
        models_dir = main_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir
    
    def _freeze_model(self, model):
        """
        Freeze model parameters - prevents student modifications
        Thesis Section 4.3.1 & 4.3.2 - Frozen baselines as safety net
        """
        try:
            # Try to freeze parameters if model has parameters attribute
            if hasattr(model, 'model') and hasattr(model.model, 'parameters'):
                for param in model.model.parameters():
                    param.requires_grad = False
                self._log("   ❄️ Model frozen - parameters locked")
            elif hasattr(model, 'parameters'):
                for param in model.parameters():
                    param.requires_grad = False
                self._log("   ❄️ Model frozen - parameters locked")
        except Exception as e:
            self._log(f"   ⚠️ Could not freeze model: {e}")
    
    def _load_models(self):
        """Load all three specialized models with frozen safety nets"""
        if not ULTRALYTICS_AVAILABLE:
            self._log("❌ Ultralytics not installed. Run: pip install ultralytics")
            return
        
        models_dir = self._get_models_dir()
        
        # ============================================================
        # 1. FROZEN SUN/MOON MODEL (Safety net - Section 4.3.1)
        # ============================================================
        sun_moon_path = models_dir / "yolov8n_sun_moon.pt"
        
        if sun_moon_path.exists():
            try:
                self.sun_moon_model = YOLO(str(sun_moon_path))
                self.sun_moon_path = str(sun_moon_path)
                self.sun_moon_available = True
                self._log(f"✅ Loaded FROZEN Sun/Moon model: {sun_moon_path.name}")
                self._log(f"   Classes: sun, moon, planet (3 classes)")
                self._log(f"   Size: {sun_moon_path.stat().st_size / 1024 / 1024:.1f} MB")
                
                # FREEZE this model - it's a safety net
                self._freeze_model(self.sun_moon_model)
                self._log(f"   ❄️ Model FROZEN - students cannot modify")
                
            except Exception as e:
                self._log(f"⚠️ Failed to load Sun/Moon model: {e}")
        else:
            self._log(f"⚠️ Sun/Moon model not found at: {sun_moon_path}")
            self._log(f"   Please place your trained 'best.pt' as 'yolov8n_sun_moon.pt'")
        
        # ============================================================
        # 2. FROZEN COSMICA MODEL (Safety net - Section 4.3.2)
        # ============================================================
        cosmica_path = models_dir / "yolov8n_cosmica.pt"
        
        if cosmica_path.exists():
            try:
                self.cosmica_model = YOLO(str(cosmica_path))
                self.cosmica_path = str(cosmica_path)
                self.cosmica_available = True
                self._log(f"✅ Loaded FROZEN Cosmica model: {cosmica_path.name}")
                self._log(f"   Classes: comet, galaxy, star, nebula")
                self._log(f"   Size: {cosmica_path.stat().st_size / 1024 / 1024:.1f} MB")
                
                # FREEZE this model - it's a safety net
                self._freeze_model(self.cosmica_model)
                self._log(f"   ❄️ Model FROZEN - students cannot modify")
                
            except Exception as e:
                self._log(f"⚠️ Failed to load Cosmica model: {e}")
        else:
            self._log(f"ℹ️ Cosmica model not found (optional)")
        
        # ============================================================
        # 3. TRAINABLE CELESTIAL MODEL (Section 4.3.3)
        # ============================================================
        celestial_path = models_dir / "yolov8n_celestial.pt"
        
        if celestial_path.exists():
            try:
                self.celestial_model = YOLO(str(celestial_path))
                self.celestial_path = str(celestial_path)
                self.celestial_available = True
                self._log(f"✅ Loaded TRAINABLE Celestial model: {celestial_path.name}")
                self._log(f"   Classes: {len(self.celestial_classes)} classes (expanded)")
                self._log(f"   Size: {celestial_path.stat().st_size / 1024 / 1024:.1f} MB")
                self._log(f"   🌟 Model is TRAINABLE - students can retrain")
                
            except Exception as e:
                self._log(f"⚠️ Failed to load Celestial model: {e}")
        else:
            self._log(f"ℹ️ Celestial model not found - will be created during training")
        
        # Summary
        self._log("=" * 50)
        self._log("📋 MODEL SUMMARY:")
        if self.sun_moon_available:
            self._log(f"   ❄️  Gate 2A (Frozen): Sun/Moon model - 3 classes (SAFETY NET)")
        if self.cosmica_available:
            self._log(f"   ❄️  Gate 2B (Frozen): Cosmica model - 4 classes (SAFETY NET)")
        if self.celestial_available:
            self._log(f"   🌟 Gate 3 (Trainable): Celestial model - {len(self.celestial_classes)} classes")
        self._log("=" * 50)
    
    def reload_model(self) -> bool:
        """Reload all models (called after training the celestial model)"""
        self._log("🔄 Reloading all models...")
        
        self.sun_moon_model = None
        self.cosmica_model = None
        self.celestial_model = None
        self.sun_moon_available = False
        self.cosmica_available = False
        self.celestial_available = False
        
        self._load_models()
        
        # Increment retraining count if celestial model was updated
        if self.celestial_available:
            self.retraining_count += 1
            self._log(f"   🌟 Celestial model retraining count: {self.retraining_count}")
        
        return self.sun_moon_available or self.cosmica_available or self.celestial_available
    
    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        Run detection using ALL available models.
        Frozen models (Gate 2) take priority as safety nets.
        """
        all_detections = []
        
        # Run FROZEN Sun/Moon model first (highest priority safety net)
        if self.sun_moon_model:
            detections = self._run_inference(
                self.sun_moon_model, 
                image, 
                self.sun_moon_classes,
                "sun_moon"
            )
            all_detections.extend(detections)
            if detections:
                self._log(f"   ❄️ Frozen Sun/Moon model: {len(detections)} detections")
        
        # Run FROZEN Cosmica model
        if self.cosmica_model:
            detections = self._run_inference(
                self.cosmica_model, 
                image, 
                self.cosmica_classes,
                "cosmica"
            )
            all_detections.extend(detections)
            if detections:
                self._log(f"   ❄️ Frozen Cosmica model: {len(detections)} detections")
        
        # Run TRAINABLE Celestial model (if available)
        if self.celestial_model:
            detections = self._run_inference(
                self.celestial_model, 
                image, 
                self.celestial_classes,
                "celestial"
            )
            all_detections.extend(detections)
            if detections:
                self._log(f"   🌟 Trainable Celestial model: {len(detections)} detections")
        
        # Merge and sort
        all_detections = self._merge_duplicate_detections(all_detections)
        all_detections.sort(key=lambda x: x['confidence'], reverse=True)
        
        return all_detections[:self.config.MAX_DETECTIONS]
    
    def _run_inference(self, model, image: np.ndarray, class_map: Dict, model_type: str) -> List[Dict]:
        """Run inference with a specific model"""
        try:
            # Use lower confidence threshold for frozen models (they are reliable)
            conf_threshold = 0.25 if model_type in ['sun_moon', 'cosmica'] else self.config.CONFIDENCE_THRESHOLD
            
            results = model(image, verbose=False, conf=conf_threshold)
            
            detections = []
            if results and len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                
                if len(boxes) > 0:
                    xyxy = boxes.xyxy.cpu().numpy()
                    confidences = boxes.conf.cpu().numpy()
                    classes = boxes.cls.cpu().numpy().astype(int)
                    
                    for i in range(len(xyxy)):
                        x1, y1, x2, y2 = xyxy[i]
                        confidence = float(confidences[i])
                        class_id = int(classes[i])
                        
                        class_name = class_map.get(class_id, 'unknown')
                        
                        detection = {
                            'class': class_name,
                            'confidence': confidence,
                            'bbox': [float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                            'source': model_type,
                            'model_type': model_type,
                            'is_frozen': model_type in ['sun_moon', 'cosmica']
                        }
                        detections.append(detection)
            
            return detections
            
        except Exception as e:
            self._log(f"⚠️ {model_type} inference error: {e}")
            return []
    
    def _merge_duplicate_detections(self, detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
        """Merge duplicate detections"""
        if not detections:
            return []
        
        by_class = {}
        for det in detections:
            cls = det['class']
            if cls not in by_class:
                by_class[cls] = []
            by_class[cls].append(det)
        
        merged = []
        
        for cls, cls_dets in by_class.items():
            if len(cls_dets) == 1:
                merged.append(cls_dets[0])
                continue
            
            # Prefer frozen model detections (they are more reliable)
            cls_dets.sort(key=lambda x: (x.get('is_frozen', False), x['confidence']), reverse=True)
            best = cls_dets[0]
            
            keep = True
            for other in merged:
                if other['class'] == cls:
                    if self._calculate_iou(best['bbox'], other['bbox']) > iou_threshold:
                        keep = False
                        if best['confidence'] > other['confidence']:
                            other.update(best)
                        break
            
            if keep:
                merged.append(best)
        
        return merged
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate IoU between two bounding boxes"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        box1 = [x1, y1, x1 + w1, y1 + h1]
        box2 = [x2, y2, x2 + w2, y2 + h2]
        
        x_left = max(box1[0], box2[0])
        y_top = max(box1[1], box2[1])
        x_right = min(box1[2], box2[2])
        y_bottom = min(box1[3], box2[3])
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        
        iou = intersection / (area1 + area2 - intersection + 1e-6)
        return iou
    
    def get_model_info(self) -> Dict:
        """Get information about all available models"""
        return {
            'sun_moon_available': self.sun_moon_available,
            'sun_moon_frozen': True,
            'cosmica_available': self.cosmica_available,
            'cosmica_frozen': True,
            'celestial_available': self.celestial_available,
            'celestial_trainable': True,
            'primary_model': self.primary_model_type,
            'sun_moon_classes': list(self.sun_moon_classes.values()) if self.sun_moon_available else [],
            'cosmica_classes': list(self.cosmica_classes.values()) if self.cosmica_available else [],
            'celestial_classes': list(self.celestial_classes.values()) if self.celestial_available else [],
            'celestial_retraining_count': self.retraining_count
        }
    
    def is_model_trained(self) -> bool:
        """Check if any model is available"""
        return self.sun_moon_available or self.cosmica_available or self.celestial_available
    
    def get_class_count(self) -> int:
        """Get total unique classes across all models"""
        classes = set()
        if self.sun_moon_available:
            classes.update(self.sun_moon_classes.values())
        if self.cosmica_available:
            classes.update(self.cosmica_classes.values())
        if self.celestial_available:
            classes.update(self.celestial_classes.values())
        return len(classes)