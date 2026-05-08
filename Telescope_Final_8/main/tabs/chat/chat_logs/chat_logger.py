#!/usr/bin/env python3
"""
Centralized Chat Logger - Single file for all logs
- system_logs.json: All system events
- conversation_logs.json: All Q&A conversations
"""

import os
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import deque

class ChatLogger:
    """Centralized logger - single files for system and conversation logs"""
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Get the chat_logs directory
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.system_logs_dir = os.path.join(self.base_dir, "system_logs")
        self.conversation_logs_dir = os.path.join(self.base_dir, "conversation_logs")
        
        # Ensure directories exist
        os.makedirs(self.system_logs_dir, exist_ok=True)
        os.makedirs(self.conversation_logs_dir, exist_ok=True)
        
        # Single log files (not per session)
        self.system_log_file = os.path.join(self.system_logs_dir, "system_logs.json")
        self.conversation_log_file = os.path.join(self.conversation_logs_dir, "conversation_logs.json")
        
        # Initialize log files if they don't exist
        self._init_log_files()
        
        # Session tracking
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_query = None
        self.query_start_time = None
        self.current_model = None
        self.current_language = None
        self._log_callback = None
        
        # Log session start
        self.log_info(f"Session started: {self.session_id}", component="ChatTab")
    
    def _init_log_files(self):
        """Initialize log files with empty arrays if they don't exist"""
        for log_file in [self.system_log_file, self.conversation_log_file]:
            if not os.path.exists(log_file):
                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2)
    
    def _write_log(self, log_file: str, entry: Dict):
        """Write a log entry to the appropriate log file"""
        with self._lock:
            try:
                # Read existing logs
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8') as f:
                        logs = json.load(f)
                else:
                    logs = []
                
                # Add new entry
                logs.append(entry)
                
                # Keep only last 1000 entries to prevent file bloat
                if len(logs) > 1000:
                    logs = logs[-1000:]
                
                # Write back
                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error writing to log: {e}")
    
    def set_log_callback(self, callback):
        self._log_callback = callback
    
    def log_info(self, message: str, component: str = "ChatTab", details: Dict = None):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'level': 'INFO',
            'component': component,
            'message': message,
            'details': details or {}
        }
        self._write_log(self.system_log_file, entry)
        if self._log_callback:
            self._log_callback(f"ℹ️ {message}")
    
    def log_error(self, message: str, component: str = "ChatTab", details: Dict = None):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'level': 'ERROR',
            'component': component,
            'message': message,
            'details': details or {}
        }
        self._write_log(self.system_log_file, entry)
        if self._log_callback:
            self._log_callback(f"❌ {message}")
    
    def log_warning(self, message: str, component: str = "ChatTab", details: Dict = None):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'level': 'WARNING',
            'component': component,
            'message': message,
            'details': details or {}
        }
        self._write_log(self.system_log_file, entry)
        if self._log_callback:
            self._log_callback(f"⚠️ {message}")
    
    def start_query(self, query: str, model: str, language: str):
        self.current_query = query
        self.current_model = model
        self.current_language = language
        self.query_start_time = time.time()
        self.log_info(f"Query started - Model: {model}", component="Query")
    
    def end_query(self, response: str, success: bool = True, error_msg: str = None, tokens: int = 0):
        if self.query_start_time is None:
            return
        
        elapsed = time.time() - self.query_start_time
        
        conversation_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'query': self.current_query,
            'response': response,
            'model': self.current_model,
            'language': self.current_language,
            'response_time_seconds': round(elapsed, 2),
            'success': success,
            'error': error_msg,
            'response_length': len(response),
            'tokens_estimated': tokens
        }
        
        self._write_log(self.conversation_log_file, conversation_entry)
        self.log_info(f"Query completed - {success} - {round(elapsed, 2)}s", component="Query")
        
        self.current_query = None
        self.query_start_time = None
    
    def log_model_switch(self, old_model: str, new_model: str, reason: str):
        self.log_info(f"Model switched: {old_model} → {new_model} ({reason})", component="ModelManager")
    
    def log_auto_selection(self, model: str, reason: str, query_preview: str = None):
        self.log_info(f"Auto-selected: {model} - {reason}", component="AutoSelector")
    
    def get_system_logs(self, limit: int = 500) -> List[Dict]:
        try:
            if os.path.exists(self.system_log_file):
                with open(self.system_log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                    return logs[-limit:] if limit else logs
        except:
            pass
        return []
    
    def get_conversation_logs(self, limit: int = 500) -> List[Dict]:
        try:
            if os.path.exists(self.conversation_log_file):
                with open(self.conversation_log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                    return logs[-limit:] if limit else logs
        except:
            pass
        return []
    
    def clear_all_logs(self) -> bool:
        """Clear all log files"""
        try:
            with self._lock:
                # Clear system logs
                with open(self.system_log_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2)
                
                # Clear conversation logs
                with open(self.conversation_log_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2)
                
                # Log the clear action
                self.log_info("All logs cleared by user", component="System")
                return True
        except Exception as e:
            print(f"Error clearing logs: {e}")
            return False
    
    def get_log_stats(self) -> Dict:
        """Get statistics about log files"""
        stats = {
            'system_logs_count': 0,
            'conversation_logs_count': 0,
            'system_log_size': 0,
            'conversation_log_size': 0
        }
        
        try:
            if os.path.exists(self.system_log_file):
                stats['system_log_size'] = os.path.getsize(self.system_log_file)
                with open(self.system_log_file, 'r') as f:
                    stats['system_logs_count'] = len(json.load(f))
        except:
            pass
        
        try:
            if os.path.exists(self.conversation_log_file):
                stats['conversation_log_size'] = os.path.getsize(self.conversation_log_file)
                with open(self.conversation_log_file, 'r') as f:
                    stats['conversation_logs_count'] = len(json.load(f))
        except:
            pass
        
        return stats

# Create global instance
chat_logger = ChatLogger()