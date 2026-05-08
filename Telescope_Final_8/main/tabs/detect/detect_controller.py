# File: tabs/detect/detect_controller.py - Complete Business Logic with Adaptive Learning
# UPDATED: Support for three specialized YOLO models (sun_moon, cosmica, celestial)

import sys
import os
import datetime
import traceback
import threading
import time
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMessageBox, QFileDialog, QDialog, 
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QRadioButton, QButtonGroup, QPushButton, 
    QWidget, QProgressBar, QCheckBox, QScrollArea  
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QMutex, QMutexLocker


class DetectionController(QObject):
    """Handles all detection business logic with adaptive learning"""
    
    # Signals for thread-safe UI updates
    log_signal = pyqtSignal(str)
    stats_update_signal = pyqtSignal(int, float, int, int, bool, int)
    model_status_signal = pyqtSignal(str)
    stream_stats_signal = pyqtSignal(dict)
    
    AUTO_TRAIN_THRESHOLD = 50  # Auto-train after 50 annotations
    LOW_CONFIDENCE_THRESHOLD = 0.4
    
    # Expanded class list for celestial objects
    ALL_CLASSES = [
        "sun", "moon", "planet", "galaxy", "nebula", "comet", 
        "asteroid", "star", "star_cluster", "supernova", "black_hole",
        "aurora", "meteor", "satellite", "space_station", "clouds",
        "airplane", "bird", "other"
    ]
    
    def __init__(self, ui_widget):
        super().__init__()
        self.ui = ui_widget
        self.language_manager = None
        self.theme_manager = None
        self.detection_pipeline = None
        self.learning_manager = None
        
        # Thread-safe locks
        self._state_lock = threading.RLock()
        self._detection_lock = threading.Lock()
        self._training_lock = threading.Lock()
        
        # Thread-safe flags
        self._is_detecting = False
        self._is_training = False
        
        # Data with thread safety
        self._current_image_path: Optional[str] = None
        self._current_image_pixmap = None
        self._current_detection_result: Optional[Dict] = None
        self._folder_images: List[str] = []
        self._current_folder_index: int = -1
        
        # Connect signals
        self.log_signal.connect(self._safe_add_log)
        self.stats_update_signal.connect(self._safe_update_stats)
        self.model_status_signal.connect(self._safe_update_model_status)
        self.stream_stats_signal.connect(self._safe_update_stream_stats)
        
        # Initialize managers
        self._init_learning_manager()
        
        # Start stats timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_learning_stats)
        self.stats_timer.start(5000)
        
        # Initialize pipeline
        QTimer.singleShot(500, self.init_detection_pipeline)
        
        print("DEBUG: DetectionController initialized with adaptive learning (3 specialized models)")
    
    def _init_learning_manager(self):
        """Initialize learning manager safely"""
        try:
            from .image_train.training.learning_manager import LearningManager
            self.learning_manager = LearningManager()
            self.learning_manager.set_log_callback(self.add_log)
            print("DEBUG: LearningManager initialized successfully")
        except ImportError as e:
            print(f"DEBUG: Could not import LearningManager: {e}")
            traceback.print_exc()
            self.learning_manager = None
    
    def _get_learning_manager(self):
        """Get learning manager instance"""
        if self.learning_manager is None:
            self._init_learning_manager()
        return self.learning_manager
    
    # Thread-safe property getters/setters
    @property
    def current_image_path(self) -> Optional[str]:
        with self._state_lock:
            return self._current_image_path
    
    @current_image_path.setter
    def current_image_path(self, value: Optional[str]):
        with self._state_lock:
            self._current_image_path = value
    
    @property
    def current_image_pixmap(self):
        with self._state_lock:
            return self._current_image_pixmap
    
    @current_image_pixmap.setter
    def current_image_pixmap(self, value):
        with self._state_lock:
            self._current_image_pixmap = value
    
    @property
    def current_detection_result(self) -> Optional[Dict]:
        with self._state_lock:
            return self._current_detection_result
    
    @current_detection_result.setter
    def current_detection_result(self, value: Optional[Dict]):
        with self._state_lock:
            self._current_detection_result = value
    
    @property
    def folder_images(self) -> List[str]:
        with self._state_lock:
            return self._folder_images.copy()
    
    @folder_images.setter
    def folder_images(self, value: List[str]):
        with self._state_lock:
            self._folder_images = value.copy()
    
    @property
    def current_folder_index(self) -> int:
        with self._state_lock:
            return self._current_folder_index
    
    @current_folder_index.setter
    def current_folder_index(self, value: int):
        with self._state_lock:
            self._current_folder_index = value
    
    def set_managers(self, language_manager, theme_manager):
        """Set language and theme managers"""
        self.language_manager = language_manager
        self.theme_manager = theme_manager
    
    def apply_theme(self, theme):
        """Apply theme to UI"""
        if self.ui and hasattr(self.ui, 'apply_theme'):
            self.ui.apply_theme(theme)
    
    def set_callbacks(self, log_callback=None, stats_callback=None, model_status_callback=None):
        """Set callback functions"""
        self.log_callback = log_callback or (self.ui.add_log if self.ui else None)
        self.stats_callback = stats_callback or (self.ui.update_learning_stats_display if self.ui else None)
        self.model_status_callback = model_status_callback or (self.ui.update_model_status_display if self.ui else None)
    
    def _safe_add_log(self, message: str):
        """Safely add log message"""
        try:
            if self.log_callback:
                self.log_callback(message)
        except (RuntimeError, AttributeError):
            pass
    
    def _safe_update_stats(self, pending: int, accuracy: float, corrections: int, 
                           auto_converted: int, is_training: bool, progress: int):
        """Safely update statistics display"""
        try:
            if self.stats_callback:
                self.stats_callback(pending, accuracy, corrections, auto_converted, is_training, progress)
        except (RuntimeError, AttributeError):
            pass
    
    def _safe_update_model_status(self, status_text: str):
        """Safely update model status"""
        try:
            if self.model_status_callback:
                self.model_status_callback(status_text)
        except (RuntimeError, AttributeError):
            pass
    
    def _safe_update_stream_stats(self, stream_stats: dict):
        """Safely update stream statistics display"""
        try:
            if self.ui and hasattr(self.ui, 'update_stream_stats_display'):
                self.ui.update_stream_stats_display(stream_stats)
        except (RuntimeError, AttributeError):
            pass
    
    def _get_theme_colors(self):
        """Get current theme colors for dialogs"""
        theme_colors = {}
        if self.theme_manager:
            if hasattr(self.theme_manager, 'get_colors'):
                theme_colors = self.theme_manager.get_colors()
            elif hasattr(self.theme_manager, 'get_current_colors'):
                theme_colors = self.theme_manager.get_current_colors()
        
        # Default fallback colors
        if not theme_colors:
            theme_colors = {
                'bg_secondary': '#1e293b',
                'text': '#f8fafc',
                'accent': '#38bdf8',
                'button_bg': '#2563eb',
                'button_hover': '#38bdf8',
                'button_text': '#ffffff',
                'border': '#475569',
                'row_bg': 'rgba(30, 41, 59, 0.8)'
            }
        
        return theme_colors
    
    def add_log(self, message: str):
        """Add log message (thread-safe)"""
        self.log_signal.emit(message)
        print(f"LOG: {message}")
    
    def is_valid(self) -> bool:
        """Check if UI is still valid"""
        try:
            return self.ui and not self.ui.isHidden()
        except (RuntimeError, AttributeError):
            return False
    
    def init_detection_pipeline(self):
        """Initialize the detection pipeline"""
        if not self.is_valid():
            return
        try:
            self.add_log(" Initializing detection pipeline...")
            from .image_train.core.detection_pipeline import ContinuousLearningPipeline
            self.detection_pipeline = ContinuousLearningPipeline(
                self._get_learning_manager(),
                log_callback=self.add_log
            )
            self.add_log(" Detection pipeline initialized - 3 specialized models active")
            self.add_log("   ☀️ Sun/Moon model: sun, moon")
            self.add_log("   🚀 Cosmica model: comet, galaxy, star, nebula")
            self.add_log("   🌟 Celestial model: trainable (10 classes)")
            self.update_learning_stats()
            self.update_model_status()
            self.update_stream_stats()
        except Exception as e:
            self.add_log(f" Failed to initialize pipeline: {str(e)}")
            traceback.print_exc()
    
    def update_stream_stats(self):
        """Update stream performance statistics"""
        if self.detection_pipeline:
            try:
                stats = self.detection_pipeline.get_stream_stats()
                self.stream_stats_signal.emit(stats)
            except Exception as e:
                print(f"Error updating stream stats: {e}")
    
    def update_model_status(self):
        """Update model status display with all three models"""
        if not self.is_valid():
            return
        try:
            if self.detection_pipeline and hasattr(self.detection_pipeline, '_get_model_manager'):
                model_manager = self.detection_pipeline._get_model_manager()
                model_info = model_manager.get_model_info()
                
                status_lines = []
                
                # Sun/Moon model
                if model_info.get('sun_moon_available'):
                    status_lines.append("☀️ Sun/Moon model: sun, moon")
                else:
                    status_lines.append("⚠️ Sun/Moon model: NOT FOUND")
                
                # Cosmica model
                if model_info.get('cosmica_available'):
                    status_lines.append("🚀 Cosmica model: comet, galaxy, star, nebula")
                else:
                    status_lines.append("⚠️ Cosmica model: NOT FOUND")
                
                # Celestial model (trainable)
                if model_info.get('celestial_available'):
                    classes = model_info.get('celestial_classes', [])
                    class_str = ', '.join(classes[:8])
                    if len(classes) > 8:
                        class_str += f" +{len(classes)-8} more"
                    status_lines.append(f"🌟 Celestial model (trainable): {class_str}")
                else:
                    status_lines.append("⚠️ Celestial model: NOT FOUND - Run training")
                
                # Primary model
                primary = model_info.get('primary_model', 'unknown').upper()
                status_lines.append(f"🎯 Primary model: {primary}")
                
                self.model_status_signal.emit("\n".join(status_lines))
            else:
                self.model_status_signal.emit(" Pipeline not ready")
        except Exception as e:
            print(f"Error updating model status: {e}")
    
    def load_image(self):
        """Load a single image"""
        self.add_log(" Opening file browser...")
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self.ui, "Select Image", "", 
                "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff)"
            )
            if file_path and os.path.exists(file_path):
                self.current_image_path = file_path
                self._load_and_display_image(file_path)
                self.folder_images = []
                self.current_folder_index = -1
                if self.ui:
                    self.ui.set_navigation_buttons(False, False)
                    self.ui.update_image_counter(0, 0)
                self.add_log(f" Loaded image: {os.path.basename(file_path)}")
        except Exception as e:
            self.add_log(f" Error loading image: {str(e)}")
    
    def load_folder(self):
        """Load a folder of images"""
        self.add_log(" Opening folder browser...")
        try:
            default_dir = "/home/Upendra/Desktop/training image"
            
            if not os.path.exists(default_dir):
                self.add_log(f" Default directory not found: {default_dir}")
                default_dir = os.path.expanduser("~")
            
            folder_path = QFileDialog.getExistingDirectory(
                self.ui, 
                "Select Image Folder", 
                default_dir,
                QFileDialog.ShowDirsOnly
            )
            
            if folder_path and os.path.isdir(folder_path):
                self.add_log(f" Loading folder: {folder_path}")
                extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.PNG', '.JPG', '.JPEG')
                images = []
                for f in os.listdir(folder_path):
                    if f.lower().endswith(extensions):
                        full_path = os.path.join(folder_path, f)
                        if os.path.isfile(full_path):
                            images.append(full_path)
                images.sort()
                self.folder_images = images
                if images:
                    self.current_folder_index = 0
                    self._load_and_display_image(images[0])
                    if self.ui:
                        self.ui.set_navigation_buttons(True, len(images) > 1)
                        self.ui.update_image_counter(1, len(images))
                    self.add_log(f" Loaded {len(images)} images from folder")
                else:
                    self.add_log(" No image files found in folder")
        except Exception as e:
            self.add_log(f" Error loading folder: {str(e)}")
    
    def _load_and_display_image(self, image_path: str):
        """Load and display an image"""
        try:
            if not os.path.exists(image_path):
                self.add_log(f" File does not exist: {image_path}")
                return
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                self.add_log(f" Failed to load image: {image_path}")
                return
            self.current_image_path = image_path
            self.current_image_pixmap = pixmap
            if self.ui:
                self.ui.set_image_display(pixmap, [])
                self.ui.annotate_btn.setEnabled(True)
                self.ui.detect_btn.setEnabled(True)
                self.ui.clear_detection_results()
            self.add_log(f" Image loaded: {os.path.basename(image_path)} ({pixmap.width()}x{pixmap.height()})")
        except Exception as e:
            self.add_log(f" Error loading image: {str(e)}")
    
    def prev_image(self):
        """Navigate to previous image in folder"""
        folder_images = self.folder_images
        current_idx = self.current_folder_index
        if folder_images and current_idx > 0:
            self.current_folder_index = current_idx - 1
            self._load_and_display_image(folder_images[current_idx - 1])
            if self.ui:
                self.ui.update_image_counter(current_idx, len(folder_images))
                self.ui.clear_detection_results()
    
    def next_image(self):
        """Navigate to next image in folder"""
        folder_images = self.folder_images
        current_idx = self.current_folder_index
        if folder_images and current_idx < len(folder_images) - 1:
            self.current_folder_index = current_idx + 1
            self._load_and_display_image(folder_images[current_idx + 1])
            if self.ui:
                self.ui.update_image_counter(current_idx + 2, len(folder_images))
                self.ui.clear_detection_results()
    
    def run_detection(self):
        """Run detection on current image with thread safety"""
        with self._detection_lock:
            if self._is_detecting:
                self.add_log(" Detection already in progress")
                return
            self._is_detecting = True
        
        try:
            current_pixmap = self.current_image_pixmap
            current_path = self.current_image_path
            
            if not current_pixmap:
                self.add_log(" No image loaded")
                if self.ui:
                    QMessageBox.warning(self.ui, "Warning", "Please load an image first")
                return
            
            if not self.detection_pipeline:
                self.add_log(" Detection pipeline not initialized")
                self.init_detection_pipeline()
                return
            
            self.add_log("=" * 50)
            self.add_log(" RUNNING ADAPTIVE DETECTION")
            
            if self.ui:
                self.ui.set_detection_button_state(detecting=True)
            
            result = self.detection_pipeline.detect(current_path)
            
            if not result or 'error' in result:
                self.add_log(f" Detection failed")
                return
            
            self.current_detection_result = result
            detected_object = result.get('object', 'Unknown')
            confidence = result.get('confidence', 0)
            voting_result = result.get('voting_result', 'N/A')
            winning_stream = result.get('winning_stream', 'N/A')
            detection_source = result.get('source', 'unknown')
            
            # Check if unknown
            is_unknown = (detected_object == 'unknown' or confidence < self.LOW_CONFIDENCE_THRESHOLD)
            
            quality = result.get('image_quality', {})
            quality_text = f"Quality: {quality.get('quality', 'Unknown')}"
            
            streams = result.get('streams', {})
            streams_text = f"Classical: {streams.get('Classical', 'N/A')} | ML: {streams.get('ML', 'N/A')} | Rule: {streams.get('Rule-Based', 'N/A')}"
            
            specialized = result.get('specialized', {})
            specialized_text = ""
            if 'star_color' in specialized:
                sc = specialized['star_color']
                specialized_text += f" Star: {sc.get('color', 'Unknown')} "
            if 'galaxy_morphology' in specialized:
                gm = specialized['galaxy_morphology']
                specialized_text += f" Galaxy: {gm.get('morphology', 'Unknown')}"
            
            if self.ui:
                self.ui.update_detection_results(
                    detected_object if not is_unknown else "Unknown", 
                    confidence, voting_result,
                    quality_text, streams_text, specialized_text,
                    source=detection_source
                )
                self.update_stream_stats()
            
            bbox = result.get('bbox')
            if bbox and len(bbox) == 4 and not is_unknown:
                x, y, w, h = bbox
                if self.ui:
                    self.ui.set_image_display(current_pixmap, [{
                        'x': x, 'y': y, 'w': w, 'h': h,
                        'label': detected_object, 'confidence': confidence
                    }])
                self.add_log(f" Bounding box drawn")
            else:
                if self.ui:
                    self.ui.set_image_display(current_pixmap, [])
            
            if is_unknown:
                self.add_log(f" Could not identify object in image")
                self._show_unknown_detection_dialog()
            else:
                source_emoji = {
                    'celestial': '🌟',
                    'cosmica': '🚀',
                    'sun_moon': '☀️',
                    'classical': '🔬',
                    'rule_based': '📏'
                }.get(detection_source, '🤖')
                self.add_log(f" Detection complete: {source_emoji} {detected_object} ({confidence:.1%}) from {winning_stream}")
                if self.ui:
                    self.ui.enable_feedback_buttons(True)
            
        except Exception as e:
            self.add_log(f" Detection error: {str(e)}")
            traceback.print_exc()
        finally:
            if self.ui:
                self.ui.set_detection_button_state(detecting=False)
            self.add_log("=" * 50)
            with self._detection_lock:
                self._is_detecting = False
    
    def _show_unknown_detection_dialog(self):
        """Show dialog for unknown detection with theme-aware colors"""
        try:
            dialog = QDialog(self.ui)
            dialog.setWindowTitle("Unknown Detection")
            dialog.setModal(True)
            dialog.setMinimumWidth(450)
            dialog.setAttribute(Qt.WA_DeleteOnClose, True)
            
            theme_colors = self._get_theme_colors()
            
            bg_color = theme_colors.get('bg_secondary', '#1e293b')
            text_color = theme_colors.get('text', '#f8fafc')
            accent_color = theme_colors.get('accent', '#38bdf8')
            button_bg = theme_colors.get('button_bg', '#2563eb')
            button_hover = theme_colors.get('button_hover', '#38bdf8')
            button_text = theme_colors.get('button_text', '#ffffff')
            row_bg = theme_colors.get('row_bg', 'rgba(30, 41, 59, 0.8)')
            
            dialog.setStyleSheet(f"""
                QDialog {{
                    background-color: {bg_color};
                    color: {text_color};
                }}
                QLabel {{
                    color: {text_color};
                    background-color: transparent;
                }}
                QPushButton {{
                    background-color: {button_bg};
                    color: {button_text};
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                }}
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            icon_label = QLabel("?")
            icon_label.setStyleSheet(f"font-size: 48px; background-color: transparent;")
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
            
            title_label = QLabel("<b>No Object Detected</b>")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet(f"font-size: 14px; color: {accent_color};")
            layout.addWidget(title_label)
            
            message_label = QLabel(
                "The system could not identify this image.\n\n"
                "Possible reasons:\n"
                "• Not a celestial object\n"
                "• Poor image quality\n"
                "• Object not in training set\n\n"
                "What would you like to do?"
            )
            message_label.setWordWrap(True)
            message_label.setAlignment(Qt.AlignCenter)
            message_label.setStyleSheet(f"padding: 8px; background-color: {row_bg}; border-radius: 4px;")
            layout.addWidget(message_label)
            
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(10)
            
            annotate_btn = QPushButton("Manually Annotate")
            annotate_btn.clicked.connect(lambda: self._open_annotation_from_unknown(dialog))
            skip_btn = QPushButton("Skip")
            skip_btn.clicked.connect(dialog.reject)
            next_btn = QPushButton("Next Image")
            next_btn.clicked.connect(lambda: self._next_after_unknown(dialog))
            
            btn_layout.addWidget(annotate_btn)
            btn_layout.addWidget(skip_btn)
            btn_layout.addWidget(next_btn)
            layout.addLayout(btn_layout)
            
            dialog.exec_()
            
        except Exception as e:
            print(f"Error showing unknown dialog: {e}")
    
    def _open_annotation_from_unknown(self, dialog: QDialog):
        """Open annotation wizard from unknown dialog"""
        dialog.accept()
        self.open_annotation_wizard()
    
    def _next_after_unknown(self, dialog: QDialog):
        """Go to next image after unknown"""
        dialog.accept()
        self.next_image()
    
    def provide_feedback(self, is_correct: bool):
        """Provide feedback on detection result - updates adaptive weights and stream learning"""
        current_result = self.current_detection_result
        current_path = self.current_image_path
        
        if not current_result or not current_path:
            self.add_log(" No detection result")
            return
        
        predicted_class = current_result.get('object', 'unknown')
        confidence = current_result.get('confidence', 0)
        
        if predicted_class == 'unknown':
            self.add_log(" Cannot provide feedback for unknown detection")
            return
        
        winning_stream = current_result.get('winning_stream', None)
        
        try:
            if is_correct:
                self.add_log(f" Feedback: CORRECT ({predicted_class})")
                if self.detection_pipeline and winning_stream:
                    self.detection_pipeline.record_feedback_with_learning(
                        stream_name=winning_stream,
                        was_correct=True,
                        predicted_class=predicted_class,
                        correct_class=predicted_class,
                        confidence=confidence,
                        image_features={
                            'image_path': current_path,
                            'confidence': confidence,
                            'bbox': current_result.get('bbox')
                        }
                    )
                    self.add_log(f"   Improved {winning_stream} stream performance")
                    self.update_stream_stats()
                self.update_learning_stats()
            else:
                self.add_log(f" Feedback: INCORRECT ({predicted_class})")
                if self.detection_pipeline and winning_stream:
                    self.detection_pipeline.record_feedback_with_learning(
                        stream_name=winning_stream,
                        was_correct=False,
                        predicted_class=predicted_class,
                        correct_class=None,
                        confidence=confidence,
                        image_features={
                            'image_path': current_path,
                            'confidence': confidence,
                            'bbox': current_result.get('bbox')
                        }
                    )
                    self.add_log(f"   Will learn from {winning_stream} stream's mistake")
                self._open_correction_dialog(predicted_class)
            
            if self.ui:
                self.ui.enable_feedback_buttons(False)
                self.update_stream_stats()
                
        except Exception as e:
            self.add_log(f" Error: {str(e)}")
    
    def _open_correction_dialog(self, predicted_class: str):
        """Open dialog for correction - with theme-aware colors preserving original layout"""
        try:
            dialog = QDialog(self.ui)
            dialog.setWindowTitle("Select Correct Class")
            dialog.setModal(True)
            dialog.setMinimumWidth(550)
            dialog.setMinimumHeight(450)
            dialog.setAttribute(Qt.WA_DeleteOnClose, True)
            
            theme_colors = self._get_theme_colors()
            
            bg_color = theme_colors.get('bg_secondary', '#1e293b')
            text_color = theme_colors.get('text', '#f8fafc')
            accent_color = theme_colors.get('accent', '#38bdf8')
            button_bg = theme_colors.get('button_bg', '#2563eb')
            button_hover = theme_colors.get('button_hover', '#38bdf8')
            button_text = theme_colors.get('button_text', '#ffffff')
            border_color = theme_colors.get('border', '#475569')
            row_bg = theme_colors.get('row_bg', 'rgba(30, 41, 59, 0.8)')
            
            dialog.setStyleSheet(f"""
                QDialog {{
                    background-color: {bg_color};
                    color: {text_color};
                }}
                QLabel {{
                    color: {text_color};
                    background-color: transparent;
                }}
                QRadioButton {{
                    color: {text_color};
                    spacing: 8px;
                    padding: 4px;
                }}
                QRadioButton::indicator {{
                    width: 14px;
                    height: 14px;
                    border-radius: 7px;
                }}
                QRadioButton::indicator:unchecked {{
                    border: 2px solid {accent_color};
                    background-color: transparent;
                }}
                QRadioButton::indicator:checked {{
                    border: 2px solid {accent_color};
                    background-color: {accent_color};
                }}
                QRadioButton:hover {{
                    background-color: {row_bg};
                    border-radius: 4px;
                }}
                QCheckBox {{
                    color: {text_color};
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                }}
                QCheckBox::indicator:unchecked {{
                    border: 2px solid {accent_color};
                    background-color: transparent;
                }}
                QCheckBox::indicator:checked {{
                    border: 2px solid {accent_color};
                    background-color: {accent_color};
                }}
                QPushButton {{
                    background-color: {button_bg};
                    color: {button_text};
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                }}
                QScrollArea {{
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    background-color: transparent;
                }}
                QScrollBar:vertical {{
                    background-color: {bg_color};
                    width: 10px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: {accent_color};
                    border-radius: 5px;
                    min-height: 20px;
                }}
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            
            winning_stream = self.current_detection_result.get('winning_stream', 'Unknown')
            detection_source = self.current_detection_result.get('source', 'unknown')
            source_emoji = {
                'celestial': '🌟',
                'cosmica': '🚀',
                'sun_moon': '☀️'
            }.get(detection_source, '🤖')
            
            info_label = QLabel(
                f"<b>Predicted:</b> <span style='color:#ff6b6b;'>{predicted_class.upper()}</span><br>"
                f"<b>Detected by:</b> {source_emoji} {detection_source.upper()}<br>"
                f"<b>Winning Stream:</b> {winning_stream.upper()}<br>"
                f"<b>Select the correct object:</b>"
            )
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMaximumHeight(350)
            
            scroll_widget = QWidget()
            scroll_widget.setStyleSheet(f"background-color: transparent;")
            grid_layout = QGridLayout(scroll_widget)
            grid_layout.setSpacing(8)
            
            button_group = QButtonGroup(dialog)
            
            # Show only celestial-relevant classes first
            priority_classes = ["sun", "moon", "planet", "galaxy", "nebula", "comet", "asteroid", "star"]
            other_classes = [c for c in self.ALL_CLASSES if c not in priority_classes]
            
            all_display_classes = priority_classes + other_classes
            
            for i, cls in enumerate(all_display_classes):
                btn = QRadioButton(cls.replace('_', ' ').title())
                btn.setToolTip(cls)
                btn.setCursor(Qt.PointingHandCursor)
                button_group.addButton(btn, i)
                row = i // 3
                col = i % 3
                grid_layout.addWidget(btn, row, col)
            
            scroll_widget.setLayout(grid_layout)
            scroll_area.setWidget(scroll_widget)
            layout.addWidget(scroll_area)
            
            auto_train_checkbox = QCheckBox("Add to training queue (for ML retraining)")
            auto_train_checkbox.setChecked(True)
            layout.addWidget(auto_train_checkbox)
            
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Submit")
            cancel_btn = QPushButton("Cancel")
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)
            
            def on_submit():
                checked_id = button_group.checkedId()
                if checked_id >= 0:
                    correct_class = all_display_classes[checked_id]
                    
                    winning_stream = self.current_detection_result.get('winning_stream', 'ml')
                    
                    if self.detection_pipeline:
                        self.detection_pipeline.record_feedback_with_learning(
                            stream_name=winning_stream,
                            was_correct=False,
                            predicted_class=predicted_class,
                            correct_class=correct_class,
                            confidence=self.current_detection_result.get('confidence', 0),
                            image_features={
                                'image_path': self.current_image_path,
                                'confidence': self.current_detection_result.get('confidence', 0),
                                'bbox': self.current_detection_result.get('bbox')
                            }
                        )
                        
                        self.detection_pipeline.record_correction(
                            self.current_image_path, predicted_class, correct_class, False
                        )
                    
                    if auto_train_checkbox.isChecked():
                        self._add_to_training_queue(correct_class)
                    
                    self.add_log(f" Correction: {predicted_class} -> {correct_class} (from {winning_stream})")
                    self.update_learning_stats()
                    self.update_stream_stats()
                    self.trigger_auto_training()
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "Warning", "Please select a class")
            
            ok_btn.clicked.connect(on_submit)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec_()
            
        except Exception as e:
            self.add_log(f" Error: {str(e)}")
            traceback.print_exc()
    
    def _add_to_training_queue(self, correct_class: str):
        """Add annotation to training queue"""
        try:
            current_path = self.current_image_path
            current_pixmap = self.current_image_pixmap
            
            if not current_path:
                return
            
            if current_pixmap:
                img_w, img_h = current_pixmap.width(), current_pixmap.height()
                norm_bbox = {
                    'x_center': 0.5,
                    'y_center': 0.5,
                    'width': 0.6,
                    'height': 0.6
                }
            else:
                norm_bbox = {'x_center': 0.5, 'y_center': 0.5, 'width': 0.6, 'height': 0.6}
            
            learning_manager = self._get_learning_manager()
            if learning_manager:
                success = learning_manager.add_annotation(
                    current_path, correct_class, norm_bbox, {}, 80
                )
                if success:
                    self.add_log(f" Added to training: {correct_class}")
                    self.update_learning_stats()
                    
                    # Show current class distribution
                    class_counts = learning_manager.get_class_counts()
                    self.add_log(f"   Class counts: {class_counts}")
        except Exception as e:
            self.add_log(f" Error adding to training: {str(e)}")
    
    def open_annotation_wizard(self):
        """Open annotation wizard"""
        current_path = self.current_image_path
        current_pixmap = self.current_image_pixmap
        
        if not current_path or current_pixmap is None:
            self.add_log(" Please load an image first")
            if self.ui:
                QMessageBox.warning(self.ui, "Warning", "Please load an image first")
            return
        
        try:
            from .image_train.annotation.annotation_wizard import AnnotationWizard
            
            wizard = AnnotationWizard(
                current_path, current_pixmap, self.detection_pipeline,
                self.theme_manager, self.ui
            )
            
            if wizard.exec_() == QDialog.Accepted:
                self.add_log(" Annotation saved")
                self.update_learning_stats()
                self.update_stream_stats()
                self.trigger_auto_training()
            
        except Exception as e:
            self.add_log(f" Error: {str(e)}")
            traceback.print_exc()
    
    def on_box_drawn(self, box_data: Dict):
        """Handle box drawn on image"""
        if not box_data:
            return
        
        current_path = self.current_image_path
        current_pixmap = self.current_image_pixmap
        
        if current_path:
            try:
                from .image_train.annotation.annotation_wizard import AnnotationWizard
                
                wizard = AnnotationWizard(
                    current_path, current_pixmap, self.detection_pipeline,
                    self.theme_manager, self.ui, pre_drawn_box=box_data
                )
                if wizard.exec_() == QDialog.Accepted:
                    self.add_log(" Annotation saved")
                    self.update_learning_stats()
                    self.update_stream_stats()
                    self.trigger_auto_training()
            except Exception as e:
                self.add_log(f" Error: {str(e)}")
    
    def trigger_auto_training(self):
        """Trigger auto-training if threshold reached"""
        try:
            pending = self._get_pending_count()
            total_images = sum(self._get_class_counts().values())
            self.add_log(f" Training data: {total_images} total images, {pending} pending")
            
            if total_images >= self.AUTO_TRAIN_THRESHOLD:
                self.add_log(f" Training threshold reached! ({total_images}/{self.AUTO_TRAIN_THRESHOLD} images)")
                self.force_training()
            else:
                remaining = self.AUTO_TRAIN_THRESHOLD - total_images
                self.add_log(f" Need {remaining} more images for auto-training")
        except Exception as e:
            self.add_log(f" Error: {str(e)}")
    
    def force_training(self):
        """Force model training - Trains CELESTIAL model only"""
        with self._training_lock:
            if self._is_training:
                self.add_log(" Training already in progress")
                return
            self._is_training = True
        
        try:
            if not self.detection_pipeline:
                self.add_log(" Pipeline not initialized")
                return
            
            pending = self._get_pending_count()
            class_counts = self._get_class_counts()
            total_images = sum(class_counts.values())
            
            self.add_log("=" * 50)
            self.add_log(" STARTING CELESTIAL MODEL TRAINING")
            self.add_log(f" Total training images: {total_images}")
            self.add_log(f" Pending annotations: {pending}")
            self.add_log(f" Class distribution:")
            
            for cls, count in class_counts.items():
                if count > 0:
                    bar = "#" * min(count, 20)
                    self.add_log(f"   - {cls:12s}: {bar} {count}")
            
            if total_images == 0:
                self.add_log(" No training data available!")
                self.add_log("   Please annotate images first using the Annotation Wizard")
                self._is_training = False
                return
            
            if total_images < 10:
                reply = QMessageBox.question(
                    self.ui,
                    "Insufficient Data",
                    f"Only {total_images} total images available.\n\n"
                    "Recommended minimum: 50 images for training.\n"
                    "Training with limited data may produce poor results.\n\n"
                    "Continue anyway?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    self._is_training = False
                    return
            
            from .image_train.training.training_dialog import TrainingDialog
            
            dialog = TrainingDialog(
                self._get_learning_manager(), 
                self.detection_pipeline,
                self.theme_manager, 
                self.ui
            )
            
            if dialog.exec_():
                self.add_log(" Training completed successfully")
                if self.detection_pipeline:
                    self.detection_pipeline.reload_model()
                    self.update_model_status()
                    self.update_stream_stats()
                    
                    # Show model info after training
                    if hasattr(self.detection_pipeline, '_get_model_manager'):
                        model_manager = self.detection_pipeline._get_model_manager()
                        model_info = model_manager.get_model_info()
                        self.add_log(f" Celestial model loaded: {model_info.get('model_type', 'unknown')}")
                        if model_info.get('celestial_available'):
                            self.add_log(f"   Classes: {', '.join(model_info.get('celestial_classes', []))}")
                        
                        # Check if model was actually created
                        current_dir = Path(__file__).resolve()
                        main_dir = current_dir.parent.parent.parent
                        models_dir = main_dir / "models"
                        celestial_model = models_dir / "yolov8n_celestial.pt"
                        if celestial_model.exists():
                            self.add_log(f" Celestial model saved at: {celestial_model}")
                            self.add_log(f"   Size: {celestial_model.stat().st_size / 1024 / 1024:.1f} MB")
                        else:
                            self.add_log(f" Warning: Celestial model not found at expected location!")
            else:
                self.add_log("Training cancelled")
            
        except Exception as e:
            self.add_log(f" Training error: {str(e)}")
            traceback.print_exc()
        finally:
            with self._training_lock:
                self._is_training = False
    
    def update_learning_stats(self):
        """Update learning statistics"""
        try:
            if not self.detection_pipeline:
                return
            
            stats = self.detection_pipeline.get_learning_stats()
            auto_stats = self._get_auto_conversion_stats()
            class_counts = self._get_class_counts()
            
            pending = stats.get('pending', 0)
            accuracy = stats.get('recent_accuracy', 0)
            corrections = stats.get('total_corrections', 0)
            auto_converted = auto_stats.get('total_auto_converted', 0)
            
            self.stats_update_signal.emit(pending, accuracy, corrections, auto_converted, False, 0)
            
            # Log class distribution periodically
            if class_counts:
                total = sum(class_counts.values())
                self.add_log(f" Training data: {total} total annotations across {len([c for c in class_counts.values() if c > 0])} classes")
        except Exception as e:
            print(f"Error updating stats: {e}")
    
    def _get_pending_count(self) -> int:
        """Get pending annotation count"""
        try:
            lm = self._get_learning_manager()
            return lm.get_pending_count() if lm else 0
        except Exception:
            return 0
    
    def _get_class_counts(self) -> Dict:
        """Get class counts from learning manager"""
        try:
            lm = self._get_learning_manager()
            return lm.get_class_counts() if lm else {}
        except Exception:
            return {}
    
    def _get_auto_conversion_stats(self) -> Dict:
        """Get auto-conversion statistics"""
        try:
            lm = self._get_learning_manager()
            return lm.get_auto_conversion_stats() if lm else {}
        except Exception:
            return {}
    
    def refresh_tab(self):
        """Refresh the tab"""
        self.add_log(" Refreshing...")
        self.update_learning_stats()
        self.update_model_status()
        self.update_stream_stats()
        if self.detection_pipeline:
            self.detection_pipeline.reload_model()
    
    def on_tab_activated(self):
        """Called when tab becomes active"""
        self.add_log(" Detection tab activated")
        self.update_learning_stats()
        self.update_model_status()
        self.update_stream_stats()
    
    def on_tab_deactivated(self):
        """Called when tab becomes inactive"""
        self.add_log("Detection tab deactivated")
    
    def save_state(self) -> dict:
        """Save tab state"""
        return {
            'current_folder_index': self.current_folder_index, 
            'folder_images': self.folder_images
        }
    
    def restore_state(self, state: dict):
        """Restore tab state"""
        if state:
            self.folder_images = state.get('folder_images', [])
            self.current_folder_index = state.get('current_folder_index', -1)
    
    def clear_data(self):
        """Clear all data"""
        pass
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.add_log(" Cleaning up detection system...")
            if self.stats_timer:
                self.stats_timer.stop()
            if self.detection_pipeline:
                self.detection_pipeline.shutdown()
            self.detection_pipeline = None
            self.current_image_pixmap = None
            self.folder_images = []
            self.add_log(" Detection system cleaned up")
        except Exception as e:
            print(f"Cleanup error: {e}")