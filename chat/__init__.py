"""Chat Tab Package"""

from .ai_chat import AIChatTab

# Try to import chat logger components if available
try:
    from .chat_log.chat_logger import chat_logger
    from .chat_log.chat_log_viewer import ChatLogViewer
    __all__ = ['AIChatTab', 'chat_logger', 'ChatLogViewer']
except ImportError:
    __all__ = ['AIChatTab']