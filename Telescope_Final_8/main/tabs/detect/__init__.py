# tabs/detect/__init__.py
"""Detection Tab Module - AI-powered celestial object detection with continuous learning"""

import os
import sys
import traceback
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the same directory - use relative imports
from .detect_ui import DetectTabUI
from .detect_controller import DetectionController


class DetectTab(DetectTabUI):
    """Main Detection Tab - Thin wrapper combining UI and Controller with proper cleanup"""
    
    def __init__(self, parent=None):
        # Initialize UI FIRST - pass None as controller initially
        super().__init__(None, parent)
        
        try:
            # Create controller
            self.controller = DetectionController(self)
            
            # Set controller reference in UI
            self.controller_ref = self.controller
            
            # Set up logging
            self._setup_logging()
            
            # Connect controller callbacks
            self.controller.set_callbacks(
                log_callback=self.add_log,
                stats_callback=self.update_learning_stats_display,
                model_status_callback=self.update_model_status_display
            )
            
            # Connect UI signals to controller
            self._connect_controller_signals()
            
            # Connect box drawn signal from image display
            self._connect_box_drawn_signal()
            
            # Initialize pipeline after UI is ready
            QTimer.singleShot(500, self._init_pipeline)
            
            print("DEBUG: DetectTab initialized successfully")
            
        except Exception as e:
            print(f"ERROR initializing DetectTab: {e}")
            traceback.print_exc()
            self.controller = None
    
    def _setup_logging(self):
        """Setup logging for the tab"""
        try:
            self.add_log("=" * 50)
            self.add_log("🔭 Detection Tab Ready")
            self.add_log("=" * 50)
        except:
            pass
    
    def _init_pipeline(self):
        """Initialize detection pipeline"""
        if self.controller:
            try:
                self.controller.init_detection_pipeline()
            except Exception as e:
                print(f"Pipeline init error: {e}")
    
    def _connect_controller_signals(self):
        """Connect UI signals to controller methods"""
        if not self.controller:
            print("DEBUG: No controller to connect signals to")
            return
        
        # Disconnect existing signals first (safe)
        self._safe_disconnect_all()
        
        try:
            # Connect buttons
            self.load_image_btn.clicked.connect(self.controller.load_image)
            self.load_folder_btn.clicked.connect(self.controller.load_folder)
            self.refresh_btn.clicked.connect(self.controller.refresh_tab)
            self.prev_btn.clicked.connect(self.controller.prev_image)
            self.next_btn.clicked.connect(self.controller.next_image)
            self.detect_btn.clicked.connect(self.controller.run_detection)
            self.correct_btn.clicked.connect(lambda: self.controller.provide_feedback(True))
            self.incorrect_btn.clicked.connect(lambda: self.controller.provide_feedback(False))
            self.annotate_btn.clicked.connect(self.controller.open_annotation_wizard)
            self.auto_train_btn.clicked.connect(self.controller.trigger_auto_training)
            self.force_train_btn.clicked.connect(self.controller.force_training)
            
            print("DEBUG: All button signals connected successfully")
            
        except Exception as e:
            print(f"Error connecting signals: {e}")
            traceback.print_exc()
    
    def _connect_box_drawn_signal(self):
        """Connect box drawn signal safely"""
        if self.image_display and self.controller:
            try:
                self.image_display.box_drawn.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.image_display.box_drawn.connect(self.controller.on_box_drawn)
            print("DEBUG: Box drawn signal connected")
    
    def _safe_disconnect_all(self):
        """Safely disconnect all signals from buttons"""
        buttons = [
            self.load_image_btn, self.load_folder_btn, self.refresh_btn,
            self.prev_btn, self.next_btn, self.detect_btn, self.correct_btn,
            self.incorrect_btn, self.annotate_btn, self.auto_train_btn,
            self.force_train_btn
        ]
        
        for btn in buttons:
            if btn:
                try:
                    btn.clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass
                except Exception as e:
                    print(f"Error disconnecting {btn}: {e}")
    
    def set_managers(self, language_manager, theme_manager):
        """Set managers from main window"""
        self.language_manager = language_manager
        self.theme_manager = theme_manager
        if self.controller:
            self.controller.set_managers(language_manager, theme_manager)
        if theme_manager:
            self.apply_theme(theme_manager.get_current_theme())
    
    def on_tab_activated(self):
        """Called when tab becomes active - RECONNECT SIGNALS"""
        print("DEBUG: DetectTab activated - reconnecting signals")
        # Reconnect signals when tab becomes active
        if self.controller:
            self._connect_controller_signals()
            self._connect_box_drawn_signal()
            try:
                self.controller.on_tab_activated()
            except Exception as e:
                print(f"Tab activation error: {e}")
        self._refresh_theme_colors()
    
    def on_tab_deactivated(self):
        """Called when tab becomes inactive"""
        if self.controller:
            try:
                self.controller.on_tab_deactivated()
            except Exception as e:
                print(f"Tab deactivation error: {e}")
    
    def save_state(self) -> dict:
        """Save tab state"""
        if self.controller:
            try:
                return self.controller.save_state()
            except:
                return {}
        return {}
    
    def restore_state(self, state: dict):
        """Restore tab state"""
        if self.controller:
            try:
                self.controller.restore_state(state)
            except:
                pass
    
    def clear_data(self):
        """Clear all data"""
        if self.controller:
            try:
                self.controller.clear_data()
            except:
                pass
    
    def update_texts(self, translation_manager):
        """Update all translatable texts"""
        if self.controller and self.controller.language_manager:
            self.apply_language(self.controller.language_manager.get_current_language(), None)
    
    def on_box_drawn(self, box_data):
        """Handle box drawn on image"""
        if self.controller:
            self.controller.on_box_drawn(box_data)
    
    def _refresh_theme_colors(self):
        """Refresh theme colors"""
        if self.theme_manager and self.controller:
            try:
                self.controller.apply_theme(self.theme_manager.get_current_theme())
            except:
                pass
    
    def closeEvent(self, event):
        """Handle close event"""
        print("DEBUG: DetectTab closing...")
        
        try:
            self._safe_disconnect_all()
            
            if self.image_display:
                try:
                    self.image_display.box_drawn.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.image_display.deleteLater()
            
            if self.controller:
                self.controller.cleanup()
                self.controller = None
            
            print("DEBUG: DetectTab closed successfully")
        except Exception as e:
            print(f"DEBUG: Error during close: {e}")
        
        super().closeEvent(event)


__all__ = ['DetectTab']