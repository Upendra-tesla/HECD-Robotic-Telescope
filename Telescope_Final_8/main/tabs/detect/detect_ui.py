# File: tabs/detect/detect_ui.py - Complete UI with Stream Performance Display
# UPDATED: Support for three specialized models with source tracking

import sys
import os
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QApplication, QMessageBox, QFileDialog, QGroupBox, QProgressBar,
    QTextEdit, QScrollArea, QRadioButton, QButtonGroup, QDialog,
    QSplitter, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter, QPen, QColor, QBrush, QPalette


def safe_set_text(widget, text):
    """Safely set text on a widget"""
    try:
        if widget and not widget.isHidden():
            widget.setText(text)
            return True
    except (RuntimeError, AttributeError):
        pass
    return False


class ImageDisplayLabel(QLabel):
    """Custom QLabel for image display with bounding box drawing"""
    
    box_drawn = pyqtSignal(object)
    
    BOX_COLORS = {
        'sun': QColor(255, 100, 0),
        'moon': QColor(200, 200, 200),
        'planet': QColor(100, 150, 255),
        'jupiter': QColor(200, 100, 50),
        'saturn': QColor(200, 180, 100),
        'mars': QColor(255, 80, 80),
        'galaxy': QColor(200, 100, 255),
        'nebula': QColor(255, 100, 200),
        'comet': QColor(100, 255, 200),
        'asteroid': QColor(150, 150, 150),
        'star': QColor(255, 255, 100),
        'star_cluster': QColor(255, 200, 100),
        'star_field': QColor(255, 200, 100),
        'supernova': QColor(255, 50, 50),
        'aurora': QColor(100, 255, 100),
        'meteor': QColor(255, 150, 50),
        'satellite': QColor(150, 150, 200),
        'clouds': QColor(200, 200, 200),
        'airplane': QColor(200, 200, 100),
        'bird': QColor(100, 100, 100),
        'other': QColor(150, 150, 150),
        'unknown': QColor(150, 150, 150),
    }
    DEFAULT_COLOR = QColor(0, 255, 0)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(400)
        self.setStyleSheet("border: 2px solid #555; border-radius: 8px; background-color: rgba(0,0,0,0.3);")
        
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.current_rect = None
        self.original_pixmap = None
        self.display_pixmap = None
        self.display_image = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.original_size = (0, 0)
        self.detected_boxes = []
        self._is_valid = True
        
    def is_valid(self):
        try:
            return not self.isHidden() and self is not None
        except (RuntimeError, AttributeError):
            return False
    
    @staticmethod
    def get_contrast_color(rgb_color):
        r, g, b = rgb_color
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return QColor(255, 255, 255) if luminance < 0.5 else QColor(0, 0, 0)
    
    @classmethod
    def get_box_color(cls, label):
        label_lower = label.lower().replace(' ', '_') if label else 'unknown'
        return cls.BOX_COLORS.get(label_lower, cls.DEFAULT_COLOR)
        
    def set_image(self, pixmap, detected_boxes=None):
        if not self.is_valid() or pixmap is None:
            return
        self.original_pixmap = pixmap
        self.detected_boxes = detected_boxes or []
        QTimer.singleShot(10, self.update_display)
        
    def update_display(self):
        if not self.is_valid() or self.original_pixmap is None:
            return
            
        widget_size = self.size()
        if widget_size.width() <= 0 or widget_size.height() <= 0:
            return
            
        self.display_pixmap = self.original_pixmap.scaled(
            widget_size.width() - 20,
            widget_size.height() - 20,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        if self.display_pixmap is None:
            return
            
        self.display_image = self.display_pixmap.toImage()
        
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        disp_w = self.display_pixmap.width()
        disp_h = self.display_pixmap.height()
        self.scale_x = orig_w / disp_w if disp_w > 0 else 1
        self.scale_y = orig_h / disp_h if disp_h > 0 else 1
        self.original_size = (orig_w, orig_h)
        
        display_copy = self.display_pixmap.copy()
        painter = QPainter(display_copy)
        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)
        
        for box in self.detected_boxes:
            x = box.get('x', 0) / self.scale_x
            y = box.get('y', 0) / self.scale_y
            w = box.get('w', 0) / self.scale_x
            h = box.get('h', 0) / self.scale_y
            
            label = box.get('label', 'Unknown')
            confidence = box.get('confidence', 0)
            box_color = self.get_box_color(label)
            
            pen = QPen(box_color, 3)
            painter.setPen(pen)
            painter.drawRect(int(x), int(y), int(w), int(h))
            
            label_text = f"{label.upper()} ({confidence:.0%})"
            text_rect = painter.fontMetrics().boundingRect(label_text)
            text_width = text_rect.width() + 10
            text_height = text_rect.height() + 6
            
            text_x = int(x)
            text_y = int(y) - 5
            if text_y - text_height < 0:
                text_y = int(y) + 5
            
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(text_x, text_y - text_height + 5, text_width, text_height)
            
            sample_x = min(text_x + 5, self.display_image.width() - 1)
            sample_y = min(text_y - text_height + 10, self.display_image.height() - 1)
            sample_x = max(0, sample_x)
            sample_y = max(0, sample_y)
            
            if sample_x < self.display_image.width() and sample_y < self.display_image.height():
                pixel_color = self.display_image.pixelColor(sample_x, sample_y)
                text_color = self.get_contrast_color((pixel_color.red(), pixel_color.green(), pixel_color.blue()))
            else:
                text_color = QColor(255, 255, 255)
            
            painter.setPen(QPen(text_color, 1))
            painter.drawText(text_x + 5, text_y, label_text)
        
        painter.end()
        
        try:
            self.setPixmap(display_copy)
        except (RuntimeError, AttributeError):
            pass
        
    def mousePressEvent(self, event):
        if not self.is_valid():
            return
        if event.button() == Qt.LeftButton and self.display_pixmap:
            self.drawing = True
            offset_x = (self.width() - self.display_pixmap.width()) // 2
            offset_y = (self.height() - self.display_pixmap.height()) // 2
            self.start_point = (event.pos().x() - offset_x, event.pos().y() - offset_y)
            self.end_point = self.start_point
            
    def mouseMoveEvent(self, event):
        if not self.is_valid():
            return
        if self.drawing and self.display_pixmap:
            offset_x = (self.width() - self.display_pixmap.width()) // 2
            offset_y = (self.height() - self.display_pixmap.height()) // 2
            self.end_point = (event.pos().x() - offset_x, event.pos().y() - offset_y)
            
            temp_pixmap = self.display_pixmap.copy()
            painter = QPainter(temp_pixmap)
            pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)
            painter.setPen(pen)
            
            x = min(self.start_point[0], self.end_point[0])
            y = min(self.start_point[1], self.end_point[1])
            w = abs(self.end_point[0] - self.start_point[0])
            h = abs(self.end_point[1] - self.start_point[1])
            painter.drawRect(int(x), int(y), int(w), int(h))
            painter.end()
            
            try:
                self.setPixmap(temp_pixmap)
            except (RuntimeError, AttributeError):
                pass
            
    def mouseReleaseEvent(self, event):
        if not self.is_valid():
            return
        if self.drawing and self.display_pixmap and self.start_point and self.end_point:
            self.drawing = False
            
            x = min(self.start_point[0], self.end_point[0])
            y = min(self.start_point[1], self.end_point[1])
            w = abs(self.end_point[0] - self.start_point[0])
            h = abs(self.end_point[1] - self.start_point[1])
            
            if w > 10 and h > 10:
                norm_x = (x + w/2) / self.display_pixmap.width()
                norm_y = (y + h/2) / self.display_pixmap.height()
                norm_w = w / self.display_pixmap.width()
                norm_h = h / self.display_pixmap.height()
                
                self.box_drawn.emit({
                    'x_center': norm_x,
                    'y_center': norm_y,
                    'width': norm_w,
                    'height': norm_h,
                    'original_size': self.original_size
                })
            
            self.update_display()
            
    def resizeEvent(self, event):
        if not self.is_valid():
            return
        super().resizeEvent(event)
        QTimer.singleShot(50, self.update_display)
    
    def closeEvent(self, event):
        self._is_valid = False
        self.original_pixmap = None
        self.display_pixmap = None
        self.detected_boxes = []
        try:
            self.box_drawn.disconnect()
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)
    
    def deleteLater(self):
        self._is_valid = False
        self.original_pixmap = None
        self.display_pixmap = None
        self.detected_boxes = []
        super().deleteLater()


class DetectTabUI(QWidget):
    """Detection Tab UI - Text-only buttons with Stream Performance Display"""
    
    BUTTON_COLORS = {
        'blue': "#2196F3", 'blue_hover': "#1976D2",
        'green': "#4CAF50", 'green_hover': "#45a049",
        'red': "#F44336", 'red_hover': "#D32F2F",
        'orange': "#FF9800", 'orange_hover': "#F57C00",
        'yellow': "#FFC107", 'yellow_hover': "#FFB300",
        'purple': "#9C27B0", 'purple_hover': "#7B1FA2",
        'teal': "#009688", 'teal_hover': "#00796B",
        'accent': "#89b4fa"
    }
    
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setObjectName("TabContent")
        
        self.controller = controller
        self.language_manager = None
        self.theme_manager = None
        self.current_theme = None
        
        # UI references
        self.image_display = None
        self.load_image_btn = None
        self.load_folder_btn = None
        self.refresh_btn = None
        self.prev_btn = None
        self.next_btn = None
        self.image_counter_label = None
        self.detect_btn = None
        self.correct_btn = None
        self.incorrect_btn = None
        self.annotate_btn = None
        self.auto_train_btn = None
        self.force_train_btn = None
        self.detected_label = None
        self.confidence_label = None
        
        # Stream display labels
        self.classical_stream_label = None
        self.ml_stream_label = None
        self.rule_stream_label = None
        self.voting_label = None
        self.quality_label = None
        self.specialized_label = None
        self.stream_stats_label = None
        self.weights_label = None
        
        self.model_status_label = None
        self.pending_label = None
        self.accuracy_label = None
        self.corrections_label = None
        self.training_status_label = None
        self.auto_converted_label = None
        self.training_progress = None
        self.log_display = None
        
        self.setup_ui()
        self.apply_default_button_colors()
    
    def setup_ui(self):
        """Setup the complete UI layout"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
    
    def _create_left_panel(self):
        """Create left panel with image display"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        action_layout = QHBoxLayout()
        self.load_image_btn = QPushButton("Load Image")
        self.load_image_btn.setMinimumHeight(36)
        self.load_folder_btn = QPushButton("Load Folder")
        self.load_folder_btn.setMinimumHeight(36)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMinimumHeight(36)
        
        action_layout.addStretch()
        action_layout.addWidget(self.load_image_btn)
        action_layout.addWidget(self.load_folder_btn)
        action_layout.addWidget(self.refresh_btn)
        action_layout.addStretch()
        
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setEnabled(False)
        self.next_btn = QPushButton("Next")
        self.next_btn.setEnabled(False)
        self.image_counter_label = QLabel("No image")
        self.image_counter_label.setAlignment(Qt.AlignCenter)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.image_counter_label)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addStretch()
        
        self.image_display = ImageDisplayLabel()
        
        self.detect_btn = QPushButton("Run Detection")
        self.detect_btn.setMinimumHeight(45)
        
        layout.addLayout(action_layout)
        layout.addLayout(nav_layout)
        layout.addWidget(self.image_display, 1)
        layout.addWidget(self.detect_btn)
        
        return panel
    
    def _create_right_panel(self):
        """Create right panel with controls and stream performance"""
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setStyleSheet("border: none;")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # ============================================================
        # DETECTION RESULTS - SHOW ALL THREE STREAMS
        # ============================================================
        results_group = QGroupBox("Detection Results")
        results_layout = QVBoxLayout()
        results_layout.setSpacing(8)
        
        # Main detected object
        main_result_layout = QHBoxLayout()
        self.detected_label = QLabel("Detected: --")
        self.detected_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.confidence_label = QLabel("Confidence: --")
        self.confidence_label.setStyleSheet("font-size: 12px;")
        main_result_layout.addWidget(self.detected_label)
        main_result_layout.addWidget(self.confidence_label)
        main_result_layout.addStretch()
        results_layout.addLayout(main_result_layout)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background-color: #475569; max-height: 1px; margin: 5px 0;")
        results_layout.addWidget(sep)
        
        # THREE STREAMS DISPLAY
        streams_title = QLabel("Detection Streams:")
        streams_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #fca311;")
        results_layout.addWidget(streams_title)
        
        # Stream 1: Classical
        classical_layout = QHBoxLayout()
        classical_label = QLabel("🔬 Classical:")
        classical_label.setStyleSheet("font-size: 10px; font-weight: bold; min-width: 70px;")
        self.classical_stream_label = QLabel("--")
        self.classical_stream_label.setStyleSheet("font-size: 10px;")
        classical_layout.addWidget(classical_label)
        classical_layout.addWidget(self.classical_stream_label)
        classical_layout.addStretch()
        results_layout.addLayout(classical_layout)
        
        # Stream 2: ML (Multi-model)
        ml_layout = QHBoxLayout()
        ml_label = QLabel("🤖 ML:")
        ml_label.setStyleSheet("font-size: 10px; font-weight: bold; min-width: 70px; color: #10b981;")
        self.ml_stream_label = QLabel("--")
        self.ml_stream_label.setStyleSheet("font-size: 10px; color: #10b981;")
        ml_layout.addWidget(ml_label)
        ml_layout.addWidget(self.ml_stream_label)
        ml_layout.addStretch()
        results_layout.addLayout(ml_layout)
        
        # Stream 3: Rule-Based
        rule_layout = QHBoxLayout()
        rule_label = QLabel("📏 Rule-Based:")
        rule_label.setStyleSheet("font-size: 10px; font-weight: bold; min-width: 70px;")
        self.rule_stream_label = QLabel("--")
        self.rule_stream_label.setStyleSheet("font-size: 10px;")
        rule_layout.addWidget(rule_label)
        rule_layout.addWidget(self.rule_stream_label)
        rule_layout.addStretch()
        results_layout.addLayout(rule_layout)
        
        # Voting result
        voting_layout = QHBoxLayout()
        voting_label = QLabel("⚖️ Voting:")
        voting_label.setStyleSheet("font-size: 10px; font-weight: bold; min-width: 70px;")
        self.voting_label = QLabel("--")
        self.voting_label.setStyleSheet("font-size: 10px;")
        voting_layout.addWidget(voting_label)
        voting_layout.addWidget(self.voting_label)
        voting_layout.addStretch()
        results_layout.addLayout(voting_layout)
        
        # Quality
        quality_layout = QHBoxLayout()
        quality_label = QLabel("📷 Quality:")
        quality_label.setStyleSheet("font-size: 10px; font-weight: bold; min-width: 70px;")
        self.quality_label = QLabel("--")
        self.quality_label.setStyleSheet("font-size: 10px;")
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_label)
        quality_layout.addStretch()
        results_layout.addLayout(quality_layout)
        
        # Specialized info
        self.specialized_label = QLabel("")
        self.specialized_label.setWordWrap(True)
        self.specialized_label.setStyleSheet("font-size: 9px; color: #94a3b8; margin-top: 5px;")
        results_layout.addWidget(self.specialized_label)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # ============================================================
        # STREAM PERFORMANCE STATS
        # ============================================================
        stats_group = QGroupBox("Stream Performance")
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(5)
        
        self.stream_stats_label = QLabel("🔬 Classical: -- | 🤖 ML: -- | 📏 Rule: --")
        self.stream_stats_label.setWordWrap(True)
        self.stream_stats_label.setStyleSheet("font-size: 9px; font-family: monospace;")
        stats_layout.addWidget(self.stream_stats_label)
        
        self.weights_label = QLabel("Adaptive Weights: 🔬-- | 🤖-- | 📏--")
        self.weights_label.setStyleSheet("font-size: 8px; color: #64748b;")
        stats_layout.addWidget(self.weights_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Model Status (updated to show all three models)
        model_group = QGroupBox("Model Status")
        model_layout = QVBoxLayout()
        self.model_status_label = QLabel("Loading model status...")
        self.model_status_label.setWordWrap(True)
        self.model_status_label.setMinimumHeight(80)
        model_layout.addWidget(self.model_status_label)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Training Controls
        training_group = QGroupBox("Training Controls")
        training_layout = QHBoxLayout()
        self.auto_train_btn = QPushButton("Auto Training")
        self.force_train_btn = QPushButton("Force Training")
        training_layout.addWidget(self.auto_train_btn)
        training_layout.addWidget(self.force_train_btn)
        training_group.setLayout(training_layout)
        layout.addWidget(training_group)
        
        # Feedback
        feedback_group = QGroupBox("Feedback")
        feedback_layout = QHBoxLayout()
        self.correct_btn = QPushButton("Correct")
        self.correct_btn.setEnabled(False)
        self.incorrect_btn = QPushButton("Incorrect")
        self.incorrect_btn.setEnabled(False)
        self.annotate_btn = QPushButton("Annotate")
        self.annotate_btn.setEnabled(False)
        feedback_layout.addWidget(self.correct_btn)
        feedback_layout.addWidget(self.incorrect_btn)
        feedback_layout.addWidget(self.annotate_btn)
        feedback_group.setLayout(feedback_layout)
        layout.addWidget(feedback_group)
        
        # Learning Statistics
        learning_group = QGroupBox("Learning Statistics")
        learning_layout = QVBoxLayout()
        
        stats_row1 = QHBoxLayout()
        self.pending_label = QLabel("Pending: 0")
        self.accuracy_label = QLabel("Accuracy: --")
        stats_row1.addWidget(self.pending_label)
        stats_row1.addWidget(self.accuracy_label)
        stats_row1.addStretch()
        
        stats_row2 = QHBoxLayout()
        self.corrections_label = QLabel("Corrections: 0")
        self.training_status_label = QLabel("Training: Idle")
        stats_row2.addWidget(self.corrections_label)
        stats_row2.addWidget(self.training_status_label)
        stats_row2.addStretch()
        
        stats_row3 = QHBoxLayout()
        self.auto_converted_label = QLabel("Auto-converted: 0")
        stats_row3.addWidget(self.auto_converted_label)
        stats_row3.addStretch()
        
        self.training_progress = QProgressBar()
        self.training_progress.setVisible(False)
        self.training_progress.setFixedHeight(6)
        
        learning_layout.addLayout(stats_row1)
        learning_layout.addLayout(stats_row2)
        learning_layout.addLayout(stats_row3)
        learning_layout.addWidget(self.training_progress)
        learning_group.setLayout(learning_layout)
        layout.addWidget(learning_group)
        
        # System Log
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(120)
        self.log_display.setFont(QFont("Monospace", 9))
        log_layout.addWidget(self.log_display)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        panel.setWidget(container)
        return panel
    
    def update_stream_stats_display(self, stream_stats: dict):
        """Update the stream statistics display"""
        if not stream_stats:
            return
        
        classical = stream_stats.get('classical', {})
        ml = stream_stats.get('ml', {})
        rule = stream_stats.get('rule_based', {})
        
        # Format main stats
        classical_text = f"🔬 Classical: {classical.get('accuracy', 0):.0%} ({classical.get('correct', 0)}/{classical.get('total', 0)})"
        ml_text = f"🤖 ML: {ml.get('accuracy', 0):.0%} ({ml.get('correct', 0)}/{ml.get('total', 0)})"
        rule_text = f"📏 Rule: {rule.get('accuracy', 0):.0%} ({rule.get('correct', 0)}/{rule.get('total', 0)})"
        
        # Color code based on accuracy
        if ml.get('accuracy', 0) > 0.6:
            ml_text = f"🟢 {ml_text}"
        elif ml.get('accuracy', 0) > 0.4:
            ml_text = f"🟡 {ml_text}"
        else:
            ml_text = f"🔴 {ml_text}"
        
        safe_set_text(self.stream_stats_label, f"{classical_text} | {ml_text} | {rule_text}")
        
        # Update weights display
        weights_text = f"Adaptive Weights: 🔬{classical.get('weight', 0):.2f} | 🤖{ml.get('weight', 0):.2f} | 📏{rule.get('weight', 0):.2f}"
        safe_set_text(self.weights_label, weights_text)
    
    def apply_default_button_colors(self):
        """Apply default colors to buttons"""
        colors = self.BUTTON_COLORS
        
        for btn in [self.load_image_btn, self.load_folder_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {colors['blue']}; color: white; border: none;
                    border-radius: 5px; padding: 8px 16px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {colors['blue_hover']}; }}
                QPushButton:disabled {{ background-color: #555555; }}
            """)
        
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['green']}; color: white; border: none;
                border-radius: 5px; padding: 8px 16px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {colors['green_hover']}; }}
        """)
        
        self.detect_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['red']}; color: white; border: none;
                border-radius: 5px; padding: 10px 20px; font-weight: bold; font-size: 14px; }}
            QPushButton:hover {{ background-color: {colors['red_hover']}; }}
            QPushButton:disabled {{ background-color: #555555; }}
        """)
        
        for btn in [self.correct_btn, self.incorrect_btn, self.annotate_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {colors['purple']}; color: white; border: none;
                    border-radius: 5px; padding: 6px 12px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {colors['purple_hover']}; }}
                QPushButton:disabled {{ background-color: #555555; }}
            """)
        
        for btn in [self.auto_train_btn, self.force_train_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {colors['orange']}; color: white; border: none;
                    border-radius: 5px; padding: 6px 12px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {colors['orange_hover']}; }}
            """)
        
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['teal']}; color: white; border: none;
                border-radius: 5px; padding: 8px 16px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {colors['teal_hover']}; }}
        """)
        
        self.next_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['teal']}; color: white; border: none;
                border-radius: 5px; padding: 8px 16px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {colors['teal_hover']}; }}
        """)
    
    def set_managers(self, language_manager, theme_manager):
        """Set language and theme managers"""
        self.language_manager = language_manager
        self.theme_manager = theme_manager
    
    def apply_theme(self, theme):
        """Apply theme colors"""
        self.current_theme = theme
    
    def apply_language(self, language, tab_content):
        """Apply language settings"""
        safe_set_text(self.load_image_btn, "Load Image")
        safe_set_text(self.load_folder_btn, "Load Folder")
        safe_set_text(self.refresh_btn, "Refresh")
        safe_set_text(self.detect_btn, "Run Detection")
        safe_set_text(self.auto_train_btn, "Auto Training")
        safe_set_text(self.force_train_btn, "Force Training")
        safe_set_text(self.correct_btn, "Correct")
        safe_set_text(self.incorrect_btn, "Incorrect")
        safe_set_text(self.annotate_btn, "Annotate")
    
    def add_log(self, message):
        """Add log message"""
        if not self.log_display:
            return
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_detection_results(self, detected_object, confidence, voting_result, 
                                quality, streams_text, specialized_text, source=None):
        """Update detection results with model source tracking"""
        
        # Main result with source emoji
        source_emoji = {
            'celestial': '🌟',
            'cosmica': '🚀',
            'sun_moon': '☀️',
            'classical': '🔬',
            'rule_based': '📏'
        }.get(source, '🤖')
        
        if detected_object.upper() == 'UNKNOWN' or confidence < 0.4:
            safe_set_text(self.detected_label, f"Detected: Unknown")
            safe_set_text(self.confidence_label, f"Confidence: {confidence:.1%} (Low)")
            self.detected_label.setStyleSheet("color: #FF9800; font-size: 14px; font-weight: bold;")
            self.confidence_label.setStyleSheet("color: #FF9800; font-size: 12px;")
        else:
            safe_set_text(self.detected_label, f"Detected: {source_emoji} {detected_object.upper()}")
            safe_set_text(self.confidence_label, f"Confidence: {confidence:.1%}")
            self.detected_label.setStyleSheet("color: #10b981; font-size: 14px; font-weight: bold;")
            self.confidence_label.setStyleSheet("color: #10b981; font-size: 12px;")
        
        # Parse and display individual streams
        if streams_text and streams_text != "--":
            parts = streams_text.split(" | ")
            for part in parts:
                if "Classical:" in part:
                    value = part.replace("Classical:", "").strip()
                    safe_set_text(self.classical_stream_label, value)
                    if "unknown" not in value.lower():
                        self.classical_stream_label.setStyleSheet("font-size: 10px; color: #f59e0b;")
                    else:
                        self.classical_stream_label.setStyleSheet("font-size: 10px; color: #64748b;")
                elif "ML:" in part:
                    value = part.replace("ML:", "").strip()
                    safe_set_text(self.ml_stream_label, value)
                    # Style based on which model detected
                    if source == 'cosmica':
                        self.ml_stream_label.setStyleSheet("font-size: 10px; color: #10b981; font-weight: bold;")
                    elif source == 'sun_moon':
                        self.ml_stream_label.setStyleSheet("font-size: 10px; color: #38bdf8; font-weight: bold;")
                    elif source == 'celestial':
                        self.ml_stream_label.setStyleSheet("font-size: 10px; color: #a855f7; font-weight: bold;")
                    else:
                        self.ml_stream_label.setStyleSheet("font-size: 10px; color: #10b981;")
                elif "Rule-Based:" in part or "Rule:" in part:
                    value = part.replace("Rule-Based:", "").replace("Rule:", "").strip()
                    safe_set_text(self.rule_stream_label, value)
                    if "unknown" not in value.lower():
                        self.rule_stream_label.setStyleSheet("font-size: 10px; color: #a855f7;")
                    else:
                        self.rule_stream_label.setStyleSheet("font-size: 10px; color: #64748b;")
        else:
            safe_set_text(self.classical_stream_label, "--")
            safe_set_text(self.ml_stream_label, "--")
            safe_set_text(self.rule_stream_label, "--")
        
        safe_set_text(self.voting_label, voting_result)
        safe_set_text(self.quality_label, quality)
        safe_set_text(self.specialized_label, specialized_text)
    
    def update_model_status_display(self, status_text):
        """Update model status with multi-line support for three models"""
        safe_set_text(self.model_status_label, status_text)
        # Adjust label height based on content
        lines = status_text.count('\n') + 1
        new_height = 70 + (lines - 3) * 14 if lines > 3 else 70
        self.model_status_label.setMinimumHeight(new_height)
    
    def update_learning_stats_display(self, pending, accuracy, corrections, auto_converted, is_training, progress):
        """Update learning stats"""
        safe_set_text(self.pending_label, f"Pending: {pending}")
        safe_set_text(self.accuracy_label, f"Accuracy: {accuracy:.1%}")
        safe_set_text(self.corrections_label, f"Corrections: {corrections}")
        safe_set_text(self.auto_converted_label, f"Auto-converted: {auto_converted}")
        
        if is_training:
            safe_set_text(self.training_status_label, "Training: In progress...")
            self.training_progress.setVisible(True)
            self.training_progress.setValue(progress)
        else:
            safe_set_text(self.training_status_label, "Training: Idle")
            self.training_progress.setVisible(False)
    
    def enable_feedback_buttons(self, enabled=True):
        """Enable/disable feedback buttons"""
        self.correct_btn.setEnabled(enabled)
        self.incorrect_btn.setEnabled(enabled)
        if enabled:
            self.annotate_btn.setEnabled(True)
    
    def set_detection_button_state(self, detecting=False):
        """Set detection button state"""
        if detecting:
            safe_set_text(self.detect_btn, "Detecting...")
            self.detect_btn.setEnabled(False)
        else:
            safe_set_text(self.detect_btn, "Run Detection")
            self.detect_btn.setEnabled(True)
    
    def set_image_display(self, pixmap, detected_boxes=None):
        """Update image display"""
        if self.image_display:
            self.image_display.set_image(pixmap, detected_boxes or [])
    
    def clear_detection_results(self):
        """Clear detection results"""
        safe_set_text(self.detected_label, "Detected: --")
        safe_set_text(self.confidence_label, "Confidence: --")
        safe_set_text(self.voting_label, "Voting: --")
        safe_set_text(self.quality_label, "Quality: --")
        safe_set_text(self.classical_stream_label, "--")
        safe_set_text(self.ml_stream_label, "--")
        safe_set_text(self.rule_stream_label, "--")
        safe_set_text(self.specialized_label, "")
        self.enable_feedback_buttons(False)
    
    def update_image_counter(self, current, total):
        """Update image counter"""
        if total > 0:
            safe_set_text(self.image_counter_label, f"Image {current} of {total}")
        else:
            safe_set_text(self.image_counter_label, "Single image")
    
    def set_navigation_buttons(self, prev_enabled, next_enabled):
        """Set navigation button states"""
        self.prev_btn.setEnabled(prev_enabled)
        self.next_btn.setEnabled(next_enabled)
    
    def get_image_display(self):
        """Get image display widget"""
        return self.image_display
    
    def get_current_image_pixmap(self):
        """Get current image pixmap"""
        return self.image_display.original_pixmap if self.image_display else None
    
    def closeEvent(self, event):
        """Handle close event"""
        print("DEBUG: DetectTabUI closing...")
        if hasattr(self, 'controller') and self.controller:
            self.controller.cleanup()
        super().closeEvent(event)