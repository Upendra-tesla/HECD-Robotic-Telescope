# File: tabs/detect/image_train/training/training_dialog.py

from datetime import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QProgressBar, QTextEdit, QGroupBox,
                             QSpinBox, QComboBox, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .training_worker import TrainingWorker


class TrainingDialog(QDialog):
    """Dialog for training configuration and monitoring - RESIZED for 850x570 main window"""
    
    def __init__(self, learning_manager, detection_pipeline, theme_manager, parent=None):
        super().__init__(parent)
        self.learning_manager = learning_manager
        self.detection_pipeline = detection_pipeline
        self.theme_manager = theme_manager
        self.training_worker = None
        
        self.setWindowTitle("Celestial Model Training")
        self.setModal(True)
        self.setMinimumSize(500, 450)  # Reduced to fit within 850x570 main window
        self.setMaximumSize(650, 520)   # Max size to ensure it fits
        self.resize(550, 480)           # Default size
        
        self.setup_ui()
        self.update_dataset_stats()
        
        if theme_manager:
            self.apply_theme()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Dataset stats - COMPACT
        stats_group = QGroupBox("Dataset Statistics")
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(3)
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet("font-size: 9px;")
        stats_layout.addWidget(self.stats_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Class distribution - COMPACT
        class_group = QGroupBox("Class Distribution")
        class_layout = QVBoxLayout()
        class_layout.setSpacing(3)
        self.class_label = QLabel()
        self.class_label.setWordWrap(True)
        self.class_label.setStyleSheet("font-size: 8px; font-family: monospace;")
        class_layout.addWidget(self.class_label)
        class_group.setLayout(class_layout)
        layout.addWidget(class_group)
        
        # Training parameters - COMPACT
        params_group = QGroupBox("Training Parameters")
        params_layout = QVBoxLayout()
        params_layout.setSpacing(5)
        
        # Epochs row
        epochs_layout = QHBoxLayout()
        epochs_layout.addWidget(QLabel("Epochs:"))
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(10, 200)
        self.epochs_spin.setValue(50)
        self.epochs_spin.setToolTip("More epochs = better accuracy, but slower training")
        epochs_layout.addWidget(self.epochs_spin)
        epochs_layout.addStretch()
        params_layout.addLayout(epochs_layout)
        
        # Image size row
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Image Size:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["320", "416", "512", "640"])
        self.size_combo.setCurrentText("640")
        self.size_combo.setToolTip("Larger = better accuracy, but more memory")
        size_layout.addWidget(self.size_combo)
        size_layout.addWidget(QLabel("px"))
        size_layout.addStretch()
        params_layout.addLayout(size_layout)
        
        # Batch size row
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("Batch Size:"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 16)
        self.batch_spin.setValue(4)  # Reduced default for lower memory usage
        self.batch_spin.setToolTip("Higher = faster training, but needs more RAM")
        batch_layout.addWidget(self.batch_spin)
        batch_layout.addStretch()
        params_layout.addLayout(batch_layout)
        
        # Device row
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu"])
        # Only add cuda if available (detect at runtime)
        try:
            import torch
            if torch.cuda.is_available():
                self.device_combo.addItem("cuda")
        except:
            pass
        device_layout.addWidget(self.device_combo)
        device_layout.addStretch()
        params_layout.addLayout(device_layout)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # Training progress - COMPACT
        progress_group = QGroupBox("Training Progress")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(15)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to start training")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 9px;")
        progress_layout.addWidget(self.status_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(120)  # Reduced height
        self.log_display.setFont(QFont("Monospace", 8))
        progress_layout.addWidget(self.log_display)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Buttons - COMPACT
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.start_btn = QPushButton("Start Training")
        self.start_btn.clicked.connect(self.start_training)
        self.start_btn.setMinimumHeight(30)
        self.start_btn.setMinimumWidth(100)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_training)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(30)
        self.stop_btn.setMinimumWidth(80)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setMinimumHeight(30)
        self.close_btn.setMinimumWidth(80)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def update_dataset_stats(self):
        """Update dataset statistics display"""
        stats = self.learning_manager.get_dataset_stats()
        pending = self.learning_manager.get_pending_count()
        class_counts = self.learning_manager.get_class_counts()
        
        total_images = stats['total']
        total_labels = stats['train_labels'] + stats['val_labels']
        
        stats_text = f" Total: {total_images} images | Labels: {total_labels} | Pending: {pending}"
        self.stats_label.setText(stats_text)
        
        # Show class distribution - compact format
        class_text = ""
        for cls, count in class_counts.items():
            if count > 0:
                bar = "#" * min(count, 10)
                class_text += f"{cls[:3]} {bar} {count}  "
        
        if not class_text:
            class_text = "No annotations yet. Use Annotation Wizard to add training data."
        
        self.class_label.setText(class_text)
    
    def start_training(self):
        """Start training process"""
        if self.training_worker and self.training_worker.isRunning():
            return
        
        pending = self.learning_manager.get_pending_count()
        total_images = sum(self.learning_manager.get_class_counts().values())
        
        if total_images < 10:
            reply = QMessageBox.warning(
                self, 
                "Insufficient Data",
                f"Only {total_images} images available.\n\n"
                "Recommended minimum: 50 images.\n"
                "Training with limited data may produce poor results.\n\n"
                "Continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        epochs = self.epochs_spin.value()
        image_size = int(self.size_combo.currentText())
        batch_size = self.batch_spin.value()
        device = self.device_combo.currentText()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Training in progress... This may take several minutes.")
        
        self.training_worker = TrainingWorker(
            self.learning_manager,
            epochs, image_size, batch_size, device
        )
        self.training_worker.progress_signal.connect(self.on_progress)
        self.training_worker.finished_signal.connect(self.on_finished)
        self.training_worker.start()
        
        self.add_log(f" Started training: epochs={epochs}, size={image_size}, batch={batch_size}, device={device}")
    
    def stop_training(self):
        """Stop training process"""
        if self.training_worker and self.training_worker.isRunning():
            self.training_worker.stop()
            self.add_log(" Training stop requested...")
            self.status_label.setText("Stopping training...")
    
    def on_progress(self, progress, message):
        """Handle training progress updates"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
        self.add_log(message)
    
    def on_finished(self, success, model_path):
        """Handle training completion"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if success:
            self.add_log(f" Training completed successfully!")
            self.add_log(f"   Model saved to: {model_path}")
            self.status_label.setText("Training completed successfully!")
            self.update_dataset_stats()
            QMessageBox.information(
                self,
                "Training Complete",
                f"Celestial model training completed!\n\nModel saved to:\n{model_path}\n\nYou can now use the Detection tab with the new model."
            )
        else:
            self.add_log(f" Training failed: {model_path}")
            self.status_label.setText("Training failed - see log for details")
            QMessageBox.critical(
                self,
                "Training Failed",
                f"Training failed:\n{model_path}\n\nCheck the log for details."
            )
    
    def add_log(self, message):
        """Add message to log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def apply_theme(self):
        """Apply theme to dialog"""
        if not self.theme_manager:
            return
            
        try:
            if hasattr(self.theme_manager, 'get_colors'):
                theme = self.theme_manager.get_colors()
            else:
                theme = {}
            
            bg = theme.get('bg', '#0f172a')
            bg_secondary = theme.get('bg_secondary', '#1e293b')
            text = theme.get('text', '#f8fafc')
            accent = theme.get('accent', '#38bdf8')
            
            self.setStyleSheet(f"""
                QDialog {{
                    background-color: {bg};
                    color: {text};
                }}
                QGroupBox {{
                    color: {accent};
                    border: 1px solid {accent};
                    border-radius: 5px;
                    margin-top: 8px;
                    font-size: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px;
                }}
                QLabel {{ 
                    color: {text};
                    font-size: 9px;
                }}
                QSpinBox, QComboBox {{
                    background-color: {bg_secondary};
                    color: {text};
                    border: 1px solid {accent};
                    border-radius: 4px;
                    padding: 3px;
                    font-size: 9px;
                }}
                QPushButton {{
                    background-color: {accent};
                    color: {bg};
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 9px;
                }}
                QPushButton:hover {{
                    opacity: 0.8;
                }}
                QPushButton:disabled {{ opacity: 0.5; }}
                QProgressBar {{
                    background-color: {bg_secondary};
                    border: 1px solid {accent};
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {accent};
                    border-radius: 3px;
                }}
                QTextEdit {{
                    background-color: {bg_secondary};
                    color: {text};
                    border: 1px solid {accent};
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 8px;
                }}
            """)
        except Exception as e:
            print(f"Theme application error: {e}")