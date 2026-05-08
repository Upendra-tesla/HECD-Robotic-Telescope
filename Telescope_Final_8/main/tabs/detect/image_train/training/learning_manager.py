# File: tabs/detect/image_train/training/learning_manager.py
# UPDATED: Complete HECD Learning Manager with Three-Student Consensus
# Thesis Section 4.7 - Student-in-the-Loop Retraining
# Equation 4.9: Consensus requires ≥ 2/3 majority

import json
import shutil
import hashlib
import random
import threading
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import deque, Counter


class ConsensusManager:
    """
    Three-student consensus mechanism for annotation verification
    Thesis Section 4.7.3 - Equation 4.9
    
    Consensus threshold: ≥ 2/3 majority
    Minimum annotations: 3 students
    """
    
    def __init__(self, consensus_ratio: float = 2/3, min_annotations: int = 3):
        self.consensus_ratio = consensus_ratio  # Equation 4.9 threshold
        self.min_annotations = min_annotations
        self.pending_consensus = {}  # image_id -> list of annotations
        self.consensus_history = []  # Track achieved consensuses
        self._lock = threading.RLock()
        
    def add_annotation(self, image_id: str, student_id: str,
                       original_prediction: Dict, corrected_class: str,
                       reasoning: str = "") -> Tuple[bool, Dict]:
        """
        Add student annotation and check for consensus (Equation 4.9)
        
        Args:
            image_id: Unique identifier for the image
            student_id: Identifier for the student providing annotation
            original_prediction: Original AI prediction dict
            corrected_class: Student's correction
            reasoning: Optional reasoning text
        
        Returns:
            (consensus_reached, consensus_info)
        """
        with self._lock:
            if image_id not in self.pending_consensus:
                self.pending_consensus[image_id] = []
            
            annotation = {
                'student_id': student_id,
                'original_prediction': original_prediction,
                'corrected_class': corrected_class,
                'reasoning': reasoning,
                'timestamp': datetime.now().isoformat()
            }
            
            self.pending_consensus[image_id].append(annotation)
            
            # Check for consensus (Equation 4.9)
            votes = {}
            for ann in self.pending_consensus[image_id]:
                votes[ann['corrected_class']] = votes.get(ann['corrected_class'], 0) + 1
            
            total = len(self.pending_consensus[image_id])
            
            if total >= self.min_annotations:
                majority_class = max(votes, key=votes.get)
                majority_ratio = votes[majority_class] / total
                
                if majority_ratio >= self.consensus_ratio:
                    # Consensus reached!
                    consensus_info = {
                        'image_id': image_id,
                        'corrected_class': majority_class,
                        'consensus_ratio': majority_ratio,
                        'total_annotators': total,
                        'vote_distribution': votes,
                        'annotations': self.pending_consensus[image_id],
                        'timestamp': datetime.now().isoformat()
                    }
                    self.consensus_history.append(consensus_info)
                    
                    # Keep only last 100 consensus records
                    if len(self.consensus_history) > 100:
                        self.consensus_history = self.consensus_history[-100:]
                    
                    # Clear pending for this image
                    del self.pending_consensus[image_id]
                    
                    return True, consensus_info
        
        return False, {}
    
    def get_pending_count(self) -> int:
        """Get number of images pending consensus"""
        with self._lock:
            return len(self.pending_consensus)
    
    def get_pending_details(self) -> Dict:
        """Get details of pending consensus items"""
        with self._lock:
            details = {}
            for image_id, annotations in self.pending_consensus.items():
                votes = Counter([a['corrected_class'] for a in annotations])
                details[image_id] = {
                    'count': len(annotations),
                    'needed': max(0, self.min_annotations - len(annotations)),
                    'current_votes': dict(votes),
                    'annotations': annotations
                }
            return details
    
    def get_consensus_stats(self) -> Dict:
        """Get statistics about consensus history"""
        with self._lock:
            if not self.consensus_history:
                return {
                    'total_consensuses': 0,
                    'avg_consensus_ratio': 0,
                    'avg_annotators': 0,
                    'class_distribution': {}
                }
            
            class_dist = Counter()
            total_ratio = 0
            total_annotators = 0
            
            for consensus in self.consensus_history:
                class_dist[consensus['corrected_class']] += 1
                total_ratio += consensus['consensus_ratio']
                total_annotators += consensus['total_annotators']
            
            return {
                'total_consensuses': len(self.consensus_history),
                'avg_consensus_ratio': total_ratio / len(self.consensus_history),
                'avg_annotators': total_annotators / len(self.consensus_history),
                'class_distribution': dict(class_dist),
                'recent_consensuses': self.consensus_history[-10:]
            }


class StreamWeightTracker:
    """
    Tracks adaptive weights for each detection stream using EMA
    Thesis Section 4.5 - Equations 4.4, 4.5, 4.6
    """
    
    def __init__(self, alpha: float = 0.3, window_size: int = 50):
        self.alpha = alpha  # EMA learning rate
        self.window_size = window_size  # Rolling window for accuracy
        
        # Stream weights
        self.weights = {
            'classical': 0.33,
            'frozen_yolo': 0.34,
            'trainable_yolo': 0.33
        }
        
        # Performance history per stream
        self.performance_history = {
            'classical': deque(maxlen=window_size),
            'frozen_yolo': deque(maxlen=window_size),
            'trainable_yolo': deque(maxlen=window_size)
        }
        
        # Weight history for visualization
        self.weight_history = {
            'classical': [],
            'frozen_yolo': [],
            'trainable_yolo': []
        }
        
        # Accuracy history
        self.accuracy_history = {
            'classical': [],
            'frozen_yolo': [],
            'trainable_yolo': []
        }
    
    def record_performance(self, stream_name: str, was_correct: bool):
        """Record performance for a stream"""
        if stream_name in self.performance_history:
            self.performance_history[stream_name].append(1 if was_correct else 0)
            self._update_weight(stream_name)
    
    def _update_weight(self, stream_name: str):
        """Update weight using EMA (Equation 4.5)"""
        perf_list = self.performance_history[stream_name]
        if len(perf_list) == 0:
            accuracy = 0.5
        else:
            accuracy = sum(perf_list) / len(perf_list)
        
        # Store accuracy history
        self.accuracy_history[stream_name].append(accuracy)
        if len(self.accuracy_history[stream_name]) > 100:
            self.accuracy_history[stream_name] = self.accuracy_history[stream_name][-100:]
        
        # EMA update: w_new = α * acc + (1-α) * w_old
        old_weight = self.weights[stream_name]
        new_weight = self.alpha * accuracy + (1 - self.alpha) * old_weight
        
        # Clamp to reasonable range
        new_weight = max(0.1, min(2.0, new_weight))
        
        self.weights[stream_name] = new_weight
        
        # Store weight history
        self.weight_history[stream_name].append(new_weight)
        if len(self.weight_history[stream_name]) > 100:
            self.weight_history[stream_name] = self.weight_history[stream_name][-100:]
        
        # Normalize all weights (Equation 4.6)
        self._normalize_weights()
    
    def _normalize_weights(self):
        """Normalize weights to sum to 1 (Equation 4.6)"""
        total = sum(self.weights.values())
        if total > 0:
            for stream in self.weights:
                self.weights[stream] /= total
    
    def get_weights(self) -> Dict[str, float]:
        """Get current normalized weights"""
        return self.weights.copy()
    
    def get_accuracy(self, stream_name: str) -> float:
        """Get current accuracy for a stream (rolling window)"""
        perf_list = self.performance_history[stream_name]
        if len(perf_list) == 0:
            return 0.5
        return sum(perf_list) / len(perf_list)
    
    def get_stream_stats(self) -> Dict:
        """Get comprehensive stream statistics"""
        return {
            stream: {
                'weight': self.weights[stream],
                'accuracy': self.get_accuracy(stream),
                'sample_count': len(self.performance_history[stream]),
                'recent_accuracy': list(self.performance_history[stream])[-20:] if self.performance_history[stream] else [],
                'weight_history': self.weight_history[stream][-20:],
                'accuracy_history': self.accuracy_history[stream][-20:]
            }
            for stream in self.weights
        }
    
    def reset(self):
        """Reset all weights to equal distribution"""
        for stream in self.weights:
            self.weights[stream] = 1.0 / len(self.weights)
            self.performance_history[stream].clear()
            self.weight_history[stream] = []
            self.accuracy_history[stream] = []
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'alpha': self.alpha,
            'window_size': self.window_size,
            'weights': self.weights.copy(),
            'performance_history': {
                stream: list(history) for stream, history in self.performance_history.items()
            },
            'weight_history': self.weight_history.copy(),
            'accuracy_history': self.accuracy_history.copy()
        }
    
    def from_dict(self, data: Dict):
        """Deserialize from dictionary"""
        self.alpha = data.get('alpha', 0.3)
        self.window_size = data.get('window_size', 50)
        self.weights = data.get('weights', {'classical': 0.33, 'frozen_yolo': 0.34, 'trainable_yolo': 0.33})
        
        # Restore performance history
        perf_history = data.get('performance_history', {})
        for stream, history in perf_history.items():
            if stream in self.performance_history:
                self.performance_history[stream] = deque(history[-self.window_size:], maxlen=self.window_size)
        
        # Restore weight history
        weight_history = data.get('weight_history', {})
        for stream, history in weight_history.items():
            if stream in self.weight_history:
                self.weight_history[stream] = history[-100:]
        
        # Restore accuracy history
        acc_history = data.get('accuracy_history', {})
        for stream, history in acc_history.items():
            if stream in self.accuracy_history:
                self.accuracy_history[stream] = history[-100:]


class LearningManager:
    """
    Learning Manager for Celestial Object Detection with HECD Architecture
    Thesis Section 4.7 - Student-in-the-Loop Retraining
    
    Manages:
    - Annotations (manual and auto from corrections)
    - Three-student consensus (Section 4.7.3)
    - Adaptive stream weights (Section 4.5)
    - Training dataset preparation
    - YOLO format conversion
    - Training statistics tracking
    """
    
    def __init__(self):
        # Get absolute paths
        self.base_dir = Path(__file__).parent.parent
        self.data_dir = self.base_dir / "data"
        self.dataset_dir = self.data_dir / "dataset"
        self.feedback_file = self.data_dir / "learning_feedback.json"
        
        self._lock = threading.RLock()
        
        # Log callback
        self._log_callback = None
        
        # CLASSES - Configured for Celestial model (10 classes)
        # Thesis Section 4.3.3
        self.classes = ["sun", "moon", "planet", "galaxy", "nebula", 
                        "comet", "asteroid", "star", "clouds", "other"]
        self.class_to_id = {cls: i for i, cls in enumerate(self.classes)}
        
        # Class colors for UI visualization
        self.class_colors = {
            "sun": (255, 100, 0),      # Orange
            "moon": (200, 200, 200),   # Light Gray
            "planet": (100, 150, 255), # Blue
            "galaxy": (200, 100, 255), # Purple
            "nebula": (255, 100, 200), # Pink
            "comet": (100, 255, 200),  # Cyan
            "asteroid": (150, 150, 150), # Gray
            "star": (255, 255, 100),   # Yellow
            "clouds": (200, 200, 200), # Light Gray
            "other": (150, 150, 150)   # Gray
        }
        
        # Emoji representation for UI
        self.class_emojis = {
            "sun": "☀️",
            "moon": "🌙",
            "planet": "🪐",
            "galaxy": "🌌",
            "nebula": "✨",
            "comet": "☄️",
            "asteroid": "💫",
            "star": "⭐",
            "clouds": "☁️",
            "other": "❓"
        }
        
        # Confidence thresholds per class
        self.class_thresholds = {
            "sun": 0.70,
            "moon": 0.70,
            "planet": 0.65,
            "galaxy": 0.60,
            "nebula": 0.60,
            "comet": 0.65,
            "asteroid": 0.60,
            "star": 0.55,
            "clouds": 0.60,
            "other": 0.50
        }
        
        # Minimum images needed per class for training
        self.min_images_per_class = 10
        
        # Initialize consensus manager (Section 4.7.3)
        self.consensus_manager = ConsensusManager(consensus_ratio=2/3, min_annotations=3)
        
        # Initialize stream weight tracker (Section 4.5)
        self.weight_tracker = StreamWeightTracker(alpha=0.3, window_size=50)
        
        # Correction history for learning
        self.correction_history = []
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Initialize feedback file
        self._init_feedback_file()
        
        # Load existing state
        self._load_state()
        
        self._log(f"✅ LearningManager initialized - HECD Architecture")
        self._log(f"   📚 Classes: {len(self.classes)} celestial object types")
        self._log(f"   👥 Three-student consensus: ≥{int(self.consensus_manager.consensus_ratio*100)}% majority")
        self._log(f"   ⚖️ Adaptive weights: α={self.weight_tracker.alpha}, window={self.weight_tracker.window_size}")
    
    def _log(self, message: str):
        """Internal logging method"""
        if self._log_callback:
            try:
                self._log_callback(message)
            except Exception as e:
                print(f"Log callback error: {e}")
        print(f"[LearningManager] {message}")
    
    def set_log_callback(self, callback):
        """Set the log callback function"""
        self._log_callback = callback
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        dirs = [
            self.dataset_dir / 'train' / 'images',
            self.dataset_dir / 'train' / 'labels',
            self.dataset_dir / 'val' / 'images',
            self.dataset_dir / 'val' / 'labels',
            self.data_dir
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        self._log(f"✅ Directory structure verified")
    
    def _init_feedback_file(self):
        """Initialize feedback JSON file if it doesn't exist"""
        if not self.feedback_file.exists():
            initial_data = {
                'pending_annotations': [],
                'correction_history': [],
                'last_training': None,
                'training_stats': {
                    'total_training_sessions': 0,
                    'total_annotations_added': 0,
                    'last_accuracy': 0.0,
                    'class_counts': {cls: 0 for cls in self.classes},
                    'model_info': {
                        'name': 'HECD Celestial Model',
                        'classes': self.classes,
                        'num_classes': len(self.classes),
                        'version': '2.0',
                        'accuracy': 0.0,
                        'last_updated': datetime.now().isoformat()
                    }
                },
                'auto_conversion_stats': {
                    'total_auto_converted': 0,
                    'total_corrections': 0,
                    'auto_conversion_history': []
                },
                'consensus_history': [],
                'stream_weights': self.weight_tracker.to_dict(),
                'adaptive_learning_enabled': True
            }
            self._write_feedback(initial_data)
            self._log("✅ Created new feedback file for HECD system")
    
    def _load_state(self):
        """Load existing state from feedback file"""
        try:
            feedback = self._read_feedback()
            
            # Load consensus history
            consensus_history = feedback.get('consensus_history', [])
            for consensus in consensus_history:
                self.consensus_manager.consensus_history.append(consensus)
            
            # Load stream weights
            stream_weights = feedback.get('stream_weights', {})
            if stream_weights:
                self.weight_tracker.from_dict(stream_weights)
            
            # Load correction history
            self.correction_history = feedback.get('correction_history', [])
            
            self._log(f"📊 Loaded state: {len(consensus_history)} consensuses, {len(self.correction_history)} corrections")
            
        except Exception as e:
            self._log(f"⚠️ Error loading state: {e}")
    
    def _save_state(self):
        """Save current state to feedback file"""
        try:
            feedback = self._read_feedback()
            
            # Save consensus history
            feedback['consensus_history'] = self.consensus_manager.consensus_history[-100:]
            
            # Save stream weights
            feedback['stream_weights'] = self.weight_tracker.to_dict()
            
            # Save correction history
            feedback['correction_history'] = self.correction_history[-1000:]
            
            # Update training stats
            if 'training_stats' in feedback:
                feedback['training_stats']['model_info']['last_updated'] = datetime.now().isoformat()
                feedback['training_stats']['model_info']['adaptive_weights'] = self.weight_tracker.get_weights()
            
            feedback['last_saved'] = datetime.now().isoformat()
            
            self._write_feedback(feedback)
            
        except Exception as e:
            self._log(f"⚠️ Error saving state: {e}")
    
    def _read_feedback(self) -> Dict:
        """Read feedback JSON file"""
        try:
            with open(self.feedback_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._log(f"Feedback file error: {e}, creating new")
            self._init_feedback_file()
            return self._read_feedback()
    
    def _write_feedback(self, data: Dict) -> bool:
        """Write feedback JSON file"""
        try:
            with open(self.feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            self._log(f"Error writing feedback: {e}")
            return False
    
    def add_annotation(self, image_path: str, class_name: str, bbox: Dict,
                      features: Optional[Dict] = None, confidence: int = 100) -> bool:
        """
        Add a manual annotation to the training queue
        
        Args:
            image_path: Path to the image file
            class_name: Class name (must be in self.classes)
            bbox: Bounding box with x_center, y_center, width, height (normalized)
            features: Optional feature dictionary
            confidence: Confidence level (0-100)
        
        Returns:
            True if successful, False if duplicate
        """
        with self._lock:
            # Validate class
            if class_name not in self.classes:
                self._log(f"⚠️ Invalid class: {class_name}. Must be one of: {self.classes}")
                return False
            
            feedback = self._read_feedback()
            
            # Check for duplicates
            for existing in feedback.get('pending_annotations', []):
                if existing.get('image_path') == image_path:
                    existing_bbox = existing.get('bbox', {})
                    if (abs(existing_bbox.get('x_center', 0) - bbox.get('x_center', 0)) < 0.1 and
                        abs(existing_bbox.get('y_center', 0) - bbox.get('y_center', 0)) < 0.1 and
                        existing.get('class_name') == class_name):
                        self._log(f"⚠️ Skipping duplicate annotation for {os.path.basename(image_path)}")
                        return False
            
            # Create annotation entry
            annotation = {
                'image_path': image_path,
                'class_name': class_name,
                'class_id': self.class_to_id[class_name],
                'bbox': bbox,
                'features': features or {},
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'from_correction': features.get('from_correction', False),
                'source': features.get('source', 'manual')
            }
            
            feedback['pending_annotations'].append(annotation)
            
            # Update statistics
            if 'training_stats' not in feedback:
                feedback['training_stats'] = {}
            feedback['training_stats']['total_annotations_added'] = feedback['training_stats'].get('total_annotations_added', 0) + 1
            
            # Update class count
            if 'class_counts' not in feedback['training_stats']:
                feedback['training_stats']['class_counts'] = {cls: 0 for cls in self.classes}
            feedback['training_stats']['class_counts'][class_name] = feedback['training_stats']['class_counts'].get(class_name, 0) + 1
            
            # Save YOLO format label
            self._save_yolo_label(image_path, class_name, bbox)
            
            # Copy image to dataset
            self._copy_image_to_dataset(image_path, class_name)
            
            total = sum(feedback['training_stats']['class_counts'].values())
            emoji = self.class_emojis.get(class_name, '📷')
            self._log(f"✅ Added annotation: {emoji} {class_name} for {os.path.basename(image_path)}")
            self._log(f"   Total annotations: {total} | Pending: {len(feedback['pending_annotations'])}")
            
            # Show class distribution
            counts = feedback['training_stats']['class_counts']
            class_summary = ", ".join([f"{self.class_emojis.get(c, c)} {counts.get(c,0)}" for c in self.classes if counts.get(c,0) > 0])
            self._log(f"   Class distribution: {class_summary}")
            
            # Save state
            self._write_feedback(feedback)
            
            return True
    
    def add_student_correction_with_consensus(self, image_id: str, student_id: str,
                                               original_prediction: Dict, corrected_class: str,
                                               reasoning: str = "") -> Tuple[bool, Dict]:
        """
        Add student correction with three-student consensus (Section 4.7.3)
        Equation 4.9: consensus requires ≥ 2/3 majority
        
        Args:
            image_id: Unique identifier for the image
            student_id: Identifier for the student
            original_prediction: Original AI prediction dict
            corrected_class: Student's correction
            reasoning: Optional reasoning text
        
        Returns:
            (consensus_reached, consensus_info)
        """
        consensus_reached, consensus_info = self.consensus_manager.add_annotation(
            image_id, student_id, original_prediction, corrected_class, reasoning
        )
        
        if consensus_reached:
            # Add to training queue
            bbox = original_prediction.get('bbox', {'x_center': 0.5, 'y_center': 0.5, 'width': 0.6, 'height': 0.6})
            self.add_annotation(
                original_prediction.get('image_path', ''),
                corrected_class,
                bbox,
                {
                    'from_consensus': True,
                    'consensus_ratio': consensus_info['consensus_ratio'],
                    'num_students': consensus_info['total_annotators'],
                    'original_prediction': original_prediction,
                    'student_ids': [a['student_id'] for a in consensus_info['annotations']]
                },
                confidence=95
            )
            
            # Update correction history
            correction_entry = {
                'image_id': image_id,
                'original_class': original_prediction.get('class', 'unknown'),
                'corrected_class': corrected_class,
                'consensus_ratio': consensus_info['consensus_ratio'],
                'num_students': consensus_info['total_annotators'],
                'timestamp': datetime.now().isoformat()
            }
            self.correction_history.append(correction_entry)
            
            # Keep only last 1000 corrections
            if len(self.correction_history) > 1000:
                self.correction_history = self.correction_history[-1000:]
            
            # Save state
            self._save_state()
            
            self._log(f"👥 Consensus reached! {consensus_info['total_annotators']} students agree on {corrected_class}")
            self._log(f"   Consensus ratio: {consensus_info['consensus_ratio']:.1%}")
            
            # Update stream weight for trainable model (corrected)
            self.weight_tracker.record_performance('trainable_yolo', was_correct=True)
        
        return consensus_reached, consensus_info
    
    def record_stream_feedback(self, stream_name: str, was_correct: bool):
        """
        Record feedback for a detection stream to update adaptive weights
        Thesis Section 4.5 - Equation 4.5
        """
        if stream_name in ['classical', 'frozen_yolo', 'trainable_yolo']:
            self.weight_tracker.record_performance(stream_name, was_correct)
            self._save_state()
            self._log(f"⚖️ Stream {stream_name} feedback: {'correct' if was_correct else 'incorrect'}")
    
    def get_stream_weights(self) -> Dict[str, float]:
        """Get current adaptive weights for all streams (Equation 4.6)"""
        return self.weight_tracker.get_weights()
    
    def get_stream_stats(self) -> Dict:
        """Get comprehensive stream statistics"""
        return self.weight_tracker.get_stream_stats()
    
    def _save_yolo_label(self, image_path: str, class_name: str, bbox: Dict):
        """
        Save annotation in YOLO format
        Format: class_id x_center y_center width height (all normalized)
        """
        class_id = self.class_to_id.get(class_name, 0)
        
        # Ensure values are within [0, 1]
        x_center = max(0.0, min(1.0, bbox.get('x_center', 0.5)))
        y_center = max(0.0, min(1.0, bbox.get('y_center', 0.5)))
        width = max(0.01, min(1.0, bbox.get('width', 0.6)))
        height = max(0.01, min(1.0, bbox.get('height', 0.6)))
        
        # YOLO format line
        label_line = f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"
        
        # Create unique filename
        hash_name = hashlib.md5(f"{image_path}{datetime.now()}".encode()).hexdigest()[:12]
        split = 'train' if random.random() < 0.8 else 'val'
        
        # Get base filename without extension
        base_name = Path(image_path).stem
        label_filename = f"{base_name}_{hash_name}.txt"
        label_path = self.dataset_dir / split / 'labels' / label_filename
        
        with open(label_path, 'w') as f:
            f.write(label_line)
        
        self._log(f"📝 Saved YOLO label: {label_filename} (class {class_id}: {class_name})")
        return label_path
    
    def _copy_image_to_dataset(self, image_path: str, class_name: str):
        """Copy image to dataset directory"""
        try:
            hash_name = hashlib.md5(f"{image_path}{datetime.now()}".encode()).hexdigest()[:12]
            split = 'train' if random.random() < 0.8 else 'val'
            
            # Preserve original extension
            img_ext = Path(image_path).suffix
            if not img_ext:
                img_ext = '.jpg'
            
            img_filename = f"{Path(image_path).stem}_{hash_name}{img_ext}"
            img_dest = self.dataset_dir / split / 'images' / img_filename
            
            if not img_dest.exists():
                shutil.copy2(image_path, str(img_dest))
                self._log(f"📸 Copied image: {img_filename} to {split}/")
        except Exception as e:
            self._log(f"Error copying image: {e}")
    
    def get_pending_count(self) -> int:
        """Get number of pending annotations"""
        feedback = self._read_feedback()
        return len(feedback.get('pending_annotations', []))
    
    def get_class_counts(self) -> Dict:
        """Get counts of annotations per class"""
        feedback = self._read_feedback()
        return feedback.get('training_stats', {}).get('class_counts', {})
    
    def get_class_count(self, class_name: str) -> int:
        """Get count for specific class"""
        counts = self.get_class_counts()
        return counts.get(class_name, 0)
    
    def get_total_annotations(self) -> int:
        """Get total number of annotations"""
        return sum(self.get_class_counts().values())
    
    def get_consensus_stats(self) -> Dict:
        """Get consensus statistics"""
        return self.consensus_manager.get_consensus_stats()
    
    def get_pending_consensus(self) -> Dict:
        """Get pending consensus details"""
        return self.consensus_manager.get_pending_details()
    
    def clear_pending(self):
        """Clear all pending annotations after training"""
        feedback = self._read_feedback()
        annotation_count = len(feedback.get('pending_annotations', []))
        feedback['pending_annotations'] = []
        feedback['last_training'] = datetime.now().isoformat()
        
        if 'training_stats' in feedback:
            feedback['training_stats']['total_training_sessions'] = feedback['training_stats'].get('total_training_sessions', 0) + 1
            if 'model_info' not in feedback['training_stats']:
                feedback['training_stats']['model_info'] = {}
            feedback['training_stats']['model_info']['last_trained'] = datetime.now().isoformat()
            feedback['training_stats']['model_info']['total_annotations'] = self.get_total_annotations()
            feedback['training_stats']['model_info']['stream_weights'] = self.get_stream_weights()
        
        self._log(f"✅ Cleared {annotation_count} pending annotations")
        self._write_feedback(feedback)
        self._save_state()
        return annotation_count
    
    def get_dataset_stats(self) -> Dict:
        """Get dataset statistics"""
        train_images = len(list((self.dataset_dir / 'train' / 'images').glob('*.*')))
        val_images = len(list((self.dataset_dir / 'val' / 'images').glob('*.*')))
        train_labels = len(list((self.dataset_dir / 'train' / 'labels').glob('*.txt')))
        val_labels = len(list((self.dataset_dir / 'val' / 'labels').glob('*.txt')))
        
        return {
            'train_images': train_images,
            'val_images': val_images,
            'train_labels': train_labels,
            'val_labels': val_labels,
            'total': train_images + val_images,
            'total_labels': train_labels + val_labels
        }
    
    def get_auto_conversion_stats(self) -> Dict:
        """Get auto-conversion statistics"""
        feedback = self._read_feedback()
        auto_stats = feedback.get('auto_conversion_stats', {})
        return {
            'total_auto_converted': auto_stats.get('total_auto_converted', 0),
            'total_corrections': auto_stats.get('total_corrections', 0),
            'total_annotations': self.get_total_annotations(),
            'auto_conversion_history': auto_stats.get('auto_conversion_history', [])[-20:]
        }
    
    def get_recent_accuracy(self) -> float:
        """Calculate recent accuracy from corrections history"""
        if not self.correction_history:
            return 0.0
        
        # Look at last 50 corrections
        recent = self.correction_history[-50:]
        if not recent:
            return 0.0
        
        # Calculate accuracy (not directly applicable to corrections)
        # For now, return stream accuracy average
        stream_stats = self.get_stream_stats()
        accuracies = [stats['accuracy'] for stats in stream_stats.values() if stats['sample_count'] > 0]
        if accuracies:
            return sum(accuracies) / len(accuracies)
        
        return 0.0
    
    def add_correction(self, image_path: str, predicted: str, correct: str, was_correct: bool):
        """Add a correction to history"""
        with self._lock:
            correction = {
                'image_path': image_path,
                'predicted': predicted,
                'correct': correct,
                'was_correct': was_correct,
                'timestamp': datetime.now().isoformat()
            }
            
            self.correction_history.append(correction)
            
            # Keep only last 1000 corrections
            if len(self.correction_history) > 1000:
                self.correction_history = self.correction_history[-1000:]
            
            # Update auto conversion stats
            feedback = self._read_feedback()
            if 'auto_conversion_stats' not in feedback:
                feedback['auto_conversion_stats'] = {'total_corrections': 0}
            feedback['auto_conversion_stats']['total_corrections'] = feedback['auto_conversion_stats'].get('total_corrections', 0) + 1
            
            self._write_feedback(feedback)
            self._save_state()
            
            if not was_correct:
                self._log(f"📝 Correction recorded: {predicted} → {correct}")
                
                # Record negative feedback for the stream that made the prediction
                # This will be called from the pipeline with the actual stream name
                
            return True
    
    def get_class_weight(self, class_name: str) -> float:
        """Get weight for class based on sample count (for balanced training)"""
        counts = self.get_class_counts()
        total = sum(counts.values())
        if total == 0 or counts.get(class_name, 0) == 0:
            return 1.0
        
        # Inverse frequency weighting to balance classes
        weight = total / (len(self.classes) * counts.get(class_name, 1))
        return min(2.0, max(0.5, weight))
    
    def get_training_summary(self) -> str:
        """Get a human-readable training summary"""
        stats = self.get_dataset_stats()
        counts = self.get_class_counts()
        total = self.get_total_annotations()
        weights = self.get_stream_weights()
        consensus_stats = self.get_consensus_stats()
        
        summary = f"""
📊 HECD System Training Summary
{'='*50}
Total Annotations: {total}
Training Images: {stats['train_images']}
Validation Images: {stats['val_images']}
Pending Annotations: {self.get_pending_count()}
Training Sessions: {self._read_feedback().get('training_stats', {}).get('total_training_sessions', 0)}

Class Distribution:
"""
        for cls in self.classes:
            count = counts.get(cls, 0)
            if count > 0:
                bar = "#" * min(count, 20)
                summary += f"  {self.class_emojis.get(cls, cls)} {cls:10s}: {bar} {count}\n"
        
        summary += f"""
🎯 Adaptive Stream Weights (Equation 4.6):
  🔬 Classical: {weights.get('classical', 0):.2f}
  ❄️ Frozen YOLO: {weights.get('frozen_yolo', 0):.2f}
  🌟 Trainable: {weights.get('trainable_yolo', 0):.2f}

👥 Three-Student Consensus (Section 4.7.3):
  Total Consensuses: {consensus_stats.get('total_consensuses', 0)}
  Avg Consensus Ratio: {consensus_stats.get('avg_consensus_ratio', 0):.1%}
  Avg Annotators: {consensus_stats.get('avg_annotators', 0):.1f}
"""
        return summary
    
    def export_dataset_info(self) -> Dict:
        """Export complete dataset information"""
        return {
            'model_type': 'hecd_celestial',
            'classes': self.classes,
            'num_classes': len(self.classes),
            'class_counts': self.get_class_counts(),
            'total_annotations': self.get_total_annotations(),
            'dataset_stats': self.get_dataset_stats(),
            'pending_count': self.get_pending_count(),
            'recent_accuracy': self.get_recent_accuracy(),
            'class_thresholds': self.class_thresholds,
            'stream_weights': self.get_stream_weights(),
            'consensus_stats': self.get_consensus_stats(),
            'last_updated': datetime.now().isoformat()
        }
    
    def has_minimum_data(self, min_per_class: int = None) -> bool:
        """Check if we have minimum required data for training"""
        if min_per_class is None:
            min_per_class = self.min_images_per_class
        
        counts = self.get_class_counts()
        for cls in self.classes:
            if counts.get(cls, 0) < min_per_class:
                self._log(f"⚠️ Insufficient data for {cls}: {counts.get(cls, 0)}/{min_per_class}")
                return False
        return True
    
    def get_missing_classes(self) -> List[str]:
        """Get list of classes with insufficient data"""
        counts = self.get_class_counts()
        return [cls for cls in self.classes if counts.get(cls, 0) < self.min_images_per_class]
    
    def get_next_training_recommendation(self) -> str:
        """Get recommendation for which class needs more data"""
        missing = self.get_missing_classes()
        if missing:
            return f"Need more images for: {', '.join([self.class_emojis.get(c, c) for c in missing])}"
        
        counts = self.get_class_counts()
        # Find class with fewest samples
        min_class = min(self.classes, key=lambda c: counts.get(c, 0))
        return f"Class with fewest samples: {self.class_emojis.get(min_class, min_class)} ({counts.get(min_class, 0)} images)"
    
    def reset(self):
        """Reset all learning data (use with caution)"""
        import shutil
        
        confirm = input("Are you sure you want to reset all learning data? (yes/no): ")
        if confirm.lower() == 'yes':
            # Clear dataset directory
            for split in ['train', 'val']:
                for subdir in ['images', 'labels']:
                    dir_path = self.dataset_dir / split / subdir
                    if dir_path.exists():
                        shutil.rmtree(dir_path)
                        dir_path.mkdir(parents=True)
            
            # Reset consensus manager
            self.consensus_manager = ConsensusManager(consensus_ratio=2/3, min_annotations=3)
            
            # Reset weight tracker
            self.weight_tracker = StreamWeightTracker(alpha=0.3, window_size=50)
            
            # Clear correction history
            self.correction_history = []
            
            # Reinitialize feedback file
            self._init_feedback_file()
            
            self._log("⚠️ All learning data has been reset!")
            return True
        return False
    
    def get_retraining_status(self) -> Dict:
        """Get detailed retraining status"""
        counts = self.get_class_counts()
        total = self.get_total_annotations()
        weights = self.get_stream_weights()
        
        status = {
            'ready_for_training': self.has_minimum_data(),
            'total_annotations': total,
            'annotations_needed': max(0, self.min_images_per_class * len(self.classes) - total),
            'class_status': {},
            'recommendation': self.get_next_training_recommendation(),
            'adaptive_weights': weights,
            'consensus_pending': self.consensus_manager.get_pending_count(),
            'total_consensuses': len(self.consensus_manager.consensus_history)
        }
        
        for cls in self.classes:
            count = counts.get(cls, 0)
            status['class_status'][cls] = {
                'count': count,
                'sufficient': count >= self.min_images_per_class,
                'emoji': self.class_emojis.get(cls, ''),
                'threshold': self.class_thresholds.get(cls, 0.7),
                'weight': self.get_class_weight(cls)
            }
        
        return status