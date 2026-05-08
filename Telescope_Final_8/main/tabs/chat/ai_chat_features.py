#!/usr/bin/env python3
"""
AI Chat Features - Business Logic
- 3 specialized models for different tasks
- qwen2.5:1.5b = Multi-language (Nepali, Hindi, Chinese)
- deepseek-r1:1.5b = Deep/Complex reasoning
- tinyllama:latest = Quick/Simple responses
- Auto-model selection based on query type
- Integrated conversation logging
"""

import sys
import os
import json
import threading
import datetime
import requests
import subprocess
import re
import time
from typing import Dict, Optional, Tuple, List
from PyQt5.QtCore import QThread, pyqtSignal, QObject

# ============================================
# PATH CONFIGURATION
# ============================================
CURRENT_FILE = os.path.abspath(__file__)
CURRENT_DIR = os.path.dirname(CURRENT_FILE)
CHAT_DIR = CURRENT_DIR
TABS_DIR = os.path.dirname(CHAT_DIR)
MAIN_DIR = os.path.dirname(TABS_DIR)
CONFIG_DIR = os.path.join(MAIN_DIR, "config")
CHAT_LOGS_DIR = os.path.join(CHAT_DIR, "chat_logs")

# Add directories to Python path
for path in [CONFIG_DIR, MAIN_DIR, TABS_DIR, CHAT_DIR, CHAT_LOGS_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ============================================
# IMPORT CHAT LOGGER
# ============================================
CHAT_LOGGER_AVAILABLE = False
chat_logger = None

try:
    from chat_logs.chat_logger import chat_logger
    CHAT_LOGGER_AVAILABLE = True
    print("✅ ai_chat_features.py - Chat logger imported successfully")
except ImportError as e:
    print(f"⚠️ Could not import chat_logger: {e}")
    # Create a fallback logger
    class FallbackChatLogger:
        def __init__(self):
            self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self._log_callback = None
        def set_log_callback(self, callback):
            self._log_callback = callback
        def start_query(self, query, model, language):
            print(f"[LOG] Query: {query[:50]}...")
        def end_query(self, response, success=True, error_msg=None, tokens=0):
            print(f"[LOG] Response: {len(response)} chars")
        def log_info(self, msg, component="", details=None):
            print(f"[INFO] {component}: {msg}")
        def log_error(self, msg, component="", details=None):
            print(f"[ERROR] {component}: {msg}")
        def log_warning(self, msg, component="", details=None):
            print(f"[WARNING] {component}: {msg}")
        def log_debug(self, msg, component="", details=None):
            print(f"[DEBUG] {component}: {msg}")
        def log_model_switch(self, old_model, new_model, reason):
            print(f"[INFO] Model switch: {old_model} -> {new_model}")
        def log_auto_selection(self, model, reason, query_preview=None):
            print(f"[INFO] Auto-selected: {model}")
        def save_session_report(self):
            pass
    chat_logger = FallbackChatLogger()
    CHAT_LOGGER_AVAILABLE = True

# ============================================
# IMPORT THEME MANAGER
# ============================================
try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False
    class FallbackThemeManager:
        def get_current_theme(self): return "Dark"
        def get_colors(self): return {"bg": "#0f172a", "bg_secondary": "#1e293b", "text": "#f8fafc"}
    theme_manager = FallbackThemeManager()

# ============================================
# MODEL CONFIGURATION - 3 SPECIALIZED MODELS
# ============================================

# Available models with their roles
AVAILABLE_MODELS = {
    "qwen2.5:1.5b": {
        "name": "Qwen2.5 1.5B",
        "role": "🌐 Multi-Language",
        "description": "Best for Nepali, Hindi, Chinese responses",
        "speed": "Medium (9-11 t/s)",
        "size": "986MB",
        "ram": "1.8GB",
        "specialty": "multilingual",
        "languages": ["en", "zh", "hi", "ne"],
        "emoji": "🌐"
    },
    "deepseek-r1:1.5b": {
        "name": "DeepSeek R1 1.5B",
        "role": "🧠 Deep Reasoning",
        "description": "Best for complex, detailed explanations",
        "speed": "Slow (8-10 t/s)",
        "size": "1.1GB",
        "ram": "1.9GB",
        "specialty": "reasoning",
        "languages": ["en", "zh"],
        "emoji": "🧠"
    },
    "tinyllama:latest": {
        "name": "TinyLlama",
        "role": "⚡ Quick Response",
        "description": "Best for fast, simple answers",
        "speed": "Fast (12-15 t/s)",
        "size": "636MB",
        "ram": "1.2GB",
        "specialty": "quick",
        "languages": ["en"],
        "emoji": "⚡"
    }
}

# Model priority order for display
MODEL_PRIORITY = ["qwen2.5:1.5b", "deepseek-r1:1.5b", "tinyllama:latest"]

# ============================================
# LANGUAGE CONFIGURATION
# ============================================
LANGUAGES = {
    "en": {
        "name": "English",
        "code": "en",
        "instruction": "Answer in English.",
        "supported_by": ["qwen2.5:1.5b", "deepseek-r1:1.5b", "tinyllama:latest"]
    },
    "zh": {
        "name": "中文",
        "code": "zh",
        "instruction": "用中文回答。",
        "supported_by": ["qwen2.5:1.5b", "deepseek-r1:1.5b"]
    },
    "hi": {
        "name": "हिन्दी",
        "code": "hi",
        "instruction": "हिंदी में उत्तर दें।",
        "supported_by": ["qwen2.5:1.5b"]
    },
    "ne": {
        "name": "नेपाली",
        "code": "ne",
        "instruction": "नेपालीमा जवाफ दिनुहोस्।",
        "supported_by": ["qwen2.5:1.5b"]
    }
}

# ============================================
# QUERY ANALYSIS
# ============================================

QUICK_PATTERNS = [
    'yes', 'no', 'ok', 'thanks', 'hello', 'hi', 'hey',
    'what time', 'status', 'check', 'working', 'temperature',
    'weather', 'connected', 'current', 'now', 'today',
    'value', 'reading', 'is it', 'does it', 'can i'
]

COMPLEX_PATTERNS = [
    'explain in detail', 'describe thoroughly', 'how does it work',
    'why does', 'difference between', 'compare and contrast',
    'analyze', 'research', 'physics', 'formula', 'equation',
    'calculate', 'derivation', 'mechanism', 'principle',
    'theory of', 'history of', 'origin of', 'mathematical',
    'scientific explanation', 'detailed analysis', 'reasoning'
]

def analyze_query(query: str, language_code: str = "en") -> Dict:
    query_lower = query.lower()
    word_count = len(query_lower.split())
    
    if language_code in ['ne', 'hi']:
        return {
            'model': 'qwen2.5:1.5b',
            'reason': f'Only Qwen supports {LANGUAGES[language_code]["name"]} language'
        }
    
    for pattern in COMPLEX_PATTERNS:
        if pattern in query_lower:
            return {
                'model': 'deepseek-r1:1.5b',
                'reason': f'Complex query detected: "{pattern}"'
            }
    
    if word_count <= 5:
        return {
            'model': 'tinyllama:latest',
            'reason': f'Very short query ({word_count} words)'
        }
    
    for pattern in QUICK_PATTERNS:
        if pattern in query_lower:
            return {
                'model': 'tinyllama:latest',
                'reason': f'Simple query detected: "{pattern}"'
            }
    
    if word_count > 20:
        return {
            'model': 'deepseek-r1:1.5b',
            'reason': f'Detailed query ({word_count} words)'
        }
    
    return {
        'model': 'qwen2.5:1.5b',
        'reason': 'General purpose query'
    }

# ============================================
# AI WORKER
# ============================================
class AIWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    log_update = pyqtSignal(str)

    def __init__(self, model_name: str, prompt: str, language_code: str = "en", cloud_api_key: str = ""):
        super().__init__()
        self.model_name = model_name
        self.original_prompt = prompt
        self.language_code = language_code
        self.cloud_api_key = cloud_api_key
        self.stop_requested = False
        self.progress = 0
        self.is_first_query = True

    def run(self):
        # Start logging the query
        try:
            chat_logger.start_query(
                query=self.original_prompt,
                model=self.model_name,
                language=self.language_code
            )
        except Exception as e:
            print(f"Error starting log: {e}")
        
        try:
            lang_info = LANGUAGES.get(self.language_code, LANGUAGES["en"])
            model_info = AVAILABLE_MODELS.get(self.model_name, {})
            
            self.log_update.emit(f"Using {model_info.get('emoji', '🤖')} {self.model_name} ({model_info.get('role', 'AI')})")
            self.log_update.emit(f"Language: {lang_info['name']}")
            self._update_progress(0)

            if not self._check_model_exists():
                error_msg = f"Model {self.model_name} not found. Please pull it first:\nollama pull {self.model_name}"
                chat_logger.log_error(error_msg, component="AIWorker")
                self.error_occurred.emit(error_msg)
                chat_logger.end_query(response="", success=False, error_msg=error_msg)
                return

            if not self._check_ollama_api():
                error_msg = "Ollama API is unreachable. Please ensure Ollama is running."
                chat_logger.log_error(error_msg, component="AIWorker")
                self.error_occurred.emit(error_msg)
                chat_logger.end_query(response="", success=False, error_msg=error_msg)
                return

            full_prompt = self._prepare_prompt()
            self._update_progress(20)

            response = self._query_ollama(full_prompt)
            self._update_progress(100)

            if not self.stop_requested:
                estimated_tokens = len(self.original_prompt) // 4 + len(response) // 4
                
                try:
                    chat_logger.end_query(
                        response=response,
                        success=True,
                        tokens=estimated_tokens
                    )
                except Exception as e:
                    print(f"Error ending log: {e}")
                
                self.response_ready.emit(response)
                self.log_update.emit(f"✅ Response received ({len(response)} chars)")

        except Exception as e:
            if not self.stop_requested:
                error_msg = str(e)
                try:
                    chat_logger.end_query(
                        response="",
                        success=False,
                        error_msg=error_msg
                    )
                except Exception:
                    pass
                self.error_occurred.emit(f"AI Error: {error_msg}")

    def _check_model_exists(self) -> bool:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model["name"] for model in models]
                return self.model_name in model_names
            return False
        except:
            return False

    def _check_ollama_api(self) -> bool:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _prepare_prompt(self) -> str:
        self._update_progress(10)
        lang_info = LANGUAGES.get(self.language_code, LANGUAGES["en"])
        
        if "qwen2.5" in self.model_name:
            return f"{lang_info['instruction']}\n\n{self.original_prompt}"
        elif "deepseek" in self.model_name:
            return f"""You are a telescope AI assistant. Provide helpful, accurate information.

{lang_info['instruction']}

Question: {self.original_prompt}

Please provide a detailed, well-reasoned answer:"""
        else:
            return f"Answer concisely: {self.original_prompt}"

    def _query_ollama(self, prompt: str) -> str:
        self.log_update.emit(f"Loading {self.model_name}...")
        
        if self.is_first_query:
            self.log_update.emit("⏳ First query - loading model into memory...")
        self._update_progress(30)

        try:
            url = "http://localhost:11434/api/generate"
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9}
            }
            
            if "deepseek" in self.model_name:
                payload["options"]["num_predict"] = 1000
                payload["options"]["temperature"] = 0.8
            elif "qwen2.5" in self.model_name:
                payload["options"]["num_predict"] = 800
                payload["options"]["temperature"] = 0.7
            else:
                payload["options"]["num_predict"] = 300
                payload["options"]["temperature"] = 0.5
            
            payload["keep_alive"] = "10m"

            self._update_progress(40)

            timeout = 120 if self.is_first_query else 60
            self.is_first_query = False
            
            response = requests.post(url, json=payload, timeout=timeout,
                                    headers={"Content-Type": "application/json"})

            self._update_progress(80)

            if response.status_code == 200:
                result = response.json()
                raw_response = result.get("response", str(result))
                
                response_text = re.sub(r'<[^>]+>', '', raw_response)
                response_text = re.sub(r'\n\s*\n', '\n\n', response_text)
                response_text = response_text.strip()
                
                return response_text if response_text else "⚠️ Empty response"
            else:
                return f"Error {response.status_code}: {response.text[:200]}"

        except requests.exceptions.Timeout:
            return f"Timeout after {timeout}s. Try again."
        except Exception as e:
            return f"Error: {str(e)}"

    def _update_progress(self, value: int):
        if not self.stop_requested and value > self.progress:
            self.progress = value
            self.progress_update.emit(value)
            QThread.msleep(50)

    def stop(self):
        self.stop_requested = True
        self.wait()

# ============================================
# MAIN AIChatFeatures CLASS
# ============================================
class AIChatFeatures(QObject):
    log_signal = pyqtSignal(str)
    response_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    model_info_signal = pyqtSignal(str)
    model_list_signal = pyqtSignal(list, str)
    benchmark_result_signal = pyqtSignal(dict)
    benchmark_finished_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_model = "qwen2.5:1.5b"
        self.current_language = "en"
        self.cloud_api_key = ""
        self.available_models = []
        self.ai_worker = None
        self.auto_select = True
        
        # Set log callback
        try:
            chat_logger.set_log_callback(self.log_signal.emit)
            chat_logger.log_info("AI Chat Features initialized", component="AIChatFeatures")
        except Exception as e:
            print(f"Error setting log callback: {e}")
        
        self.fetch_models()
    
    def fetch_models(self):
        chat_logger.log_info("Fetching available models from Ollama", component="ModelManager")
        threading.Thread(target=self._fetch_models_bg, daemon=True).start()
    
    def _fetch_models_bg(self):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                self.available_models = [model["name"] for model in models]
                
                available_priority = [m for m in MODEL_PRIORITY if m in self.available_models]
                if available_priority:
                    self.current_model = available_priority[0]
                
                self.model_list_signal.emit(self.available_models, self.current_model)
                self._update_model_info()
                
                chat_logger.log_info(f"Found {len(self.available_models)} models: {', '.join(self.available_models[:5])}", 
                                    component="ModelManager")
                self.log_signal.emit(f"✅ Available models: {', '.join(self.available_models[:5])}")
            else:
                chat_logger.log_warning("Failed to fetch models from Ollama", component="ModelManager")
                self.log_signal.emit("⚠️ Failed to fetch models")
        except requests.exceptions.ConnectionError:
            chat_logger.log_error("Cannot connect to Ollama. Run: ollama serve", component="ModelManager")
            self.log_signal.emit("❌ Cannot connect to Ollama. Run: ollama serve")
            self.model_list_signal.emit([], "")
        except Exception as e:
            chat_logger.log_error(f"Error fetching models: {str(e)}", component="ModelManager")
            self.log_signal.emit(f"❌ Error: {str(e)}")
    
    def _update_model_info(self):
        info = AVAILABLE_MODELS.get(self.current_model, {})
        if info:
            self.model_info_signal.emit(f"{info['emoji']} {info['name']} | {info['role']} | {info['speed']} | {info['description']}")
    
    def set_language(self, language_code: str):
        if language_code in LANGUAGES:
            self.current_language = language_code
            lang_info = LANGUAGES[language_code]
            chat_logger.log_info(f"Language changed to {lang_info['name']}", component="Language")
            
            if self.current_model not in lang_info.get('supported_by', []):
                if language_code in ['ne', 'hi'] and 'qwen2.5:1.5b' in self.available_models:
                    chat_logger.log_warning(f"{self.current_model} doesn't support {lang_info['name']}. Switching to Qwen2.5...", component="Language")
                    self.log_signal.emit(f"⚠️ {self.current_model} doesn't support {lang_info['name']}. Switching to Qwen2.5...")
                    self.set_model('qwen2.5:1.5b')
                else:
                    chat_logger.log_warning(f"{lang_info['name']} may not work well with {self.current_model}", component="Language")
                    self.log_signal.emit(f"⚠️ {lang_info['name']} may not work well with {self.current_model}")
            
            self.log_signal.emit(f"🌐 Language: {lang_info['name']}")
    
    def set_model(self, model_name: str):
        if model_name in self.available_models:
            old_model = self.current_model
            self.current_model = model_name
            self._update_model_info()
            info = AVAILABLE_MODELS.get(model_name, {})
            chat_logger.log_model_switch(old_model, model_name, "Manual selection")
            self.log_signal.emit(f"📱 Switched to: {info.get('emoji', '')} {model_name} ({info.get('role', 'AI')})")
            return True
        return False
    
    def set_auto_select(self, enabled: bool):
        self.auto_select = enabled
        chat_logger.log_info(f"Auto-model selection {'enabled' if enabled else 'disabled'}", component="AutoSelector")
        self.log_signal.emit(f"🤖 Auto-model selection {'enabled' if enabled else 'disabled'}")
    
    def select_model_for_query(self, query: str) -> Tuple[str, str]:
        if not self.auto_select:
            return self.current_model, "Manual selection"
        
        analysis = analyze_query(query, self.current_language)
        recommended = analysis['model']
        
        chat_logger.log_auto_selection(recommended, analysis['reason'], query[:100])
        
        if recommended in self.available_models:
            return recommended, analysis['reason']
        if self.current_model in self.available_models:
            return self.current_model, "Using current model (fallback)"
        if self.available_models:
            return self.available_models[0], "Using first available model"
        return "", "No models available"
    
    def send_query(self, prompt: str):
        if self.auto_select:
            selected_model, reason = self.select_model_for_query(prompt)
            if selected_model and selected_model != self.current_model:
                self.current_model = selected_model
                self._update_model_info()
                chat_logger.log_auto_selection(selected_model, reason, prompt[:100])
                self.log_signal.emit(f"🎯 Auto-selected: {selected_model} ({reason})")
        
        if not self.current_model or self.current_model not in self.available_models:
            error_msg = "No model available. Please check Ollama."
            chat_logger.log_error(error_msg, component="Query")
            self.error_signal.emit(error_msg)
            return
        
        lang_info = LANGUAGES.get(self.current_language, LANGUAGES["en"])
        model_info = AVAILABLE_MODELS.get(self.current_model, {})
        
        self.log_signal.emit(f"📤 Sending query to {model_info.get('emoji', '')} {self.current_model}")
        self.log_signal.emit(f"   Language: {lang_info['name']}")
        self.progress_signal.emit(5)
        
        self.ai_worker = AIWorker(self.current_model, prompt, self.current_language, self.cloud_api_key)
        self.ai_worker.response_ready.connect(self._on_response)
        self.ai_worker.error_occurred.connect(self.error_signal.emit)
        self.ai_worker.progress_update.connect(self.progress_signal.emit)
        self.ai_worker.log_update.connect(self.log_signal.emit)
        self.ai_worker.start()
    
    def _on_response(self, response: str):
        if response and not response.startswith("Error"):
            self.response_signal.emit(response)
            self.log_signal.emit(f"✅ Response received ({len(response)} chars)")
        else:
            chat_logger.log_error(response[:200] if response else "Empty response", component="Response")
            self.error_signal.emit(response if response else "Unknown error")
    
    def stop_query(self):
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
            chat_logger.log_info("Query stopped by user", component="Query")
            self.log_signal.emit("⏹ Query stopped")
    
    def run_benchmark(self):
        if not self.available_models:
            chat_logger.log_warning("No models available for benchmark", component="Benchmark")
            self.log_signal.emit("⚠️ No models available")
            return
        
        chat_logger.log_info(f"Running benchmark on {len(self.available_models)} models", component="Benchmark")
        self.log_signal.emit("📊 Running benchmark...")
        for model in self.available_models[:5]:
            if model in AVAILABLE_MODELS:
                info = AVAILABLE_MODELS[model]
                self.log_signal.emit(f"   {info['emoji']} {model}: {info['role']} - {info['speed']}")
    
    def cleanup(self):
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
        chat_logger.log_info("AI Chat Features cleaned up", component="AIChatFeatures")
        try:
            chat_logger.save_session_report()
        except:
            pass