#!/usr/bin/env python3
"""
AI Chat UI Components
- Pure UI layout without business logic
- Theme-aware styling
- Language selection dropdown (EN, ZH, HI, NE)
- Model selection with 3 specialized models
- Compact layout - model and language on same line
- Added Clear Logs button
"""

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QProgressBar, QLabel, QDialog, QLineEdit, QDialogButtonBox,
    QGridLayout, QSizePolicy, QFrame, QScrollArea, QCheckBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


def rgba_color(hex_color, opacity=0.10):
    """Convert hex color to rgba with opacity for 90% transparency"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {opacity})"


def get_contrasting_color(bg_color):
    """Calculate contrasting text color (black or white)"""
    bg_color = bg_color.lstrip('#')
    if len(bg_color) == 3:
        bg_color = ''.join([c*2 for c in bg_color])
    r = int(bg_color[0:2], 16) / 255.0
    g = int(bg_color[2:4], 16) / 255.0
    b = int(bg_color[4:6], 16) / 255.0
    
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if luminance > 0.5 else "#ffffff"


# ============================================
# MODEL CONFIGURATION - 3 SPECIALIZED MODELS
# ============================================
AVAILABLE_MODELS = {
    "qwen2.5:1.5b": {
        "name": "Qwen2.5 1.5B",
        "role": "Multi-Language",
        "description": "Best for Nepali, Hindi, Chinese responses",
        "speed": "Medium (9-11 t/s)",
        "size": "986MB",
        "specialty": "multilingual",
        "emoji": "🌐"
    },
    "deepseek-r1:1.5b": {
        "name": "DeepSeek R1 1.5B",
        "role": "Deep Reasoning",
        "description": "Best for complex, detailed explanations",
        "speed": "Slow (8-10 t/s)",
        "size": "1.1GB",
        "specialty": "reasoning",
        "emoji": "🧠"
    },
    "tinyllama:latest": {
        "name": "TinyLlama",
        "role": "Quick Response",
        "description": "Best for fast, simple answers",
        "speed": "Fast (12-15 t/s)",
        "size": "636MB",
        "specialty": "quick",
        "emoji": "⚡"
    }
}

# Model priority order for display
MODEL_PRIORITY = ["qwen2.5:1.5b", "deepseek-r1:1.5b", "tinyllama:latest"]


# ============================================
# LANGUAGE CONFIGURATION
# ============================================
LANGUAGES = {
    "EN": {"name": "English", "code": "en", "instruction": "Answer in English.", "supported": True},
    "ZH": {"name": "中文", "code": "zh", "instruction": "用中文回答。", "supported": True},
    "HI": {"name": "हिन्दी", "code": "hi", "instruction": "हिंदी में उत्तर दें।", "supported": True},
    "NE": {"name": "नेपाली", "code": "ne", "instruction": "नेपालीमा जवाफ दिनुहोस्।", "supported": True},
}


class APIKeyDialog(QDialog):
    """Dialog for cloud API key input"""
    
    def __init__(self, parent=None, current_key: str = "", theme_colors=None):
        super().__init__(parent)
        self.setWindowTitle("DeepSeek Cloud API Key")
        self.setModal(True)
        self.setFixedSize(450, 150)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.api_key = current_key
        self.theme = theme_colors or {}
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Enter your DeepSeek Cloud API Key:"))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.key_input.setText(self.api_key)
        self.key_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        layout.addWidget(self.key_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def apply_theme(self):
        bg_color = self.theme.get('bg_secondary', '#1e293b')
        text_color = self.theme.get('text', '#f8fafc')
        accent = self.theme.get('accent', '#38bdf8')
        button_bg = self.theme.get('button_bg', '#2563eb')
        button_text = get_contrasting_color(button_bg)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {accent};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 11px;
                font-weight: bold;
            }}
            QLineEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {accent};
                border-radius: 4px;
                padding: 5px;
                font-size: 10px;
            }}
            QPushButton {{
                background-color: {button_bg};
                color: {button_text};
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)

    def get_api_key(self) -> str:
        return self.key_input.text().strip()


class BenchmarkDialog(QDialog):
    """Simple dialog to show benchmark results"""
    
    def __init__(self, parent=None, models=None):
        super().__init__(parent)
        self.setWindowTitle("Model Benchmark")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.models = models or []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        title = QLabel("📊 Model Performance Comparison")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Model info display
        self.model_text = QTextEdit()
        self.model_text.setReadOnly(True)
        self.model_text.setFont(QFont("Monospace", 10))
        layout.addWidget(self.model_text)
        
        # Display model information
        info_text = ""
        for model_name in MODEL_PRIORITY:
            if model_name in self.models or model_name in AVAILABLE_MODELS:
                info = AVAILABLE_MODELS.get(model_name, {})
                info_text += f"""
╔══════════════════════════════════════════════════════════════╗
║  {info.get('emoji', '📦')} {model_name}
╠══════════════════════════════════════════════════════════════╣
║  Role:        {info.get('role', 'General Purpose')}
║  Speed:       {info.get('speed', 'Unknown')}
║  Size:        {info.get('size', 'Unknown')}
║  Description: {info.get('description', 'No description')}
╚══════════════════════════════════════════════════════════════╝

"""
        
        self.model_text.setText(info_text)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedSize(100, 30)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class AIChatUI(QWidget):
    """Pure UI class for AI Chat tab - no business logic"""
    
    # Signals for user interactions
    send_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    quick_command_requested = pyqtSignal(str)
    auto_model_toggled = pyqtSignal(bool)
    model_manually_selected = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    benchmark_requested = pyqtSignal()
    clear_logs_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = {}
        self.auto_scroll = True
        self.current_language = "en"
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the complete user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # ============================================================
        # ROW 1: Model Selection, Language Selection, and Controls (ALL ON ONE LINE)
        # ============================================================
        row1 = QFrame()
        row1.setObjectName("row1")
        row1.setFixedHeight(50)
        row1.setFrameStyle(QFrame.NoFrame)
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(8, 5, 8, 5)
        row1_layout.setSpacing(8)
        
        # Model selection
        model_label = QLabel("AI Model:")
        model_label.setFont(QFont("Arial", 9, QFont.Bold))
        row1_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        self.model_combo.setFont(QFont("Arial", 9))
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        row1_layout.addWidget(self.model_combo)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedWidth(2)
        sep.setStyleSheet("background-color: rgba(255,255,255,30); margin: 2px 4px;")
        row1_layout.addWidget(sep)
        
        # Language selection
        lang_label = QLabel("Response Language:")
        lang_label.setFont(QFont("Arial", 9, QFont.Bold))
        row1_layout.addWidget(lang_label)
        
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(120)
        self.language_combo.setFont(QFont("Arial", 9))
        
        # Add language options
        for lang_key, lang_info in LANGUAGES.items():
            self.language_combo.addItem(f"{lang_key} - {lang_info['name']}", lang_info['code'])
        
        self.language_combo.setCurrentIndex(0)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        row1_layout.addWidget(self.language_combo)
        
        row1_layout.addStretch()
        
        # Auto-select toggle
        self.auto_model_cb = QCheckBox("Auto-Select")
        self.auto_model_cb.setChecked(True)
        self.auto_model_cb.setToolTip("Automatically select best model based on query")
        self.auto_model_cb.stateChanged.connect(self._on_auto_model_toggled)
        row1_layout.addWidget(self.auto_model_cb)
        
        # Benchmark button
        self.benchmark_btn = QPushButton("Benchmark")
        self.benchmark_btn.setFixedSize(80, 28)
        self.benchmark_btn.setToolTip("Compare model performance with 100 test questions")
        self.benchmark_btn.clicked.connect(self.benchmark_requested.emit)
        row1_layout.addWidget(self.benchmark_btn)
        
        # Clear Logs button
        self.clear_logs_btn = QPushButton("🗑 Clear Logs")
        self.clear_logs_btn.setFixedSize(90, 28)
        self.clear_logs_btn.setToolTip("Clear all system logs, conversation history, and benchmark results")
        self.clear_logs_btn.clicked.connect(self._on_clear_logs_clicked)
        row1_layout.addWidget(self.clear_logs_btn)
        
        main_layout.addWidget(row1)
        
        # ============================================================
        # ROW 2: AI Response Display
        # ============================================================
        row2 = QFrame()
        row2.setObjectName("row2")
        row2.setFrameStyle(QFrame.NoFrame)
        row2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        row2_layout = QVBoxLayout(row2)
        row2_layout.setContentsMargins(8, 8, 8, 8)
        row2_layout.setSpacing(5)
        
        response_header = QHBoxLayout()
        response_label = QLabel("AI Response:")
        response_label.setFont(QFont("Arial", 10, QFont.Bold))
        response_header.addWidget(response_label)
        
        response_header.addStretch()
        
        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(self.auto_scroll)
        self.auto_scroll_cb.stateChanged.connect(self._on_auto_scroll_toggled)
        self.auto_scroll_cb.setFont(QFont("Arial", 8))
        response_header.addWidget(self.auto_scroll_cb)
        
        row2_layout.addLayout(response_header)
        
        self.response_scroll = QScrollArea()
        self.response_scroll.setWidgetResizable(True)
        self.response_scroll.setFrameStyle(QFrame.NoFrame)
        
        self.ai_response_display = QTextEdit()
        self.ai_response_display.setReadOnly(True)
        self.ai_response_display.setPlaceholderText("AI responses will appear here...")
        self.ai_response_display.setFont(QFont("Arial", 10))
        self.ai_response_display.setMinimumHeight(280)
        
        self.response_scroll.setWidget(self.ai_response_display)
        row2_layout.addWidget(self.response_scroll)
        
        main_layout.addWidget(row2, 3)
        
        # ============================================================
        # ROW 3: Chat Input
        # ============================================================
        row3 = QFrame()
        row3.setObjectName("row3")
        row3.setFixedHeight(100)
        row3.setFrameStyle(QFrame.NoFrame)
        row3_layout = QHBoxLayout(row3)
        row3_layout.setContentsMargins(8, 8, 8, 8)
        row3_layout.setSpacing(8)
        
        input_container = QWidget()
        input_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(2)
        
        input_label = QLabel("Your Question:")
        input_label.setFont(QFont("Arial", 9))
        input_layout.addWidget(input_label)
        
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText(
            "Ask me anything about telescopes, astronomy, or space...\n\n"
            "Tip: Select 'Auto-Select' for intelligent model choice based on your query"
        )
        self.chat_input.setMaximumHeight(60)
        self.chat_input.setFont(QFont("Arial", 9))
        input_layout.addWidget(self.chat_input)
        
        row3_layout.addWidget(input_container, 3)
        
        button_container = QWidget()
        button_container.setFixedWidth(200)
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedHeight(35)
        self.send_btn.clicked.connect(self._on_send_clicked)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.send_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedHeight(35)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.stop_btn)
        
        row3_layout.addWidget(button_container)
        
        main_layout.addWidget(row3)
        
        # ============================================================
        # ROW 4: Quick Commands and Logs
        # ============================================================
        row4 = QFrame()
        row4.setObjectName("row4")
        row4.setFixedHeight(130)
        row4.setFrameStyle(QFrame.NoFrame)
        row4_layout = QHBoxLayout(row4)
        row4_layout.setContentsMargins(8, 5, 8, 5)
        row4_layout.setSpacing(8)
        
        # Quick Commands section
        quick_container = QFrame()
        quick_container.setObjectName("quick_container")
        quick_container.setFrameStyle(QFrame.NoFrame)
        quick_layout = QVBoxLayout(quick_container)
        quick_layout.setContentsMargins(5, 5, 5, 5)
        quick_layout.setSpacing(4)
        
        quick_title = QLabel("Quick Commands")
        quick_title.setFont(QFont("Arial", 9, QFont.Bold))
        quick_layout.addWidget(quick_title)
        
        quick_grid = QGridLayout()
        quick_grid.setSpacing(4)
        
        # Quick command buttons
        self.track_moon_btn = QPushButton("Track Moon")
        self.track_moon_btn.clicked.connect(lambda: self.quick_command_requested.emit("How to track the moon with a telescope?"))
        self.track_moon_btn.setCursor(Qt.PointingHandCursor)
        quick_grid.addWidget(self.track_moon_btn, 0, 0)
        
        self.track_sun_btn = QPushButton("Track Sun")
        self.track_sun_btn.clicked.connect(lambda: self.quick_command_requested.emit("How to safely track the sun with a telescope?"))
        self.track_sun_btn.setCursor(Qt.PointingHandCursor)
        quick_grid.addWidget(self.track_sun_btn, 0, 1)
        
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.clicked.connect(lambda: self.quick_command_requested.emit("How do I calibrate my telescope motors?"))
        self.calibrate_btn.setCursor(Qt.PointingHandCursor)
        quick_grid.addWidget(self.calibrate_btn, 1, 0)
        
        self.align_btn = QPushButton("Star Align")
        self.align_btn.clicked.connect(lambda: self.quick_command_requested.emit("How to perform star alignment for telescope?"))
        self.align_btn.setCursor(Qt.PointingHandCursor)
        quick_grid.addWidget(self.align_btn, 1, 1)
        
        quick_layout.addLayout(quick_grid)
        quick_layout.addStretch()
        
        row4_layout.addWidget(quick_container, 40)
        
        # System Logs section
        logs_container = QFrame()
        logs_container.setObjectName("logs_container")
        logs_container.setFrameStyle(QFrame.NoFrame)
        logs_layout = QVBoxLayout(logs_container)
        logs_layout.setContentsMargins(5, 5, 5, 5)
        logs_layout.setSpacing(4)
        
        logs_title = QLabel("System Logs")
        logs_title.setFont(QFont("Arial", 9, QFont.Bold))
        logs_layout.addWidget(logs_title)
        
        self.ai_log_display = QTextEdit()
        self.ai_log_display.setReadOnly(True)
        self.ai_log_display.setPlaceholderText("Logs will appear here...")
        self.ai_log_display.setFont(QFont("Monospace", 8))
        self.ai_log_display.setMaximumHeight(70)
        logs_layout.addWidget(self.ai_log_display)
        
        # Progress bar
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(15)
        progress_layout.addWidget(self.progress_bar)
        logs_layout.addLayout(progress_layout)
        
        row4_layout.addWidget(logs_container, 60)
        
        main_layout.addWidget(row4)
    
    def update_model_combo(self, models: list, current_model: str = None):
        """Update the model combo box with available models"""
        self.model_combo.clear()
        
        # Add our priority models first (if available)
        for model_name in MODEL_PRIORITY:
            if model_name in models:
                info = AVAILABLE_MODELS.get(model_name, {})
                display_name = f"{info.get('emoji', '')} {model_name} - {info.get('role', 'General')}"
                self.model_combo.addItem(display_name, model_name)
        
        # Add other available models
        for model_name in models:
            if model_name not in MODEL_PRIORITY:
                self.model_combo.addItem(f"📦 {model_name}", model_name)
        
        # Set current model
        if current_model and current_model in models:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == current_model:
                    self.model_combo.setCurrentIndex(i)
                    break
    
    def _on_send_clicked(self):
        prompt = self.chat_input.toPlainText().strip()
        if prompt:
            self.send_requested.emit(prompt)
    
    def _on_auto_model_toggled(self, state):
        is_checked = (state == Qt.Checked)
        self.auto_model_cb.setChecked(is_checked)
        self.auto_model_toggled.emit(is_checked)
        self.model_combo.setEnabled(not is_checked)
    
    def _on_auto_scroll_toggled(self, state):
        self.auto_scroll = (state == Qt.Checked)
    
    def _on_model_selected(self, text):
        if not self.auto_model_cb.isChecked():
            model_name = self.model_combo.currentData()
            if model_name:
                self.model_manually_selected.emit(model_name)
    
    def _on_language_changed(self, index):
        language_code = self.language_combo.itemData(index)
        self.current_language = language_code
        self.language_changed.emit(language_code)
    
    def _on_clear_logs_clicked(self):
        """Handle clear logs button click"""
        self.clear_logs_requested.emit()
    
    def set_response_text(self, text: str):
        """Set the AI response display text"""
        self.ai_response_display.setText(text)
    
    def clear_response(self):
        """Clear the AI response display"""
        self.ai_response_display.clear()
    
    def add_log(self, message: str):
        """Add a log message to the log display"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.ai_log_display.append(log_entry)
        scroll_bar = self.ai_log_display.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
    
    def set_progress(self, value: int):
        """Set progress bar value"""
        self.progress_bar.setValue(value)
    
    def set_send_enabled(self, enabled: bool):
        """Enable/disable send button"""
        self.send_btn.setEnabled(enabled)
    
    def set_stop_enabled(self, enabled: bool):
        """Enable/disable stop button"""
        self.stop_btn.setEnabled(enabled)
    
    def get_prompt(self) -> str:
        """Get the current prompt text and clear it"""
        prompt = self.chat_input.toPlainText().strip()
        if prompt:
            self.chat_input.clear()
        return prompt
    
    def get_auto_scroll(self) -> bool:
        return self.auto_scroll
    
    def scroll_to_bottom(self):
        scrollbar = self.ai_response_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def apply_theme(self, theme_colors: dict):
        """Apply theme colors to the UI"""
        self.theme = theme_colors
        
        bg_color = theme_colors.get('bg', '#0f172a')
        bg_secondary = theme_colors.get('bg_secondary', '#1e293b')
        text_color = theme_colors.get('text', '#f8fafc')
        accent = theme_colors.get('accent', '#38bdf8')
        button_bg = theme_colors.get('button_bg', '#2563eb')
        
        row_bg = rgba_color(bg_secondary, 0.10)
        container_bg = rgba_color(bg_secondary, 0.10)
        
        send_button_text = get_contrasting_color("#10b981")
        stop_button_text = get_contrasting_color("#ef4444")
        button_text = get_contrasting_color(button_bg)
        
        stylesheet = f"""
            QWidget {{
                background-color: transparent;
                color: {text_color};
                font-family: 'Arial', sans-serif;
            }}
            
            QFrame#row1, QFrame#row2, QFrame#row3, QFrame#row4 {{
                background-color: {row_bg};
                border: none;
                border-radius: 6px;
            }}
            
            QFrame#quick_container, QFrame#logs_container {{
                background-color: {container_bg};
                border: none;
                border-radius: 4px;
            }}
            
            QLabel {{
                color: {text_color};
                background-color: transparent;
                border: none;
                padding: 2px;
            }}
            
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            
            QTextEdit {{
                background-color: {rgba_color(bg_color, 0.20)};
                color: {text_color};
                border: 1px solid {accent};
                border-radius: 4px;
                padding: 6px;
                font-size: 10px;
            }}
            
            QCheckBox {{
                color: {text_color};
                font-size: 8px;
                spacing: 4px;
            }}
            
            QCheckBox::indicator {{
                width: 12px;
                height: 12px;
            }}
            
            QCheckBox::indicator:unchecked {{
                border: 1px solid {accent};
                background: transparent;
            }}
            
            QCheckBox::indicator:checked {{
                border: 1px solid {accent};
                background: {accent};
            }}
            
            QComboBox {{
                background-color: {rgba_color(bg_color, 0.30)};
                color: {text_color};
                border: 1px solid {accent};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9px;
            }}
            
            QComboBox::drop-down {{
                border: none;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {bg_secondary};
                color: {text_color};
                border: 1px solid {accent};
                selection-background-color: {accent};
                selection-color: {bg_color};
            }}
            
            QPushButton {{
                background-color: {button_bg};
                color: {button_text};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 9px;
            }}
            
            QPushButton:hover {{
                opacity: 0.8;
            }}
            
            QPushButton#send_btn, QPushButton.send_btn {{
                background-color: #10b981;
                color: {send_button_text};
            }}
            
            QPushButton#stop_btn, QPushButton.stop_btn {{
                background-color: #ef4444;
                color: {stop_button_text};
            }}
            
            QProgressBar {{
                background-color: {rgba_color(bg_color, 0.20)};
                border-radius: 3px;
                text-align: center;
                color: {text_color};
                font-size: 8px;
                border: none;
            }}
            
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 3px;
            }}
        """
        
        self.setStyleSheet(stylesheet)
        self.send_btn.setObjectName("send_btn")
        self.stop_btn.setObjectName("stop_btn")