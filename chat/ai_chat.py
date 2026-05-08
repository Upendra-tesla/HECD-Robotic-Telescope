#!/usr/bin/env python3
"""
AI Chat Tab for Telescope Control System
"""

import sys
import os
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox, QVBoxLayout, QProgressBar, QPushButton, QDialog, QTextEdit
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

# Add parent directories to path
CURRENT_FILE = os.path.abspath(__file__)
CURRENT_DIR = os.path.dirname(CURRENT_FILE)
CHAT_DIR = CURRENT_DIR
TABS_DIR = os.path.dirname(CHAT_DIR)
MAIN_DIR = os.path.dirname(TABS_DIR)
CONFIG_DIR = os.path.join(MAIN_DIR, "config")
CHAT_LOGS_DIR = os.path.join(CHAT_DIR, "chat_logs")

for path in [CONFIG_DIR, MAIN_DIR, TABS_DIR, CHAT_LOGS_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import UI and Features
from tabs.chat.ai_chat_ui import AIChatUI, LANGUAGES, AVAILABLE_MODELS, MODEL_PRIORITY
from tabs.chat.ai_chat_features import AIChatFeatures
from tabs.chat.chat_logs.chat_logger import chat_logger
from tabs.chat.chat_logs.benchmark_manager import BenchmarkManager, BenchmarkWorker, benchmark_manager

try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False
    class FallbackThemeManager:
        def get_current_theme(self): return "Dark"
        def get_colors(self): return {"bg": "#0f172a", "bg_secondary": "#1e293b", "text": "#f8fafc"}
    theme_manager = FallbackThemeManager()


class AIChatTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.theme = theme_manager.get_colors()
        self.current_theme = theme_manager.get_current_theme()
        
        # Create UI and Features
        self.ui = AIChatUI(self)
        self.features = AIChatFeatures(self)
        
        # Setup layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.ui)
        
        # Add installation progress bar (hidden initially)
        self.install_progress = QProgressBar()
        self.install_progress.setVisible(False)
        self.install_progress.setFixedHeight(20)
        layout.addWidget(self.install_progress)
        
        # Benchmark worker
        self.benchmark_worker = None
        self.benchmark_dialog = None
        
        # Connect signals
        self._connect_signals()
        self._connect_features_signals()
        self._connect_ui_signals()
        
        # Apply initial theme
        self.ui.apply_theme(self.theme)
        
        # Progress animation timer
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._animate_progress)
        self.progress_value = 0
        self.progress_timer.start(200)
        
        # Connect to global theme manager
        if THEME_AVAILABLE and hasattr(theme_manager, 'theme_changed'):
            theme_manager.theme_changed.connect(self.on_theme_changed)
        
        # Auto-scroll handling
        self.ui.ai_response_display.verticalScrollBar().valueChanged.connect(
            self._on_response_scroll
        )
    
    def _connect_ui_signals(self):
        """Connect UI signals"""
        self.ui.clear_logs_requested.connect(self._on_clear_logs)
    
    def _on_clear_logs(self):
        """Handle clear logs button click"""
        reply = QMessageBox.question(
            self,
            "Clear Logs",
            "Are you sure you want to clear ALL logs?\n\n"
            "This will delete:\n"
            "• All system logs\n"
            "• All conversation history\n"
            "• All benchmark results\n\n"
            "This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if chat_logger.clear_all_logs():
                benchmark_manager.clear_benchmark()
                self.ui.add_log("🗑 All logs cleared successfully")
                QMessageBox.information(self, "Success", "All logs have been cleared!")
            else:
                self.ui.add_log("❌ Failed to clear logs")
                QMessageBox.warning(self, "Error", "Failed to clear logs")
    
    def _connect_signals(self):
        self.ui.send_requested.connect(self._on_send_query)
        self.ui.stop_requested.connect(self.features.stop_query)
        self.ui.quick_command_requested.connect(self._on_quick_command)
        self.ui.auto_model_toggled.connect(self.features.set_auto_select)
        self.ui.model_manually_selected.connect(self._on_model_selected)
        self.ui.language_changed.connect(self._on_language_changed)
        self.ui.benchmark_requested.connect(self._run_benchmark)
    
    def _connect_features_signals(self):
        self.features.log_signal.connect(self.ui.add_log)
        self.features.response_signal.connect(self._display_response)
        self.features.error_signal.connect(self._display_error)
        self.features.progress_signal.connect(self.ui.set_progress)
        self.features.model_list_signal.connect(self._update_model_list)
    
    def _run_benchmark(self):
        """Run the full benchmark test - NON-MODAL so tab stays open"""
        # Check if Ollama is running
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code != 200:
                QMessageBox.warning(self, "Ollama Not Running", 
                                   "Ollama is not running. Please start Ollama first:\n\nollama serve")
                return
        except:
            QMessageBox.warning(self, "Ollama Not Running", 
                               "Cannot connect to Ollama. Please start Ollama first:\n\nollama serve")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Run Benchmark",
            "This will test all AI models with 100 questions.\n\n"
            "Estimated time: 20-30 minutes\n"
            "Models to test:\n"
            "  • qwen2.5:1.5b\n"
            "  • deepseek-r1:1.5b (may take 2-3 minutes per question first time)\n"
            "  • tinyllama:latest\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Create progress dialog (NON-MODAL so tab stays open)
        self.benchmark_dialog = QDialog(self)
        self.benchmark_dialog.setWindowTitle("Model Benchmark - Running...")
        self.benchmark_dialog.setModal(False)  # ← NON-MODAL!
        self.benchmark_dialog.setMinimumSize(650, 450)
        self.benchmark_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        
        dialog_layout = QVBoxLayout(self.benchmark_dialog)
        
        # Progress bar
        self.benchmark_progress = QProgressBar()
        self.benchmark_progress.setRange(0, 100)
        self.benchmark_progress.setValue(0)
        dialog_layout.addWidget(self.benchmark_progress)
        
        # Status display
        self.benchmark_status = QTextEdit()
        self.benchmark_status.setReadOnly(True)
        self.benchmark_status.setFont(QFont("Monospace", 9))
        dialog_layout.addWidget(self.benchmark_status)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel Benchmark")
        cancel_btn.clicked.connect(self._cancel_benchmark)
        dialog_layout.addWidget(cancel_btn)
        
        self.benchmark_dialog.show()
        
        # Start benchmark
        self.benchmark_worker = BenchmarkWorker()
        self.benchmark_worker.progress_signal.connect(self._on_benchmark_progress)
        self.benchmark_worker.log_signal.connect(self._on_benchmark_log)
        self.benchmark_worker.finished_signal.connect(self._on_benchmark_finished)
        self.benchmark_worker.start()
    
    def _on_benchmark_progress(self, current, total, model, question):
        progress = int((current / total) * 100)
        if hasattr(self, 'benchmark_progress'):
            self.benchmark_progress.setValue(progress)
        if hasattr(self, 'benchmark_status'):
            self.benchmark_status.append(f"[{model}] {current}/{total}: {question[:60]}...")
            scrollbar = self.benchmark_status.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _on_benchmark_log(self, message):
        if hasattr(self, 'benchmark_status'):
            self.benchmark_status.append(message)
            scrollbar = self.benchmark_status.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _on_benchmark_finished(self, results):
        """Handle benchmark completion - KEEP TAB OPEN!"""
        # Close the benchmark dialog
        if hasattr(self, 'benchmark_dialog') and self.benchmark_dialog:
            self.benchmark_dialog.close()
            self.benchmark_dialog = None
        
        winner = results.get('winner', {})
        
        # Create detailed results message
        winner_msg = f"""
🏆 BENCHMARK COMPLETE! 🏆

╔══════════════════════════════════════════════════════════════╗
║  WINNER: {winner.get('name', 'Unknown').upper()}
║  Score: {winner.get('score', 0)}/100
║  Reason: {winner.get('reason', 'N/A')}
╚══════════════════════════════════════════════════════════════╝

📊 DETAILED RESULTS:
"""
        for model, data in results.get('results', {}).items():
            winner_msg += f"\n  {model}:"
            winner_msg += f"\n    ✅ Success Rate: {data.get('success_rate', 0)}%"
            winner_msg += f"\n    ⏱️  Avg Time: {data.get('avg_response_time', 0)}s"
            winner_msg += f"\n    📝 Depth Score: {data.get('avg_depth_score', 0)}/100"
        
        winner_msg += f"\n\n📁 Results saved to: chat_logs/benchmark_results/benchmark_results.json"
        winner_msg += f"\n📝 Full responses saved for all {len(results.get('detailed_results', []))} Q&A pairs!"
        
        QMessageBox.information(self, "Benchmark Complete", winner_msg)
        
        # Also log to chat UI
        self.ui.add_log("🏆 Benchmark Complete!")
        self.ui.add_log(f"Winner: {winner.get('name', 'Unknown')}")
        for model, data in results.get('results', {}).items():
            self.ui.add_log(f"  {model}: {data.get('success_rate', 0)}% success, {data.get('avg_response_time', 0)}s avg, {data.get('avg_depth_score', 0)}/100 depth")
        self.ui.add_log(f"📁 Full results saved to chat_logs/benchmark_results/")
        
        # Clear worker reference
        self.benchmark_worker = None
    
    def _cancel_benchmark(self):
        """Cancel the benchmark"""
        if self.benchmark_worker:
            self.benchmark_worker.stop()
            if hasattr(self, 'benchmark_dialog') and self.benchmark_dialog:
                self.benchmark_dialog.close()
                self.benchmark_dialog = None
            self.ui.add_log("⚠️ Benchmark cancelled by user")
            QMessageBox.information(self, "Cancelled", "Benchmark was cancelled by user.")
            self.benchmark_worker = None
    
    def _on_send_query(self, prompt: str):
        if self.features.auto_select:
            selected_model, reason = self.features.select_model_for_query(prompt)
            if selected_model and selected_model != self.features.current_model:
                self.features.set_model(selected_model)
                self.ui.add_log(f"🤖 Auto-selected {selected_model} - {reason}")
        
        self.ui.set_send_enabled(False)
        self.ui.set_stop_enabled(True)
        self.progress_timer.stop()
        self.ui.set_progress(5)
        
        self.features.send_query(prompt)
    
    def _on_quick_command(self, command: str):
        self.ui.chat_input.setText(command)
        self._on_send_query(command)
    
    def _on_model_selected(self, model_name):
        self.features.set_model(model_name)
    
    def _on_language_changed(self, language_code: str):
        self.features.set_language(language_code)
    
    def _update_model_list(self, models: list, current_model: str):
        self.ui.update_model_combo(models, current_model)
        self.features.current_model = current_model
    
    def _display_response(self, response: str):
        self.ui.set_response_text(response)
        self.ui.add_log(f"✅ Response received ({len(response)} chars)")
        self._reset_ui()
        
        if self.ui.get_auto_scroll():
            QTimer.singleShot(100, self.ui.scroll_to_bottom)
    
    def _display_error(self, error: str):
        self.ui.set_response_text(f"❌ {error}")
        self.ui.add_log(f"❌ {error}")
        self._reset_ui()
    
    def _reset_ui(self):
        self.ui.set_send_enabled(True)
        self.ui.set_stop_enabled(False)
        self.progress_timer.start(200)
    
    def _animate_progress(self):
        if self.ui.progress_bar.value() == 0:
            self.progress_value = (self.progress_value + 1) % 10
            self.ui.progress_bar.setValue(self.progress_value)
    
    def _on_response_scroll(self, value):
        scrollbar = self.ui.ai_response_display.verticalScrollBar()
        if value < scrollbar.maximum():
            if self.ui.auto_scroll:
                self.ui.auto_scroll = False
                self.ui.auto_scroll_cb.setChecked(False)
    
    def on_theme_changed(self, theme_name, theme_colors):
        self.current_theme = theme_name
        self.theme = theme_colors
        self.ui.apply_theme(theme_colors)
    
    def update_theme(self, theme_colors):
        self.theme = theme_colors
        self.ui.apply_theme(theme_colors)
    
    def cleanup(self):
        if self.benchmark_worker and self.benchmark_worker.isRunning():
            self.benchmark_worker.stop()
        self.features.cleanup()
        self.progress_timer.stop()
    
    def register_worker(self, worker):
        pass
    
    def closeEvent(self, event):
        self.cleanup()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = AIChatTab()
    window.setWindowTitle("AI Chat - Multi-Language Assistant")
    window.resize(840, 490)
    window.show()
    
    sys.exit(app.exec_())