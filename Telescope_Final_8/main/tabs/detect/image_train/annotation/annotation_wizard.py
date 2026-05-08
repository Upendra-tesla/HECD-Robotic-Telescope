# File: tabs/detect/image_train/annotation/annotation_wizard.py

from PyQt5.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QTextEdit, QPushButton,
                             QGroupBox, QRadioButton, QButtonGroup, QMessageBox,
                             QFrame, QScrollArea, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
import traceback
import sys
import os


class DrawableImageLabel(QLabel):
    """Custom QLabel that allows drawing bounding boxes"""
    
    box_drawn = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(250)
        self.setStyleSheet("border: 2px solid #555; border-radius: 8px; background-color: rgba(0,0,0,0.3);")
        
        # Drawing state
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.original_pixmap = None
        self.display_pixmap = None
        self.current_box = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.drawn_boxes = []
        self._is_valid = True
        
    def is_valid(self):
        try:
            return not self.isHidden() and self is not None
        except (RuntimeError, AttributeError):
            return False
        
    def set_image(self, pixmap):
        if not self.is_valid() or pixmap is None:
            return
        self.original_pixmap = pixmap
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
        
        # Calculate scaling factors
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        disp_w = self.display_pixmap.width()
        disp_h = self.display_pixmap.height()
        self.scale_x = orig_w / disp_w if disp_w > 0 else 1
        self.scale_y = orig_h / disp_h if disp_h > 0 else 1
        
        # Make a copy for drawing
        display_copy = self.display_pixmap.copy()
        painter = QPainter(display_copy)
        
        # Draw all saved boxes
        pen = QPen(QColor(0, 255, 0), 3)
        painter.setPen(pen)
        for box in self.drawn_boxes:
            painter.drawRect(box['x'], box['y'], box['w'], box['h'])
        
        # Draw current drawing box
        if self.current_box:
            pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.current_box)
        
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
            
            x = min(self.start_point[0], self.end_point[0])
            y = min(self.start_point[1], self.end_point[1])
            w = abs(self.end_point[0] - self.start_point[0])
            h = abs(self.end_point[1] - self.start_point[1])
            
            self.current_box = QRect(int(x), int(y), int(w), int(h))
            self.update_display()
    
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
                # Convert to normalized coordinates for YOLO
                norm_x = (x + w/2) / self.display_pixmap.width()
                norm_y = (y + h/2) / self.display_pixmap.height()
                norm_w = w / self.display_pixmap.width()
                norm_h = h / self.display_pixmap.height()
                
                # Store drawn box for display
                self.drawn_boxes.append({'x': x, 'y': y, 'w': w, 'h': h})
                
                # Emit signal with normalized coordinates
                self.box_drawn.emit({
                    'x_center': norm_x,
                    'y_center': norm_y,
                    'width': norm_w,
                    'height': norm_h
                })
            
            self.current_box = None
            self.update_display()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.update_display)
    
    def clear_boxes(self):
        self.drawn_boxes = []
        self.update_display()
    
    def closeEvent(self, event):
        self._is_valid = False
        self.original_pixmap = None
        self.display_pixmap = None
        super().closeEvent(event)


class AnnotationWizard(QWizard):
    """4-step wizard for manual annotation"""
    
    def __init__(self, image_path, pixmap, detection_pipeline, theme_manager, parent=None, pre_drawn_box=None):
        super().__init__(parent)
        
        # Store references
        self.image_path = image_path
        self.original_pixmap = pixmap
        self.detection_pipeline = detection_pipeline
        self.theme_manager = theme_manager
        
        # Get learning manager safely from pipeline
        self.learning_manager = None
        if detection_pipeline:
            if hasattr(detection_pipeline, 'learning_manager'):
                self.learning_manager = detection_pipeline.learning_manager
            elif hasattr(detection_pipeline, '_get_learning_manager'):
                self.learning_manager = detection_pipeline._get_learning_manager()
        
        # Set window properties
        self.setWindowTitle("Annotation Wizard")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(650, 500)
        self.setMaximumSize(750, 550)
        self.setModal(True)
        
        # Remove help button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # Annotation data
        self.annotation_data = {
            'bbox': pre_drawn_box,
            'class_name': None,
            'features': {},
            'confidence': 100
        }
        
        # Store page references
        self.box_page = None
        self.class_page = None
        self.confidence_page = None
        self.review_page = None
        
        # Add pages
        self._create_pages()
        
        # Apply theme if available
        if theme_manager:
            QTimer.singleShot(10, self.apply_theme)
        
        self.setAttribute(Qt.WA_DeleteOnClose, True)
    
    def _create_pages(self):
        self.box_page = BoxDrawingPage(self)
        self.class_page = ClassPage(self)
        self.confidence_page = ConfidencePage(self)
        self.review_page = ReviewPage(self)
        
        self.addPage(self.box_page)
        self.addPage(self.class_page)
        self.addPage(self.confidence_page)
        self.addPage(self.review_page)
    
    def apply_theme(self):
        try:
            if not self.theme_manager:
                return
            
            if hasattr(self.theme_manager, 'get_colors'):
                colors = self.theme_manager.get_colors()
            elif hasattr(self.theme_manager, 'get_current_colors'):
                colors = self.theme_manager.get_current_colors()
            else:
                colors = {}
            
            bg = colors.get('bg', '#1e1e2e')
            bg_secondary = colors.get('bg_secondary', '#2d2d3d')
            text = colors.get('text', '#ffffff')
            text_secondary = colors.get('text_secondary', '#a0a0a0')
            accent = colors.get('accent', '#89b4fa')
            button_bg = colors.get('button_bg', '#89b4fa')
            border = colors.get('border', '#444444')
            
            def rgba(color, opacity=0.3):
                color = color.lstrip('#')
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                return f"rgba({r}, {g}, {b}, {opacity})"
            
            self.setStyleSheet(f"""
                QWizard {{
                    background-color: {bg};
                    color: {text};
                }}
                QWizardPage {{
                    background-color: {bg};
                }}
                QLabel {{
                    color: {text};
                    background-color: transparent;
                }}
                QTextEdit {{
                    background-color: {bg_secondary};
                    color: {text};
                    border: 1px solid {accent};
                    border-radius: 4px;
                }}
                QSlider::groove:horizontal {{
                    border: 1px solid {accent};
                    height: 6px;
                    background: {bg_secondary};
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    background: {accent};
                    width: 14px;
                    margin: -4px 0;
                    border-radius: 7px;
                }}
                QPushButton {{
                    background-color: {button_bg};
                    color: {bg};
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {accent};
                }}
                QGroupBox {{
                    color: {accent};
                    border: 1px solid {border};
                    border-radius: 5px;
                    margin-top: 8px;
                }}
                QFrame {{
                    background-color: {rgba(bg_secondary, 0.3)};
                    border: 1px solid {border};
                    border-radius: 5px;
                }}
                QScrollArea {{
                    background-color: transparent;
                    border: none;
                }}
                QScrollBar:vertical {{
                    background-color: {bg_secondary};
                    width: 8px;
                    border-radius: 4px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: {accent};
                    border-radius: 4px;
                    min-height: 20px;
                }}
                QRadioButton {{
                    color: {text};
                    background-color: transparent;
                    spacing: 8px;
                    font-size: 10px;
                    padding: 3px;
                }}
                QRadioButton:hover {{
                    background-color: {rgba(accent, 0.15)};
                    border-radius: 4px;
                }}
                QRadioButton::indicator {{
                    width: 14px;
                    height: 14px;
                    border-radius: 7px;
                }}
                QRadioButton::indicator:unchecked {{
                    border: 2px solid {accent};
                    background-color: transparent;
                }}
                QRadioButton::indicator:checked {{
                    border: 2px solid {accent};
                    background-color: {accent};
                }}
            """)
            
            print("Annotation Wizard theme applied")
            
        except Exception as e:
            print(f"Theme application error: {e}")
    
    def closeEvent(self, event):
        try:
            self.learning_manager = None
            self.detection_pipeline = None
            self.theme_manager = None
            self.original_pixmap = None
            event.accept()
        except Exception as e:
            print(f"Close event error: {e}")
            event.accept()


class BoxDrawingPage(QWizardPage):
    """Step 1: Draw bounding box"""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Step 1: Draw Bounding Box")
        self.setSubTitle("Click and drag to draw a rectangle around the celestial object")
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        instructions = QLabel("Click and drag on the image to draw a bounding box around the object.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 6px; background-color: rgba(0,0,0,0.5); border-radius: 4px;")
        layout.addWidget(instructions)
        
        self.image_draw = DrawableImageLabel()
        if wizard.original_pixmap:
            self.image_draw.set_image(wizard.original_pixmap)
        self.image_draw.box_drawn.connect(self.on_box_drawn)
        layout.addWidget(self.image_draw)
        
        self.status_label = QLabel("No box drawn. Click and drag on the image above.")
        self.status_label.setStyleSheet("padding: 3px;")
        layout.addWidget(self.status_label)
        
        clear_btn = QPushButton("Clear Box")
        clear_btn.setFixedHeight(25)
        clear_btn.clicked.connect(self.clear_box)
        layout.addWidget(clear_btn)
        
        self.setLayout(layout)
    
    def on_box_drawn(self, box_data):
        self.wizard.annotation_data['bbox'] = box_data
        self.status_label.setText("Bounding box drawn successfully!")
        self.status_label.setStyleSheet("padding: 3px; color: #4CAF50;")
    
    def clear_box(self):
        self.wizard.annotation_data['bbox'] = None
        self.image_draw.clear_boxes()
        self.status_label.setText("Box cleared. Draw a new box.")
        self.status_label.setStyleSheet("padding: 3px; color: #FF9800;")
    
    def validatePage(self):
        if self.wizard.annotation_data['bbox'] is None:
            reply = QMessageBox.question(
                self, "No Bounding Box",
                "No bounding box drawn. Continue with default center box?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False
            else:
                self.wizard.annotation_data['bbox'] = {
                    'x_center': 0.5, 'y_center': 0.5,
                    'width': 0.6, 'height': 0.6
                }
        return True
    
    def initializePage(self):
        if self.wizard.original_pixmap:
            self.image_draw.set_image(self.wizard.original_pixmap)


class ClassPage(QWizardPage):
    """Step 2: Class selection"""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Step 2: Object Class")
        self.setSubTitle("Select the celestial object type")
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        class_label = QLabel("Select the type of celestial object:")
        class_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(class_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        radio_container = QWidget()
        radio_container.setAutoFillBackground(False)
        radio_container.setStyleSheet("background-color: transparent;")
        
        radio_layout = QVBoxLayout(radio_container)
        radio_layout.setSpacing(6)
        radio_layout.setContentsMargins(5, 5, 5, 5)
        
        self.class_button_group = QButtonGroup(self)
        
        class_options = [
            ("Sun", "Our local star - extremely bright, round, yellow/white appearance"),
            ("Moon", "Earth's natural satellite - gray, cratered surface, visible phases"),
            ("Planet", "Planetary body - round, steady light, may show bands or rings"),
            ("Galaxy", "Collection of stars - diffuse, spiral or elliptical structure"),
            ("Nebula", "Cloud of gas and dust - diffuse, often colorful"),
            ("Comet", "Icy body with tail - diffuse head, may show tail"),
            ("Asteroid", "Rocky body - point-like, moves relative to stars"),
            ("Star", "Distant sun - point source, may twinkle, shows color")
        ]
        
        self.radio_buttons = []
        
        for i, (name, description) in enumerate(class_options):
            radio_btn = QRadioButton(name)
            radio_btn.setToolTip(description)
            radio_btn.setCursor(Qt.PointingHandCursor)
            
            radio_btn.setProperty("class_name", name.lower())
            radio_btn.setProperty("description", description)
            
            radio_btn.toggled.connect(lambda checked, btn=radio_btn: self.update_description_from_button(btn))
            
            self.class_button_group.addButton(radio_btn, i)
            radio_layout.addWidget(radio_btn)
            self.radio_buttons.append(radio_btn)
        
        radio_layout.addStretch()
        scroll_area.setWidget(radio_container)
        layout.addWidget(scroll_area)
        
        self.desc_frame = QFrame()
        self.desc_frame.setStyleSheet("""
            background-color: rgba(0,0,0,0.3);
            border-radius: 6px;
            padding: 6px;
        """)
        desc_layout = QVBoxLayout(self.desc_frame)
        desc_layout.setSpacing(4)
        
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setStyleSheet("font-size: 10px; background-color: transparent;")
        desc_layout.addWidget(self.desc_label)
        
        layout.addWidget(self.desc_frame)
        
        if self.radio_buttons:
            self.radio_buttons[0].setChecked(True)
        
        self.setLayout(layout)
    
    def update_description_from_button(self, radio_button):
        if radio_button.isChecked():
            description = radio_button.property("description")
            self.desc_label.setText(description)
    
    def validatePage(self):
        checked_button = self.class_button_group.checkedButton()
        if checked_button:
            class_name = checked_button.property("class_name")
            self.wizard.annotation_data['class_name'] = class_name
            print(f"DEBUG: Selected class: {class_name}")
            return True
        else:
            QMessageBox.warning(self, "No Selection", "Please select a celestial object type.")
            return False


class ConfidencePage(QWizardPage):
    """Step 3: Confidence rating"""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Step 3: Confidence Rating")
        self.setSubTitle("Rate your confidence in this annotation")
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        layout.addWidget(QLabel("How confident are you about this annotation?"))
        
        self.confidence_slider = QSlider(Qt.Horizontal)
        self.confidence_slider.setRange(0, 100)
        self.confidence_slider.setValue(100)
        self.confidence_slider.setTickPosition(QSlider.TicksBelow)
        self.confidence_slider.setTickInterval(10)
        layout.addWidget(self.confidence_slider)
        
        self.confidence_label = QLabel("Confidence: 100%")
        self.confidence_label.setAlignment(Qt.AlignCenter)
        self.confidence_slider.valueChanged.connect(
            lambda v: self.confidence_label.setText(f"Confidence: {v}%")
        )
        layout.addWidget(self.confidence_label)
        
        self.confidence_bar = QFrame()
        self.confidence_bar.setFixedHeight(8)
        self.confidence_slider.valueChanged.connect(self.update_bar)
        layout.addWidget(self.confidence_bar)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def update_bar(self, value):
        if value >= 70:
            color = "#4CAF50"
        elif value >= 40:
            color = "#FF9800"
        else:
            color = "#F44336"
        self.confidence_bar.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
    
    def validatePage(self):
        self.wizard.annotation_data['confidence'] = self.confidence_slider.value()
        print(f"DEBUG: Confidence set to: {self.confidence_slider.value()}%")
        return True


class ReviewPage(QWizardPage):
    """Step 4: Review and submit"""
    
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self.setTitle("Step 4: Review and Submit")
        self.setSubTitle("Review your annotation before saving")
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        self.review_card = QFrame()
        card_layout = QVBoxLayout(self.review_card)
        
        self.review_text = QLabel()
        self.review_text.setWordWrap(True)
        self.review_text.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.review_text)
        
        layout.addWidget(self.review_card)
        
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def initializePage(self):
        data = self.wizard.annotation_data
        bbox = data.get('bbox', {})
        
        review_text = f"""
        ANNOTATION SUMMARY
        =================
        Class: {data['class_name'].capitalize() if data['class_name'] else 'Unknown'}
        Confidence: {data['confidence']}%
        Bounding Box:
          Center: ({bbox.get('x_center', 0.5):.2f}, {bbox.get('y_center', 0.5):.2f})
          Size: {bbox.get('width', 0.6):.2f} x {bbox.get('height', 0.6):.2f}
        """
        self.review_text.setText(review_text)
        
        if data['confidence'] < 70:
            self.warning_label.setText("Warning: Low confidence annotation. Consider reviewing this annotation.")
        else:
            self.warning_label.setText("Ready to save annotation.")
    
    def validatePage(self):
        """Save annotation to learning manager"""
        try:
            # Get learning manager from wizard - try multiple sources
            learning_manager = self.wizard.learning_manager
            
            # If learning_manager is None, try to get it from detection_pipeline
            if learning_manager is None and self.wizard.detection_pipeline:
                if hasattr(self.wizard.detection_pipeline, 'learning_manager'):
                    learning_manager = self.wizard.detection_pipeline.learning_manager
                    self.wizard.learning_manager = learning_manager
                elif hasattr(self.wizard.detection_pipeline, '_get_learning_manager'):
                    learning_manager = self.wizard.detection_pipeline._get_learning_manager()
                    self.wizard.learning_manager = learning_manager
            
            # Check if learning manager is available
            if not learning_manager:
                error_msg = "Learning manager not available!\n\nPlease ensure the detection pipeline is initialized properly."
                QMessageBox.critical(self, "Error", error_msg)
                print("ERROR: No learning manager available")
                return False
            
            # Check if class name is selected
            if not self.wizard.annotation_data['class_name']:
                QMessageBox.warning(self, "Error", "No class selected!")
                return False
            
            # Check if image path exists
            if not self.wizard.image_path or not os.path.exists(self.wizard.image_path):
                QMessageBox.critical(self, "Error", f"Image file not found: {self.wizard.image_path}")
                return False
            
            # Get the bounding box
            bbox = self.wizard.annotation_data['bbox']
            if not bbox:
                QMessageBox.warning(self, "Error", "No bounding box defined!")
                return False
            
            # Add the annotation
            print(f"DEBUG: Saving annotation - Class: {self.wizard.annotation_data['class_name']}")
            print(f"DEBUG: BBox: {bbox}")
            print(f"DEBUG: Image: {self.wizard.image_path}")
            
            success = learning_manager.add_annotation(
                self.wizard.image_path,
                self.wizard.annotation_data['class_name'],
                bbox,
                self.wizard.annotation_data.get('features', {}),
                self.wizard.annotation_data['confidence']
            )
            
            if success:
                print("DEBUG: Annotation saved successfully!")
                if self.wizard.detection_pipeline:
                    self.wizard.detection_pipeline.get_learning_stats()
                QMessageBox.information(self, "Success", "Annotation saved successfully!")
                return True
            else:
                QMessageBox.warning(self, "Error", "Failed to save annotation - duplicate or error")
                return False
                
        except Exception as e:
            print(f"Error saving annotation: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save annotation: {str(e)}")
            return False