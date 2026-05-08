# File: tabs/detect/image_train/training/training_worker.py

import os
import yaml
import shutil
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False


class TrainingWorker(QThread):
    """Background thread for YOLO training - Trains Celestial model with 8 classes"""
    
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, learning_manager, epochs=50, image_size=640, batch_size=8, device='cpu'):
        super().__init__()
        self.learning_manager = learning_manager
        self.epochs = epochs
        self.image_size = image_size
        self.batch_size = batch_size
        self.device = device
        self.stop_requested = False
        self._log_callback = None
    
    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)
        print(f"[TrainingWorker] {message}")
    
    def set_log_callback(self, callback):
        self._log_callback = callback
    
    def _get_models_dir(self) -> Path:
        """Get the models directory path - ABSOLUTE PATH to main/models"""
        current_file = Path(__file__).resolve()
        # training_worker.py -> training -> image_train -> detect -> tabs -> main
        main_dir = current_file.parent.parent.parent.parent.parent
        models_dir = main_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir
    
    def _find_and_copy_model(self, celestial_model_path: Path) -> bool:
        """Find the trained model in various locations and copy to models directory"""
        
        # Possible locations for the trained model
        search_paths = [
            # Standard YOLO output paths
            Path('runs/detect/celestial_model/weights/best.pt'),
            Path('runs/detect/celestial_model/weights/last.pt'),
            Path('runs/detect/train/weights/best.pt'),
            Path('runs/detect/train/weights/last.pt'),
            Path(f'runs/detect/train{self.epochs}/weights/best.pt'),
            Path(f'runs/detect/train{self.epochs}/weights/last.pt'),
        ]
        
        # Also search recursively in runs/detect
        runs_detect_dir = Path('runs/detect')
        if runs_detect_dir.exists():
            for pt_file in runs_detect_dir.rglob('*.pt'):
                if 'best' in pt_file.name or 'last' in pt_file.name:
                    if pt_file not in search_paths:
                        search_paths.append(pt_file)
        
        # Search each path
        for model_path in search_paths:
            if model_path.exists():
                self._log(f"✅ Found trained model at: {model_path}")
                shutil.copy2(str(model_path), str(celestial_model_path))
                self._log(f"✅ Copied to: {celestial_model_path}")
                self._log(f"   File size: {celestial_model_path.stat().st_size / 1024 / 1024:.1f} MB")
                return True
        
        # Last resort - find any .pt file modified recently
        runs_dir = Path('runs')
        if runs_dir.exists():
            pt_files = list(runs_dir.rglob('*.pt'))
            if pt_files:
                # Get the most recently modified .pt file
                latest_pt = max(pt_files, key=lambda f: f.stat().st_mtime)
                self._log(f"⚠️ Found alternative model at: {latest_pt}")
                shutil.copy2(str(latest_pt), str(celestial_model_path))
                self._log(f"✅ Copied alternative model to: {celestial_model_path}")
                return True
        
        return False
    
    def run(self):
        """Run training in background - Trains Celestial model (8 classes)"""
        if not ULTRALYTICS_AVAILABLE:
            self.progress_signal.emit(0, "Ultralytics not installed. Run: pip install ultralytics")
            self.finished_signal.emit(False, "")
            return
            
        try:
            # Ensure models directory exists
            models_dir = self._get_models_dir()
            self._log(f"📁 Models directory: {models_dir}")
            
            self.progress_signal.emit(5, "Preparing dataset...")
            
            # Check if we have enough annotations
            pending_count = self.learning_manager.get_pending_count()
            class_counts = self.learning_manager.get_class_counts()
            
            self._log(f"📊 Dataset status:")
            self._log(f"   Pending annotations: {pending_count}")
            self._log(f"   Class distribution: {class_counts}")
            
            # Calculate total images
            total_images = sum(class_counts.values())
            self._log(f"   Total images in dataset: {total_images}")
            
            if total_images < 5:
                self.progress_signal.emit(0, f"Need at least 5 images. Currently: {total_images}")
                self.finished_signal.emit(False, f"Insufficient data: {total_images}/5 images")
                return
            
            # Prepare YAML config with 8 classes for Celestial model
            yaml_path = self.prepare_yaml_config()
            
            self.progress_signal.emit(10, "Loading base model for Celestial training...")
            
            # Get models directory and target path
            models_dir = self._get_models_dir()
            celestial_model_path = models_dir / "yolov8n_celestial.pt"
            
            self._log(f"📁 Target model path: {celestial_model_path}")
            
            # Load existing model or start fresh
            if celestial_model_path.exists():
                try:
                    model = YOLO(str(celestial_model_path))
                    self._log("✅ Continuing training from existing Celestial model")
                except Exception as e:
                    self._log(f"⚠️ Existing model corrupted: {e}")
                    self._log("   Starting fresh...")
                    model = YOLO('yolov8n.pt')
            else:
                # Start fresh with base YOLO for Celestial training
                model = YOLO('yolov8n.pt')
                self._log("✅ Starting fresh Celestial model from YOLOv8n base")
                self._log("   Training for classes: sun, moon, planet, galaxy, nebula, comet, asteroid, star")
            
            self.progress_signal.emit(15, "Starting Celestial model training...")
            self._log(f"   Epochs: {self.epochs}")
            self._log(f"   Image size: {self.image_size}")
            self._log(f"   Batch size: {self.batch_size}")
            self._log(f"   Device: {self.device}")
            
            # Create runs directory if it doesn't exist
            runs_dir = Path('runs')
            runs_dir.mkdir(exist_ok=True)
            
            # Train model with 8 classes
            results = model.train(
                data=str(yaml_path),
                epochs=self.epochs,
                imgsz=self.image_size,
                batch=self.batch_size,
                device=self.device,
                patience=10,
                project='runs/detect',
                name='celestial_model',
                exist_ok=True,
                verbose=True,
                seed=42
            )
            
            if self.stop_requested:
                self.progress_signal.emit(100, "Training stopped by user")
                self.finished_signal.emit(False, "Training cancelled")
                return
                
            self.progress_signal.emit(90, "Saving Celestial model...")
            
            # Find and copy the trained model
            if self._find_and_copy_model(celestial_model_path):
                self.progress_signal.emit(95, f"Celestial model saved to {celestial_model_path}")
                
                # Show training metrics if available
                try:
                    if hasattr(results, 'results') and results.results:
                        metrics = results.results
                        if len(metrics) > 0:
                            best_metric = max(metrics, key=lambda x: x.get('mAP50', 0))
                            self._log(f"   Best mAP50: {best_metric.get('mAP50', 0):.3f}")
                except:
                    pass
            else:
                self._log(f"❌ ERROR: Could not find trained model file!")
                self._log(f"   Searched in runs/detect/ directory")
                self._log(f"   Runs directory contents:")
                runs_dir = Path('runs')
                if runs_dir.exists():
                    for f in runs_dir.rglob('*'):
                        if f.is_file():
                            self._log(f"      {f}")
                self.finished_signal.emit(False, "Training completed but model file not found")
                return
            
            # Clear pending annotations after successful training
            self.learning_manager.clear_pending()
            
            self.progress_signal.emit(100, "Celestial training completed successfully!")
            self.finished_signal.emit(True, str(celestial_model_path))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.progress_signal.emit(0, f"Training error: {str(e)}")
            self.finished_signal.emit(False, str(e))
    
    def prepare_yaml_config(self):
        """Prepare YAML configuration for Celestial model training (8 classes)"""
        dataset_dir = str(self.learning_manager.dataset_dir)
        
        # Verify dataset directory exists and has images
        train_images_dir = os.path.join(dataset_dir, 'train', 'images')
        val_images_dir = os.path.join(dataset_dir, 'val', 'images')
        
        train_count = len(os.listdir(train_images_dir)) if os.path.exists(train_images_dir) else 0
        val_count = len(os.listdir(val_images_dir)) if os.path.exists(val_images_dir) else 0
        
        self._log(f"📊 Dataset directories:")
        self._log(f"   Train images: {train_count}")
        self._log(f"   Val images: {val_count}")
        
        # 8 classes for Celestial model
        class_names = ['sun', 'moon', 'planet', 'galaxy', 'nebula', 'comet', 'asteroid', 'star']
        
        config = {
            'path': dataset_dir,
            'train': 'train/images',
            'val': 'val/images',
            'nc': len(class_names),
            'names': class_names
        }
        
        yaml_path = os.path.join(dataset_dir, 'dataset.yaml')
        with open(yaml_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        self._log(f"📄 Created dataset config at {yaml_path}")
        self._log(f"   Classes: {', '.join(class_names)}")
        
        return yaml_path
    
    def stop(self):
        """Request training stop"""
        self.stop_requested = True