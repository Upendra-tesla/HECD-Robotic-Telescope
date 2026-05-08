#!/usr/bin/env python3
"""
Chat Log Viewer Dialog - View system logs and conversation history
"""

import os
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox, QComboBox,
    QTreeWidget, QTreeWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from .chat_logger import chat_logger


class ChatLogViewer(QDialog):
    """Dialog to view chat logs and system information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat Logs & Conversation History")
        self.setModal(False)
        self.setMinimumSize(900, 650)
        self.resize(900, 650)
        
        self.setup_ui()
        self.refresh_all()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_system_logs)
        self.refresh_timer.start(3000)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Tab 1: System Logs
        self.system_logs_tab = self._create_system_logs_tab()
        self.tab_widget.addTab(self.system_logs_tab, "📋 System Logs")
        
        # Tab 2: Conversation History
        self.conversation_tab = self._create_conversation_tab()
        self.tab_widget.addTab(self.conversation_tab, "💬 Conversation History")
        
        # Tab 3: Statistics
        self.stats_tab = self._create_stats_tab()
        self.tab_widget.addTab(self.stats_tab, "📊 Statistics")
        
        # Tab 4: Log Files
        self.log_files_tab = self._create_log_files_tab()
        self.tab_widget.addTab(self.log_files_tab, "📁 Log Files")
        
        layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh All")
        self.refresh_btn.clicked.connect(self.refresh_all)
        button_layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("💾 Export Conversations")
        self.export_btn.clicked.connect(self.export_conversations)
        button_layout.addWidget(self.export_btn)
        
        self.export_system_btn = QPushButton("📄 Export System Logs")
        self.export_system_btn.clicked.connect(self.export_system_logs)
        button_layout.addWidget(self.export_system_btn)
        
        self.report_btn = QPushButton("📈 Generate Report")
        self.report_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(self.report_btn)
        
        button_layout.addStretch()
        
        self.cleanup_btn = QPushButton("🗑 Cleanup Old Logs")
        self.cleanup_btn.clicked.connect(self.cleanup_old_logs)
        button_layout.addWidget(self.cleanup_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_system_logs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by level:"))
        
        self.log_level_filter = QComboBox()
        self.log_level_filter.addItems(["ALL", "INFO", "WARNING", "ERROR", "DEBUG"])
        self.log_level_filter.currentTextChanged.connect(self.refresh_system_logs)
        filter_layout.addWidget(self.log_level_filter)
        
        filter_layout.addWidget(QLabel("Limit:"))
        self.log_limit_combo = QComboBox()
        self.log_limit_combo.addItems(["50", "100", "200", "500", "1000"])
        self.log_limit_combo.setCurrentText("200")
        self.log_limit_combo.currentTextChanged.connect(self.refresh_system_logs)
        filter_layout.addWidget(self.log_limit_combo)
        
        filter_layout.addStretch()
        
        self.clear_logs_btn = QPushButton("Clear Display")
        self.clear_logs_btn.clicked.connect(self.clear_logs_display)
        filter_layout.addWidget(self.clear_logs_btn)
        
        layout.addLayout(filter_layout)
        
        self.logs_display = QTextEdit()
        self.logs_display.setReadOnly(True)
        self.logs_display.setFont(QFont("Monospace", 9))
        layout.addWidget(self.logs_display)
        
        return widget
    
    def _create_conversation_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Limit:"))
        
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["10", "25", "50", "100", "200", "All"])
        self.limit_combo.setCurrentText("50")
        self.limit_combo.currentTextChanged.connect(self.refresh_conversations)
        control_layout.addWidget(self.limit_combo)
        
        control_layout.addWidget(QLabel("Search:"))
        self.search_edit = QComboBox()
        self.search_edit.setEditable(True)
        self.search_edit.setFixedWidth(200)
        self.search_edit.setPlaceholderText("Type to search...")
        self.search_edit.lineEdit().textChanged.connect(self.refresh_conversations)
        control_layout.addWidget(self.search_edit)
        
        control_layout.addStretch()
        
        self.clear_search_btn = QPushButton("Clear Search")
        self.clear_search_btn.clicked.connect(self.clear_search)
        control_layout.addWidget(self.clear_search_btn)
        
        layout.addLayout(control_layout)
        
        self.conversation_display = QTextEdit()
        self.conversation_display.setReadOnly(True)
        self.conversation_display.setFont(QFont("Monospace", 10))
        layout.addWidget(self.conversation_display)
        
        return widget
    
    def _create_stats_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(True)
        self.stats_display.setFont(QFont("Monospace", 10))
        layout.addWidget(self.stats_display)
        
        return widget
    
    def _create_log_files_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.log_files_tree = QTreeWidget()
        self.log_files_tree.setHeaderLabels(["File Name", "Size", "Modified"])
        self.log_files_tree.setColumnWidth(0, 400)
        self.log_files_tree.setColumnWidth(1, 100)
        self.log_files_tree.setColumnWidth(2, 150)
        self.log_files_tree.itemDoubleClicked.connect(self.open_log_file)
        layout.addWidget(self.log_files_tree)
        
        btn_layout = QHBoxLayout()
        
        self.refresh_files_btn = QPushButton("🔄 Refresh")
        self.refresh_files_btn.clicked.connect(self.refresh_log_files)
        btn_layout.addWidget(self.refresh_files_btn)
        
        self.open_file_btn = QPushButton("📂 Open Selected")
        self.open_file_btn.clicked.connect(self.open_selected_log_file)
        btn_layout.addWidget(self.open_file_btn)
        
        self.delete_file_btn = QPushButton("🗑 Delete Selected")
        self.delete_file_btn.clicked.connect(self.delete_selected_log_file)
        btn_layout.addWidget(self.delete_file_btn)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def refresh_all(self):
        self.refresh_system_logs()
        self.refresh_conversations()
        self.refresh_stats()
        self.refresh_log_files()
    
    def refresh_system_logs(self):
        level_filter = self.log_level_filter.currentText()
        if level_filter == "ALL":
            level_filter = None
        
        limit = int(self.log_limit_combo.currentText())
        logs = chat_logger.get_system_logs(level=level_filter, limit=limit)
        
        self.logs_display.clear()
        
        if not logs:
            self.logs_display.append("No logs found.")
            return
        
        for log in reversed(logs):
            timestamp = log.get('timestamp', '')
            if 'T' in timestamp:
                timestamp = timestamp.split('T')[1][:8]
            
            level = log.get('level', 'INFO')
            component = log.get('component', 'ChatTab')
            message = log.get('message', '')
            
            if level == "ERROR":
                color = "#ef4444"
                emoji = "❌"
            elif level == "WARNING":
                color = "#f59e0b"
                emoji = "⚠️"
            elif level == "DEBUG":
                color = "#94a3b8"
                emoji = "🔍"
            else:
                color = "#10b981"
                emoji = "ℹ️"
            
            self.logs_display.append(
                f'<span style="color:#64748b">[{timestamp}]</span> '
                f'<span style="color:{color};font-weight:bold">{emoji} [{level}]</span> '
                f'<span style="color:#38bdf8">[{component}]</span> '
                f'{message}'
            )
        
        scrollbar = self.logs_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def refresh_conversations(self):
        limit_text = self.limit_combo.currentText()
        limit = None if limit_text == "All" else int(limit_text)
        
        conversations = chat_logger.get_conversation_history(limit=limit or 1000, session_only=False)
        search_text = self.search_edit.currentText().strip().lower()
        
        self.conversation_display.clear()
        
        if not conversations:
            self.conversation_display.append("No conversations found.")
            return
        
        displayed_count = 0
        
        for conv in reversed(conversations):
            if search_text:
                query_match = search_text in conv.get('query', '').lower()
                response_match = search_text in conv.get('response', '').lower()
                if not (query_match or response_match):
                    continue
            
            displayed_count += 1
            
            timestamp = conv.get('timestamp', '')
            if 'T' in timestamp:
                time_str = timestamp.split('T')[1][:8]
                date_str = timestamp.split('T')[0]
            else:
                time_str = timestamp[:8]
                date_str = ""
            
            query = conv.get('query', '')[:300]
            if len(conv.get('query', '')) > 300:
                query += "..."
            
            response = conv.get('response', '')[:500]
            if len(conv.get('response', '')) > 500:
                response += "..."
            
            model = conv.get('model', 'unknown')
            response_time = conv.get('response_time_seconds', 0)
            success = conv.get('success', True)
            language = conv.get('language', 'en').upper()
            
            status_icon = "✅" if success else "❌"
            status_color = "#10b981" if success else "#ef4444"
            
            self.conversation_display.append(
                f'<div style="margin-bottom: 15px; padding: 10px; background-color: rgba(30,41,59,0.4); border-radius: 6px; border-left: 3px solid {status_color};">'
                f'<div><span style="color:#64748b">📅 {date_str} 🕐 {time_str}</span> '
                f'<span style="color:{status_color}">{status_icon}</span> '
                f'<span style="color:#fca311">🤖 {model}</span> '
                f'<span style="color:#94a3b8">⏱ {response_time}s</span> '
                f'<span style="color:#38bdf8">🌐 {language}</span></div>'
                f'<div style="margin-top: 8px;"><span style="color:#38bdf8;font-weight:bold">Q:</span> {query}</div>'
                f'<div style="margin-top: 5px;"><span style="color:#38bdf8;font-weight:bold">A:</span> {response}</div>'
                f'</div>'
            )
        
        if displayed_count == 0:
            self.conversation_display.append(f"No conversations found matching '{search_text}'")
    
    def refresh_stats(self):
        report = chat_logger.generate_session_report()
        self.stats_display.clear()
        self.stats_display.append(report)
    
    def refresh_log_files(self):
        self.log_files_tree.clear()
        log_files = chat_logger.get_log_files()
        
        if log_files['system_logs']:
            system_item = QTreeWidgetItem(["📁 System Logs", "", ""])
            system_item.setExpanded(True)
            self.log_files_tree.addTopLevelItem(system_item)
            for f in sorted(log_files['system_logs'], key=lambda x: x['name'], reverse=True):
                size_kb = f['size'] / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                modified = datetime.fromtimestamp(os.path.getmtime(f['path'])).strftime("%Y-%m-%d %H:%M:%S")
                item = QTreeWidgetItem([f['name'], size_str, modified])
                item.setData(0, Qt.UserRole, f['path'])
                system_item.addChild(item)
        
        if log_files['conversation_logs']:
            conv_item = QTreeWidgetItem(["📁 Conversation Logs", "", ""])
            conv_item.setExpanded(True)
            self.log_files_tree.addTopLevelItem(conv_item)
            for f in sorted(log_files['conversation_logs'], key=lambda x: x['name'], reverse=True):
                size_kb = f['size'] / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                modified = datetime.fromtimestamp(os.path.getmtime(f['path'])).strftime("%Y-%m-%d %H:%M:%S")
                item = QTreeWidgetItem([f['name'], size_str, modified])
                item.setData(0, Qt.UserRole, f['path'])
                conv_item.addChild(item)
        
        if log_files['reports']:
            report_item = QTreeWidgetItem(["📁 Reports", "", ""])
            report_item.setExpanded(True)
            self.log_files_tree.addTopLevelItem(report_item)
            for f in sorted(log_files['reports'], key=lambda x: x['name'], reverse=True):
                size_kb = f['size'] / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                modified = datetime.fromtimestamp(os.path.getmtime(f['path'])).strftime("%Y-%m-%d %H:%M:%S")
                item = QTreeWidgetItem([f['name'], size_str, modified])
                item.setData(0, Qt.UserRole, f['path'])
                report_item.addChild(item)
    
    def clear_logs_display(self):
        self.logs_display.clear()
    
    def clear_search(self):
        self.search_edit.setCurrentText("")
        self.refresh_conversations()
    
    def open_log_file(self, item, column):
        filepath = item.data(0, Qt.UserRole)
        if filepath and os.path.exists(filepath):
            self._display_file_content(filepath)
    
    def open_selected_log_file(self):
        selected = self.log_files_tree.selectedItems()
        if selected:
            filepath = selected[0].data(0, Qt.UserRole)
            if filepath and os.path.exists(filepath):
                self._display_file_content(filepath)
    
    def _display_file_content(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if filepath.endswith('.json'):
                try:
                    data = json.loads(content)
                    content = json.dumps(data, indent=2, ensure_ascii=False)
                except:
                    pass
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Viewing: {os.path.basename(filepath)}")
            dialog.setMinimumSize(800, 600)
            
            layout = QVBoxLayout(dialog)
            text_edit = QTextEdit()
            text_edit.setPlainText(content)
            text_edit.setFont(QFont("Monospace", 9))
            layout.addWidget(text_edit)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(close_btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)
            
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")
    
    def delete_selected_log_file(self):
        selected = self.log_files_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a file to delete")
            return
        
        filepath = selected[0].data(0, Qt.UserRole)
        if not filepath:
            QMessageBox.warning(self, "Invalid Selection", "Please select a file")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {os.path.basename(filepath)}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                os.remove(filepath)
                self.refresh_log_files()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
    
    def export_conversations(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Conversations", f"chat_conversations_{chat_logger.session_id}", "JSON Files (*.json);;Text Files (*.txt)")
        if filepath:
            format_type = "json" if filepath.endswith('.json') else "txt"
            if chat_logger.export_conversations(filepath, format_type):
                QMessageBox.information(self, "Success", f"Exported to:\n{filepath}")
    
    def export_system_logs(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export System Logs", f"system_logs_{chat_logger.session_id}.json", "JSON Files (*.json)")
        if filepath:
            logs = chat_logger.get_system_logs(limit=10000)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Success", f"Exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")
    
    def generate_report(self):
        report_file = chat_logger.save_session_report()
        QMessageBox.information(self, "Report Generated", f"Saved to:\n{report_file}")
        self.refresh_stats()
    
    def cleanup_old_logs(self):
        reply = QMessageBox.question(self, "Cleanup", "Delete logs older than 30 days?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            chat_logger.cleanup_old_logs(days=30)
            self.refresh_log_files()
    
    def closeEvent(self, event):
        self.refresh_timer.stop()
        event.accept()