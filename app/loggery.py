import json
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from typing import List, Optional, Dict, Any

from .config import settings


class AccessLogger:
    """Logs access patterns for audit and monitoring"""

    def __init__(self):
        self.logger = logging.getLogger('access_audit')
        self.enabled = settings.security.ENABLE_ACCESS_LOGGING
        if not self.logger.handlers:
            handler = None
            try:
                import os
                file_path = settings.security.ACCESS_LOG_FILE
                if file_path:
                    dir_path = os.path.dirname(file_path)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    handler = TimedRotatingFileHandler(file_path, when='midnight', interval=1, backupCount=settings.security.LOG_BACKUP_COUNT, encoding='utf-8')
            except Exception:
                handler = None
            if handler is None:
                handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_query_access(
        self,
        user_context,
        query: str,
        entities_accessed: Optional[List[str]] = None,
        success: bool = True,
        error_message: str = None
    ):
        if not self.enabled:
            return
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'role': getattr(user_context, 'role', None),
                'scoping_value': getattr(user_context, 'scoping_value', None),
                'query_hash': hash(query) % 1000000,
                'entities_accessed': entities_accessed or [],
                'success': success,
                'error_message': error_message,
                'request_id': getattr(user_context, 'request_id', None)
            }
            self.logger.info(f"Query Access: {json.dumps(log_data)}")
        except Exception:
            pass


class QueryLogger:
    """Logs NL2SQL queries, generated SQL, metadata for analytics and improvement"""

    def __init__(self):
        self.enabled = settings.security.ENABLE_QUERY_LOGGING
        self.file_path = settings.security.QUERY_LOG_FILE
        self.logger = logging.getLogger('query_events')
        if not self.logger.handlers:
            handler = None
            try:
                import os
                if self.file_path:
                    dir_path = os.path.dirname(self.file_path)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    handler = TimedRotatingFileHandler(self.file_path, when='midnight', interval=1, backupCount=settings.security.LOG_BACKUP_COUNT, encoding='utf-8')
            except Exception:
                handler = None
            if handler is None:
                # Fallback to stdout if file path is not writable
                handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_event(
        self,
        user_context,
        question: str,
        provider: str,
        relevant_tables: List[str],
        schema_tokens: int,
        attempts: int,
        success: bool,
        sql: str = None,
        error: str = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        if not self.enabled:
            return
        try:
            event = {
                'timestamp': datetime.now().isoformat(),
                'role': getattr(user_context, 'role', None),
                'scoping_value': getattr(user_context, 'scoping_value', None),
                'question_hash': hash(question) % 1000000,
                'question': question,
                'provider': provider,
                'relevant_tables': relevant_tables or [],
                'schema_tokens': schema_tokens,
                'attempts': attempts,
                'success': success,
                'sql': (sql or '').strip(),
                'error': error,
                'error_details': error_details or {},
                'request_id': getattr(user_context, 'request_id', None)
            }
            self.logger.info(json.dumps(event))
        except Exception:
            pass


# Global singletons
access_logger = AccessLogger()
query_logger = QueryLogger()


