# File: tabs/detect/image_train/core/detection_pipeline.py
# HECD 3-Gate Architecture with Adaptive Weighted Voting

import os
import cv2
import json
import time
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Callable, Tuple
from collections import deque, Counter

from .config import config


class StreamPerformance:
    """
    Tracks performance for each detection stream with EMA weight update
    Thesis Section 4.5 - Adaptive weights with exponential moving average
    
    Equation 4.5: w_m^(t+1) = α · acc_m^(t) + (1-α) · w_m^(t)
    Equation 4.6: Normalize weights to sum to 1
    """
    
    def __init__(self, name: str, initial_weight: float = 1.0):
        self.name = name
        self.weight = initial_weight
        self.correct = 0
        self.incorrect = 0
        self.confusion_matrix = {}
        self.correction_patterns = []
        
        # Rolling window for recent accuracy (thesis: 50 frames)
        self.recent_performance = deque(maxlen=50)
        self.recent_accuracies = deque(maxlen=50)
        
        # EMA learning rate (thesis α = 0.3)
        self.alpha = 0.3
        
        # Track weight history for visualization
        self.weight_history = []
        self.accuracy_history = []
        
    @property
    def accuracy(self):
        """Calculate rolling accuracy (last 50 frames)"""
        total = len(self.recent_performance)
        if total == 0:
            return 0.5
        return sum(self.recent_performance) / total
    
    @property
    def adaptive_weight(self):
        """
        Calculate adaptive weight using EMA (Equation 4.5)
        w_m^(t+1) = α · acc_m^(t) + (1-α) · w_m^(t)
        """
        current_accuracy = self.accuracy
        
        # Store for history
        self.recent_accuracies.append(current_accuracy)
        
        # Apply EMA update (Equation 4.5)
        new_weight = self.alpha * current_accuracy + (1 - self.alpha) * self.weight
        
        # Clamp to reasonable range
        new_weight = max(0.1, min(2.0, new_weight))
        
        # Store history
        self.weight_history.append(new_weight)
        self.accuracy_history.append(current_accuracy)
        
        # Keep only last 100 history entries
        if len(self.weight_history) > 100:
            self.weight_history = self.weight_history[-100:]
            self.accuracy_history = self.accuracy_history[-100:]
        
        return new_weight
    
    def record_feedback(self, was_correct: bool, predicted_class: str = None, 
                        correct_class: str = None, confidence: float = 0):
        """Record feedback and update rolling window"""
        self.recent_performance.append(1 if was_correct else 0)
        
        if was_correct:
            self.correct += 1
        else:
            self.incorrect += 1
            if predicted_class and correct_class:
                key = f"{predicted_class}→{correct_class}"
                self.confusion_matrix[key] = self.confusion_matrix.get(key, 0) + 1
                
                self.correction_patterns.append({
                    'predicted': predicted_class,
                    'correct': correct_class,
                    'confidence': confidence,
                    'timestamp': time.time()
                })
                # Keep only last 100 patterns
                if len(self.correction_patterns) > 100:
                    self.correction_patterns = self.correction_patterns[-100:]
        
        # Update weight with EMA
        self.weight = self.adaptive_weight
    
    def get_correction_suggestion(self, predicted_class: str):
        """Get most common correction for a predicted class"""
        suggestions = []
        for pattern in self.correction_patterns[-30:]:
            if pattern['predicted'] == predicted_class:
                suggestions.append(pattern['correct'])
        
        if suggestions:
            most_common = Counter(suggestions).most_common(1)[0]
            return most_common[0], most_common[1]
        return None, 0
    
    def get_most_confused(self):
        """Get most common confusion pair"""
        if not self.confusion_matrix:
            return None, 0
        return max(self.confusion_matrix.items(), key=lambda x: x[1])
    
    def to_dict(self):
        return {
            'name': self.name,
            'weight': self.weight,
            'correct': self.correct,
            'incorrect': self.incorrect,
            'accuracy': self.accuracy,
            'adaptive_weight': self.adaptive_weight,
            'confusion_matrix': self.confusion_matrix,
            'correction_patterns': self.correction_patterns[-30:],
            'weight_history': self.weight_history[-20:],
            'accuracy_history': self.accuracy_history[-20:]
        }
    
    def from_dict(self, data):
        self.weight = data.get('weight', self.weight)
        self.correct = data.get('correct', 0)
        self.incorrect = data.get('incorrect', 0)
        self.confusion_matrix = data.get('confusion_matrix', {})
        self.correction_patterns = data.get('correction_patterns', [])
        self.weight_history = data.get('weight_history', [])
        self.accuracy_history = data.get('accuracy_history', [])


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
        
    def add_annotation(self, image_id: str, student_id: str,
                       original_prediction: Dict, corrected_class: str,
                       reasoning: str = "") -> Tuple[bool, Dict]:
        """
        Add annotation and check for consensus (Equation 4.9)
        
        Returns: (consensus_reached, consensus_info)
        """
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
                    'annotations': self.pending_consensus[image_id],
                    'timestamp': datetime.now().isoformat()
                }
                self.consensus_history.append(consensus_info)
                
                # Clear pending for this image
                del self.pending_consensus[image_id]
                
                return True, consensus_info
        
        return False, {}
    
    def get_pending_count(self) -> int:
        """Get number of images pending consensus"""
        return len(self.pending_consensus)
    
    def get_pending_details(self) -> Dict:
        """Get details of pending consensus items"""
        details = {}
        for image_id, annotations in self.pending_consensus.items():
            details[image_id] = {
                'count': len(annotations),
                'needed': max(0, self.min_annotations - len(annotations)),
                'current_votes': Counter([a['corrected_class'] for a in annotations])
            }
        return details


class ContinuousLearningPipeline:
    """
    HECD Pipeline - Hybrid Ensemble Celestial Detection
    Thesis Section 4 - Complete architecture
    
    Three Gates:
    - Gate 1: Classical Vision (Section 4.4)
    - Gate 2: Frozen YOLO Models (Section 4.3.1 & 4.3.2) - Safety net
    - Gate 3: Trainable YOLO Model (Section 4.3.3)
    
    Fusion: Adaptive Weighted Voting with selective dominance
    """
    
    def __init__(self, learning_manager, log_callback: Optional[Callable] = None):
        self.learning_manager = learning_manager
        self.log_callback = log_callback
        self._model_manager = None
        self._image_processor = None
        self._classical_detectors = None
        
        # Gate configuration (thesis Section 4.3)
        self.GATE_1_CLASSICAL = "classical"
        self.GATE_2_FROZEN = "frozen_yolo"  # Safety net - cannot be modified
        self.GATE_3_TRAINABLE = "trainable_yolo"
        
        # COSMICA classes (Section 4.3.2 - frozen)
        self.COSMICA_CLASSES = ['comet', 'galaxy', 'star', 'nebula']
        
        # Sun/Moon classes (Section 4.3.1 - frozen)
        self.SUN_MOON_CLASSES = ['sun', 'moon']
        
        # Confidence thresholds
        self.MODEL_CONFIDENCE = {
            'celestial': 0.35,
            'cosmica': 0.30,
            'sun_moon': 0.40
        }
        
        self.CLASSICAL_MIN_CONFIDENCE = 0.50
        self.RULE_MIN_CONFIDENCE = 0.50
        
        # Initialize performance tracking for each gate (Section 4.5)
        self.stream_performance = {
            self.GATE_1_CLASSICAL: StreamPerformance(self.GATE_1_CLASSICAL, initial_weight=0.6),
            self.GATE_2_FROZEN: StreamPerformance(self.GATE_2_FROZEN, initial_weight=2.0),
            self.GATE_3_TRAINABLE: StreamPerformance(self.GATE_3_TRAINABLE, initial_weight=0.4)
        }
        
        # Custom rules from student corrections (Section 4.4.4)
        self.custom_rules = []
        self.class_thresholds = {}
        self.classical_confusions = {}
        
        # Consensus manager (Section 4.7.3)
        self.consensus_manager = ConsensusManager(consensus_ratio=2/3, min_annotations=3)
        
        # EMA learning rate (Section 4.5)
        self.alpha = 0.3
        
        # Load saved performance
        self._load_stream_performance()
        
        # Log initialization
        self._log("=" * 60)
        self._log("🎯 HECD Pipeline Initialized - 3-Gate Architecture")
        self._log("=" * 60)
        self._log("🚪 Gate 1: Classical Vision (star clustering, planetary features, comet tails)")
        self._log("🚪 Gate 2: Frozen YOLO Models (Sun/Moon + COSMICA) - SAFETY NET")
        self._log("🚪 Gate 3: Trainable YOLO Model - STUDENT RETRAINABLE")
        self._log(f"⚖️ Adaptive Weighted Voting: α={self.alpha} (Equation 4.5)")
        self._log(f"👥 Three-Student Consensus: ≥{int(self.consensus_manager.consensus_ratio*100)}% majority (Equation 4.9)")
        self._log_stream_stats()
        self._log("=" * 60)
    
    def _log(self, message: str):
        if self.log_callback:
            try:
                self.log_callback(message)
            except:
                print(message)
        else:
            print(f"[HECD] {message}")
    
    def _log_stream_stats(self):
        """Log current stream statistics"""
        for name, perf in self.stream_performance.items():
            gate_name = {
                'classical': '🔬 Gate 1 (Classical)',
                'frozen_yolo': '❄️ Gate 2 (Frozen YOLO)',
                'trainable_yolo': '🌟 Gate 3 (Trainable)'
            }.get(name, name)
            self._log(f"   {gate_name}: Acc={perf.accuracy:.1%}, Weight={perf.adaptive_weight:.2f}")
    
    def _load_stream_performance(self):
        """Load saved stream performance data"""
        try:
            perf_file = os.path.join(os.path.dirname(__file__), 'stream_performance.json')
            if os.path.exists(perf_file):
                with open(perf_file, 'r') as f:
                    data = json.load(f)
                    for name, perf_data in data.get('performance', {}).items():
                        if name in self.stream_performance:
                            self.stream_performance[name].from_dict(perf_data)
                    self.custom_rules = data.get('custom_rules', [])
                    self.class_thresholds = data.get('class_thresholds', {})
                    self._log("📊 Loaded stream performance data")
        except Exception as e:
            self._log(f"⚠️ Could not load performance data: {e}")
    
    def _save_stream_performance(self):
        """Save stream performance data"""
        try:
            perf_file = os.path.join(os.path.dirname(__file__), 'stream_performance.json')
            data = {
                'performance': {name: perf.to_dict() for name, perf in self.stream_performance.items()},
                'custom_rules': self.custom_rules[-50:],
                'class_thresholds': self.class_thresholds,
                'consensus_history': self.consensus_manager.consensus_history[-20:],
                'last_updated': datetime.now().isoformat()
            }
            with open(perf_file, 'w') as f:
                json.dump(data, f, indent=2)
            self._log("💾 Saved stream performance data")
        except Exception as e:
            self._log(f"⚠️ Could not save performance data: {e}")
    
    def _normalize_weights(self):
        """Normalize weights to sum to 1 (Equation 4.6)"""
        total = 0
        for perf in self.stream_performance.values():
            total += perf.weight
        
        if total > 0:
            for perf in self.stream_performance.values():
                perf.weight /= total
    
    def get_adaptive_weights(self) -> Dict:
        """Get current adaptive weights for all gates"""
        # Update weights using EMA (Equation 4.5)
        weights = {}
        for name, perf in self.stream_performance.items():
            weights[name] = perf.adaptive_weight
        
        # Normalize (Equation 4.6)
        total = sum(weights.values())
        if total > 0:
            for name in weights:
                weights[name] /= total
        
        return weights
    
    def get_stream_stats(self) -> Dict:
        """Get comprehensive stream statistics"""
        weights = self.get_adaptive_weights()
        return {
            name: {
                'accuracy': perf.accuracy,
                'weight': weights.get(name, perf.weight),
                'raw_weight': perf.weight,
                'correct': perf.correct,
                'incorrect': perf.incorrect,
                'total': perf.correct + perf.incorrect,
                'recent_performance': list(perf.recent_performance)[-20:],
                'weight_history': perf.weight_history[-20:],
                'accuracy_history': perf.accuracy_history[-20:]
            }
            for name, perf in self.stream_performance.items()
        }
    
    def _convert_bbox_to_dict(self, bbox, image_width=640, image_height=480) -> Dict:
        """Convert bbox from list [x, y, w, h] to dict format for YOLO"""
        if bbox is None:
            return {'x_center': 0.5, 'y_center': 0.5, 'width': 0.6, 'height': 0.6}
        
        if isinstance(bbox, dict):
            # Already in correct format, ensure values are valid
            return {
                'x_center': max(0.0, min(1.0, bbox.get('x_center', 0.5))),
                'y_center': max(0.0, min(1.0, bbox.get('y_center', 0.5))),
                'width': max(0.01, min(1.0, bbox.get('width', 0.6))),
                'height': max(0.01, min(1.0, bbox.get('height', 0.6)))
            }
        
        if isinstance(bbox, list) and len(bbox) == 4:
            x, y, w, h = bbox
            # Convert to YOLO format (center x, center y, width, height) normalized
            x_center = (x + w/2) / image_width
            y_center = (y + h/2) / image_height
            norm_w = w / image_width
            norm_h = h / image_height
            
            # Clamp to [0, 1]
            return {
                'x_center': max(0.0, min(1.0, x_center)),
                'y_center': max(0.0, min(1.0, y_center)),
                'width': max(0.01, min(1.0, norm_w)),
                'height': max(0.01, min(1.0, norm_h))
            }
        
        # Default
        return {'x_center': 0.5, 'y_center': 0.5, 'width': 0.6, 'height': 0.6}
    
    def record_feedback_with_learning(self, stream_name: str, was_correct: bool,
                                       predicted_class: str, correct_class: str = None,
                                       confidence: float = 0, image_features: Dict = None):
        """
        Record feedback and update adaptive weights (Section 4.5)
        Implements Equation 4.5: w_m^(t+1) = α · acc_m^(t) + (1-α) · w_m^(t)
        """
        stream = self.stream_performance.get(stream_name)
        if not stream:
            self._log(f"⚠️ Unknown stream: {stream_name}")
            return
        
        # Record feedback
        stream.record_feedback(was_correct, predicted_class, correct_class, confidence)
        
        # Update weights and normalize
        self._normalize_weights()
        
        # Save updated stats
        self._save_stream_performance()
        
        # Log weight update
        weights = self.get_adaptive_weights()
        self._log(f"📊 {stream_name.upper()} - Acc: {stream.accuracy:.1%}, Weight: {weights.get(stream_name, 0):.2f}")
        
        # If incorrect, try to improve the stream
        if not was_correct and correct_class and predicted_class != correct_class:
            self._improve_stream(stream_name, predicted_class, correct_class, image_features)
    
    def _improve_stream(self, stream_name: str, predicted: str, correct: str, features: Dict = None):
        """Improve stream based on correction feedback"""
        self._log(f"   🔧 Improving {stream_name} detector: {predicted} → {correct}")
        
        if stream_name == self.GATE_1_CLASSICAL:
            self._improve_classical_detector(predicted, correct, features)
        elif stream_name == self.GATE_2_FROZEN:
            self._improve_frozen_model(predicted, correct, features)
        elif stream_name == self.GATE_3_TRAINABLE:
            self._improve_trainable_model(predicted, correct, features)
    
    def _improve_classical_detector(self, predicted: str, correct: str, features: Dict):
        """Improve classical detector with rule-based learning"""
        confusion_key = f"{predicted}_to_{correct}"
        self.classical_confusions[confusion_key] = self.classical_confusions.get(confusion_key, 0) + 1
        
        # After 3 confusions, adjust threshold
        if self.classical_confusions[confusion_key] >= 3:
            if predicted == 'planet' and correct == 'nebula':
                self.CLASSICAL_MIN_CONFIDENCE = min(0.7, self.CLASSICAL_MIN_CONFIDENCE + 0.05)
                self._log(f"   📈 Increased classical min confidence to {self.CLASSICAL_MIN_CONFIDENCE:.2f}")
    
    def _improve_frozen_model(self, predicted: str, correct: str, features: Dict):
        """
        Frozen models (Gate 2) are NOT modified - they are safety nets!
        Instead, we add correction to trainable model's training queue.
        Thesis Section 4.3 - Frozen baselines remain untouched
        """
        self._log(f"   ❄️ Gate 2 (Frozen) remains unchanged - safety net preserved")
        
        # Add to trainable model's training queue instead
        if self.learning_manager and features and features.get('image_path'):
            # Get image dimensions
            img_width = features.get('image_width', 640)
            img_height = features.get('image_height', 480)
            
            # Convert bbox to dict format
            bbox_dict = self._convert_bbox_to_dict(features.get('bbox'), img_width, img_height)
            
            self.learning_manager.add_annotation(
                features.get('image_path', ''),
                correct,
                bbox_dict,
                {
                    'priority': 'high',
                    'from_correction': True,
                    'predicted_as': predicted,
                    'confidence': features.get('confidence', 80)
                },
                confidence=100
            )
            self._log(f"   📚 Added to Gate 3 training queue: {correct}")
    
    def _improve_trainable_model(self, predicted: str, correct: str, features: Dict):
        """Improve trainable model with student annotations"""
        if self.learning_manager and features and features.get('image_path'):
            # Get image dimensions
            img_width = features.get('image_width', 640)
            img_height = features.get('image_height', 480)
            
            # Convert bbox to dict format
            bbox_dict = self._convert_bbox_to_dict(features.get('bbox'), img_width, img_height)
            
            self.learning_manager.add_annotation(
                features.get('image_path', ''),
                correct,
                bbox_dict,
                {
                    'priority': 'high',
                    'from_correction': True,
                    'predicted_as': predicted,
                    'student_correction': True,
                    'confidence': features.get('confidence', 80)
                },
                confidence=100
            )
            self._log(f"   📚 Added to Gate 3 training queue: {correct}")
    
    def add_student_annotation_with_consensus(self, image_id: str, student_id: str,
                                               original_prediction: Dict, corrected_class: str,
                                               reasoning: str = "") -> Tuple[bool, Dict]:
        """
        Add student annotation with three-student consensus (Section 4.7.3)
        Equation 4.9: consensus requires ≥ 2/3 majority
        """
        consensus_reached, consensus_info = self.consensus_manager.add_annotation(
            image_id, student_id, original_prediction, corrected_class, reasoning
        )
        
        if consensus_reached:
            self._log(f"👥 Consensus reached! {len(consensus_info['annotations'])} students agree on {corrected_class}")
            
            # Add to training queue
            if self.learning_manager and consensus_info.get('image_id'):
                image_path = original_prediction.get('image_path', '')
                if image_path:
                    bbox_dict = self._convert_bbox_to_dict(original_prediction.get('bbox'))
                    self.learning_manager.add_annotation(
                        image_path,
                        corrected_class,
                        bbox_dict,
                        {
                            'from_consensus': True,
                            'consensus_ratio': consensus_info['consensus_ratio'],
                            'num_students': len(consensus_info['annotations']),
                            'original_prediction': original_prediction
                        },
                        confidence=95
                    )
                    self._log(f"   ✅ Verified annotation added to training queue")
        
        return consensus_reached, consensus_info
    
    def _get_model_manager(self):
        if self._model_manager is None:
            from .model_manager import ModelManager
            self._model_manager = ModelManager(config, self._log)
        return self._model_manager
    
    def _get_image_processor(self):
        if self._image_processor is None:
            from ..processing.preprocessor import ImagePreprocessor
            self._image_processor = ImagePreprocessor(config)
        return self._image_processor
    
    def _get_classical_detectors(self):
        if self._classical_detectors is None:
            from ..classical import (
                PlanetaryDetector, CometDetector, BlobDetector,
                ColorDetector, MoonDetector, StarDetector
            )
            self._classical_detectors = {
                'planetary': PlanetaryDetector(),
                'comet': CometDetector(),
                'blob': BlobDetector(),
                'color': ColorDetector(config),
                'moon': MoonDetector(),
                'star': StarDetector()
            }
        return self._classical_detectors
    
    def _ensure_dict_has_object(self, result: Dict, default: str = 'unknown') -> Dict:
        """Ensure dictionary has 'object' key (fix for missing key error)"""
        if result is None:
            return {'object': default, 'confidence': 0}
        if 'object' not in result:
            result['object'] = default
        if 'confidence' not in result:
            result['confidence'] = 0
        return result
    
    def detect(self, image_path: str) -> Dict:
        """
        Main detection method with 3-gate architecture and adaptive weighted voting
        Thesis Section 4 - Complete HECD pipeline
        """
        self._log(f"🔍 Starting HECD detection: {os.path.basename(image_path)}")
        
        # Load and preprocess image
        image = self._get_image_processor().load_from_path(image_path)
        if image is None:
            return {'object': 'unknown', 'confidence': 0, 'error': 'Could not read image'}
        
        preprocessed = self._get_image_processor().preprocess(image)
        quality = self._get_image_processor().estimate_quality(preprocessed)
        
        # Get image dimensions
        h, w = preprocessed.shape[:2]
        
        # ============================================================
        # RUN ALL THREE GATES (Section 4.3)
        # ============================================================
        
        # Gate 1: Classical Vision (Section 4.4)
        classical_result = self._gate1_classical_detection(preprocessed)
        classical_result = self._ensure_dict_has_object(classical_result, 'unknown')
        
        # Gate 2: Frozen YOLO Models (Section 4.3.1 & 4.3.2) - SAFETY NET
        frozen_result = self._gate2_frozen_detection(preprocessed)
        frozen_result = self._ensure_dict_has_object(frozen_result, 'unknown')
        
        # Gate 3: Trainable YOLO Model (Section 4.3.3)
        trainable_result = self._gate3_trainable_detection(preprocessed)
        trainable_result = self._ensure_dict_has_object(trainable_result, 'unknown')
        
        # Apply custom rules from learning
        rule_result = self._apply_custom_rules(preprocessed)
        rule_result = self._ensure_dict_has_object(rule_result, 'unknown')
        
        # ============================================================
        # ADAPTIVE WEIGHTED VOTING (Section 4.5)
        # Equation 4.4: class(x) = argmax_c Σ w_m · p_m(c|x)
        # ============================================================
        
        final_result = self._weighted_vote(classical_result, frozen_result, trainable_result, rule_result)
        final_result = self._ensure_dict_has_object(final_result, 'unknown')
        
        # Add specialized classifications if available
        final_result = self._add_specialized_classifications(preprocessed, final_result)
        
        # Add metadata
        final_result['image_path'] = image_path
        final_result['image_quality'] = quality
        final_result['gate_weights'] = self.get_adaptive_weights()
        final_result['image_width'] = w
        final_result['image_height'] = h
        
        # Get stream results for display
        final_result['streams'] = {
            'Classical': f"{classical_result.get('object', 'unknown')} ({classical_result.get('confidence', 0):.0%})",
            'Frozen YOLO': f"{frozen_result.get('object', 'unknown')} ({frozen_result.get('confidence', 0):.0%})",
            'Trainable': f"{trainable_result.get('object', 'unknown')} ({trainable_result.get('confidence', 0):.0%})"
        }
        
        # Track which model provided the detection
        final_result['source'] = trainable_result.get('source', 'unknown')
        
        # Use bounding box from best detection
        bbox = frozen_result.get('bbox') or classical_result.get('bbox') or trainable_result.get('bbox')
        if bbox:
            final_result['bbox'] = bbox
        else:
            final_result['bbox'] = [w*0.25, h*0.25, w*0.5, h*0.5]
        
        final_result['confidence'] = self._calculate_confidence(final_result['object'])
        
        # Log result
        if final_result['object'] == 'unknown':
            self._log(f"⚠️ Could not identify object")
        else:
            weights = self.get_adaptive_weights()
            winning = final_result.get('winning_stream', 'unknown')
            gate_emoji = {
                'classical': '🔬',
                'frozen_yolo': '❄️',
                'trainable_yolo': '🌟'
            }.get(winning, '🤖')
            self._log(f"✅ Detection: {gate_emoji} {final_result['object']} ({final_result['confidence']:.1%}) from {winning}")
            self._log(f"   📊 Gate weights: Classical={weights.get('classical',0):.2f}, Frozen={weights.get('frozen_yolo',0):.2f}, Trainable={weights.get('trainable_yolo',0):.2f}")
        
        return final_result
    
    def _gate1_classical_detection(self, image: np.ndarray) -> Dict:
        """
        Gate 1: Classical Vision Methods
        Thesis Section 4.4 - Star clustering, planetary features, comet detection
        """
        detectors = self._get_classical_detectors()
        h, w = image.shape[:2]
        results = []
        
        # Moon detection
        moon_result = detectors['moon'].detect_moon(image)
        if moon_result and moon_result.get('detected') and moon_result.get('confidence', 0) > 0.7:
            results.append({'object': 'moon', 'confidence': 0.85, 'bbox': moon_result.get('bbox')})
            self._log("   🔬 Gate 1 (Classical): Moon detected")
        
        # Planet detection
        planet_result = detectors['planetary'].detect_planet(image)
        if planet_result and planet_result.get('detected') and planet_result.get('confidence', 0) > 0.65:
            planet_type = planet_result.get('type', 'planet')
            results.append({'object': planet_type, 'confidence': 0.85, 'bbox': planet_result.get('bbox')})
            self._log(f"   🔬 Gate 1 (Classical): {planet_type.capitalize()} detected")
        
        # Star field detection
        star_field = detectors['star'].detect_star_field(image)
        if star_field.get('is_star_field') and star_field['star_count'] >= 10:
            results.append({'object': 'star_field', 'confidence': min(0.85, star_field['star_count'] / 30), 
                           'bbox': [w*0.2, h*0.2, w*0.6, h*0.6]})
            self._log(f"   🔬 Gate 1 (Classical): Star field ({star_field['star_count']} stars)")
        elif star_field.get('star_count', 0) == 1:
            brightest = star_field['stars'][0] if star_field['stars'] else None
            if brightest and brightest.get('brightness', 0) > 200:
                results.append({'object': 'star', 'confidence': 0.65, 'bbox': brightest['bbox']})
                self._log("   🔬 Gate 1 (Classical): Single star")
        
        # Comet detection
        comet_result = detectors['comet'].detect_comet(image)
        if comet_result.get('comet_detected') and comet_result.get('tail_detected'):
            results.append({'object': 'comet', 'confidence': 0.75, 'bbox': [w*0.3, h*0.3, w*0.4, h*0.4]})
            self._log("   🔬 Gate 1 (Classical): Comet with tail")
        
        # Sun detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        if mean_brightness > 220:
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=h/2,
                param1=50, param2=20, minRadius=int(h*0.2), maxRadius=int(h*0.8))
            if circles is not None:
                results.append({'object': 'sun', 'confidence': 0.85, 'bbox': [w*0.2, h*0.2, w*0.6, h*0.6]})
                self._log("   🔬 Gate 1 (Classical): Sun detected")
        
        if results:
            best = max(results, key=lambda x: x['confidence'])
            best['gate'] = self.GATE_1_CLASSICAL
            return best
        
        self._log("   🔬 Gate 1 (Classical): No detection")
        return {'object': 'unknown', 'confidence': 0, 'gate': self.GATE_1_CLASSICAL}
    
    def _gate2_frozen_detection(self, image: np.ndarray) -> Dict:
        """
        Gate 2: Frozen YOLO Models (Section 4.3.1 & 4.3.2)
        These models are FROZEN - students cannot modify them (safety net)
        """
        model_manager = self._get_model_manager()
        all_detections = model_manager.detect(image)
        
        if not all_detections:
            self._log("   ❄️ Gate 2 (Frozen): No detections")
            return {'object': 'unknown', 'confidence': 0, 'gate': self.GATE_2_FROZEN}
        
        # Get best detection overall
        best = max(all_detections, key=lambda x: x['confidence'])
        
        source = best.get('source', 'unknown')
        source_emoji = {
            'sun_moon': '☀️',
            'cosmica': '🚀',
            'celestial': '🌟'
        }.get(source, '🤖')
        
        self._log(f"   ❄️ Gate 2 (Frozen): {source_emoji} {source.upper()} - {best['class']} ({best['confidence']:.1%})")
        
        # If multiple detections, log all
        if len(all_detections) > 1:
            others = [f"{d['class']}({d['confidence']:.0%})" for d in all_detections[1:3]]
            self._log(f"      Also detected: {', '.join(others)}")
        
        result = {
            'object': best['class'],
            'confidence': best['confidence'],
            'bbox': best.get('bbox'),
            'source': source,
            'gate': self.GATE_2_FROZEN
        }
        return result
    
    def _gate3_trainable_detection(self, image: np.ndarray) -> Dict:
        """
        Gate 3: Trainable YOLO Model (Section 4.3.3)
        This model can be retrained by students
        """
        model_manager = self._get_model_manager()
        
        # Try to get celestial model detections first
        celestial_detections = []
        if hasattr(model_manager, 'celestial_model') and model_manager.celestial_model:
            try:
                from ultralytics import YOLO
                results = model_manager.celestial_model(image, verbose=False, conf=0.3)
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
                            
                            class_names = model_manager.celestial_classes
                            class_name = class_names.get(class_id, 'unknown')
                            
                            celestial_detections.append({
                                'class': class_name,
                                'confidence': confidence,
                                'bbox': [float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                                'source': 'celestial',
                                'model_type': 'celestial'
                            })
            except Exception as e:
                self._log(f"   ⚠️ Celestial model error: {e}")
        
        if celestial_detections:
            best = max(celestial_detections, key=lambda x: x['confidence'])
            self._log(f"   🌟 Gate 3 (Trainable): {best['class']} ({best['confidence']:.1%})")
            return {
                'object': best['class'],
                'confidence': best['confidence'],
                'bbox': best.get('bbox'),
                'source': 'celestial',
                'gate': self.GATE_3_TRAINABLE
            }
        
        # Fallback to other models
        all_detections = model_manager.detect(image)
        if all_detections:
            best = max(all_detections, key=lambda x: x['confidence'])
            self._log(f"   🌟 Gate 3 (Trainable): {best['class']} ({best['confidence']:.1%})")
            return {
                'object': best['class'],
                'confidence': best['confidence'],
                'bbox': best.get('bbox'),
                'source': best.get('source', 'unknown'),
                'gate': self.GATE_3_TRAINABLE
            }
        
        self._log("   🌟 Gate 3 (Trainable): No detection")
        return {'object': 'unknown', 'confidence': 0, 'gate': self.GATE_3_TRAINABLE}
    
    def _apply_custom_rules(self, image: np.ndarray) -> Dict:
        """Apply custom rules from student corrections"""
        if not self.custom_rules:
            return {'object': 'unknown', 'confidence': 0}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        
        for rule in self.custom_rules[-20:]:
            condition = rule.get('condition', '')
            if 'brightness_medium' in condition and 80 < mean_brightness < 180:
                return {
                    'object': rule['result'],
                    'confidence': rule.get('confidence', 0.65),
                    'source': 'custom_rule',
                    'gate': 'rule_based'
                }
        
        return {'object': 'unknown', 'confidence': 0}
    
    def _weighted_vote(self, classical: Dict, frozen: Dict, trainable: Dict, rule: Dict) -> Dict:
        """
        Adaptive weighted voting (Equation 4.4)
        class(x) = argmax_c Σ w_m · p_m(c|x)
        """
        weights = self.get_adaptive_weights()
        
        votes = {}
        vote_details = {}
        winning_stream = None
        
        self._log(f"   ⚖️ Adaptive weights: Classical={weights.get('classical',0):.2f}, Frozen={weights.get('frozen_yolo',0):.2f}, Trainable={weights.get('trainable_yolo',0):.2f}")
        
        # Gate 1: Classical vote
        classical_obj = classical.get('object', 'unknown')
        if classical_obj != 'unknown':
            obj = classical_obj
            conf = classical.get('confidence', 0)
            gate_weight = weights.get(self.GATE_1_CLASSICAL, 0.6)
            
            votes[obj] = votes.get(obj, 0) + gate_weight
            vote_details[self.GATE_1_CLASSICAL] = {
                'object': obj,
                'weight': gate_weight,
                'confidence': conf,
                'accuracy': self.stream_performance[self.GATE_1_CLASSICAL].accuracy
            }
            self._log(f"   🔬 Gate 1 vote: {obj} (weight: {gate_weight:.2f})")
        
        # Gate 2: Frozen YOLO vote
        frozen_obj = frozen.get('object', 'unknown')
        if frozen_obj != 'unknown':
            obj = frozen_obj
            conf = frozen.get('confidence', 0)
            source = frozen.get('source', 'unknown')
            gate_weight = weights.get(self.GATE_2_FROZEN, 2.0)
            
            final_weight = gate_weight
            
            # Boost weight for classes that match the model's specialty
            if source == 'cosmica' and obj in self.COSMICA_CLASSES:
                final_weight *= 1.8
                self._log(f"   🚀 Frozen COSMICA detected its specialty: {obj}")
            elif source == 'sun_moon' and obj in self.SUN_MOON_CLASSES:
                final_weight *= 1.6
                self._log(f"   ☀️ Frozen Sun/Moon detected its specialty: {obj}")
            
            votes[obj] = votes.get(obj, 0) + final_weight
            vote_details[self.GATE_2_FROZEN] = {
                'object': obj,
                'weight': final_weight,
                'confidence': conf,
                'accuracy': self.stream_performance[self.GATE_2_FROZEN].accuracy,
                'source': source
            }
            self._log(f"   ❄️ Gate 2 vote: {obj} (weight: {final_weight:.2f})")
        
        # Gate 3: Trainable YOLO vote
        trainable_obj = trainable.get('object', 'unknown')
        if trainable_obj != 'unknown':
            obj = trainable_obj
            conf = trainable.get('confidence', 0)
            gate_weight = weights.get(self.GATE_3_TRAINABLE, 0.4)
            
            votes[obj] = votes.get(obj, 0) + gate_weight
            vote_details[self.GATE_3_TRAINABLE] = {
                'object': obj,
                'weight': gate_weight,
                'confidence': conf,
                'accuracy': self.stream_performance[self.GATE_3_TRAINABLE].accuracy
            }
            self._log(f"   🌟 Gate 3 vote: {obj} (weight: {gate_weight:.2f})")
        
        # Rule-based vote
        rule_obj = rule.get('object', 'unknown')
        if rule_obj != 'unknown':
            obj = rule_obj
            rule_weight = 0.3
            votes[obj] = votes.get(obj, 0) + rule_weight
            vote_details['rule_based'] = {
                'object': obj,
                'weight': rule_weight,
                'confidence': rule.get('confidence', 0)
            }
            self._log(f"   📏 Rule vote: {obj} (weight: {rule_weight:.2f})")
        
        if not votes:
            return {'object': 'unknown', 'voting_result': 'no_detection', 'winning_stream': None}
        
        # Determine winner
        winner = max(votes, key=votes.get)
        winner_votes = votes[winner]
        total_votes = sum(votes.values())
        
        # Find which gate provided the winner
        for stream, details in vote_details.items():
            if details.get('object') == winner:
                winning_stream = stream
                break
        
        # Determine voting result type
        if len(votes) == 1:
            voting_result = 'unanimous'
        elif winner_votes > total_votes / 2:
            voting_result = 'majority'
        else:
            voting_result = 'plurality'
        
        # Calculate confidence from winning stream
        confidence = 0
        if winning_stream and winning_stream in vote_details:
            confidence = vote_details[winning_stream].get('confidence', 0)
        
        self._log(f"   🏆 Winner: {winner} from {winning_stream} ({winner_votes:.1f}/{total_votes:.1f} votes, {voting_result})")
        
        return {
            'object': winner,
            'confidence': confidence,
            'voting_result': voting_result,
            'winning_stream': winning_stream,
            'vote_details': vote_details
        }
    
    def _add_specialized_classifications(self, image: np.ndarray, result: Dict) -> Dict:
        """Add specialized classifications for stars, galaxies, and moon phases"""
        result['specialized'] = {}
        obj_class = result.get('object', 'unknown')
        bbox = result.get('bbox')
        
        if bbox and len(bbox) == 4 and obj_class != 'unknown':
            x, y, w, h = [int(v) for v in bbox]
            x, y = max(0, x), max(0, y)
            w = min(w, image.shape[1] - x)
            h = min(h, image.shape[0] - y)
            
            if w > 0 and h > 0:
                crop = image[y:y+h, x:x+w]
                if crop.size > 0:
                    if obj_class in ['star', 'star_field']:
                        from ..ml import StarColorClassifier
                        classifier = StarColorClassifier(config)
                        result['specialized']['star_color'] = classifier.classify(crop)
                    elif obj_class in ['galaxy', 'nebula']:
                        from ..ml import GalaxyMorphologyClassifier
                        classifier = GalaxyMorphologyClassifier()
                        result['specialized']['galaxy_morphology'] = classifier.classify(crop)
                    elif obj_class == 'moon':
                        from ..classical import MoonDetector
                        detector = MoonDetector()
                        result['specialized']['moon_phase'] = detector.estimate_moon_phase(crop)
        
        return result
    
    def _calculate_confidence(self, detected_class: str) -> float:
        """Calculate confidence based on class thresholds"""
        class_confidences = {
            'sun': 0.85, 'moon': 0.80, 'planet': 0.75, 'jupiter': 0.78,
            'saturn': 0.77, 'mars': 0.76, 'galaxy': 0.80, 'nebula': 0.78,
            'comet': 0.75, 'asteroid': 0.70, 'star': 0.65, 'star_field': 0.70,
            'clouds': 0.70, 'other': 0.50
        }
        return class_confidences.get(detected_class, 0.7)
    
    def record_correction(self, image_path: str, predicted: str, correct: str, was_correct: bool):
        """Record correction for learning"""
        if self.learning_manager:
            self.learning_manager.add_correction(image_path, predicted, correct, was_correct)
    
    def get_learning_stats(self) -> Dict:
        """Get comprehensive learning statistics"""
        weights = self.get_adaptive_weights()
        stats = {
            'gate_stats': self.get_stream_stats(),
            'custom_rules_count': len(self.custom_rules),
            'classical_confusions': self.classical_confusions,
            'current_weights': weights,
            'consensus_pending': self.consensus_manager.get_pending_count(),
            'consensus_history_count': len(self.consensus_manager.consensus_history)
        }
        
        if self.learning_manager:
            stats.update({
                'pending': self.learning_manager.get_pending_count(),
                'total_corrections': self.learning_manager.get_auto_conversion_stats().get('total_corrections', 0),
                'recent_accuracy': self.learning_manager.get_recent_accuracy(),
                'class_counts': self.learning_manager.get_class_counts()
            })
        
        return stats
    
    def reload_model(self):
        """Reload all models (called after training)"""
        if self._model_manager:
            self._model_manager.reload_model()
            self._log("🔄 All models reloaded")
    
    def shutdown(self):
        """Shutdown pipeline and save state"""
        self._save_stream_performance()
        self._log("🛑 HECD Pipeline shutdown")