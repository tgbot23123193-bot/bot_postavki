"""
Structured logging configuration for the application.

This module provides JSON-formatted logging with proper levels,
filtering, and rotation for production environments.
"""

import logging
import logging.handlers
import sys
from typing import Any, Dict, Optional
from pathlib import Path
import json
from datetime import datetime

import structlog
from structlog.typing import EventDict

from ..config import get_settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        if hasattr(record, 'api_key_id'):
            log_entry['api_key_id'] = record.api_key_id
        
        if hasattr(record, 'task_id'):
            log_entry['task_id'] = record.task_id
        
        if hasattr(record, 'warehouse_id'):
            log_entry['warehouse_id'] = record.warehouse_id
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add stack trace if present
        if record.stack_info:
            log_entry['stack_trace'] = record.stack_info
        
        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter for development."""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def add_request_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add request ID to log events."""
    # This could be enhanced to track request IDs in async context
    event_dict.setdefault("request_id", "unknown")
    return event_dict


def add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add timestamp to log events."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def setup_logging() -> None:
    """
    Setup application logging with proper handlers and formatters.
    
    Configures both standard logging and structlog for structured logging.
    """
    settings = get_settings()
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set log level
    log_level = getattr(logging, settings.logging.level.upper())
    root_logger.setLevel(log_level)
    
    # Create formatter based on configuration
    if settings.logging.format.lower() == 'json':
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # File handler if configured
    if settings.logging.file_path:
        file_path = Path(settings.logging.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=settings.logging.max_file_size,
            backupCount=settings.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    configure_library_loggers()
    
    # Setup structlog
    setup_structlog()
    
    # Log setup completion
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        level=settings.logging.level,
        format=settings.logging.format,
        file_path=settings.logging.file_path,
    )


def configure_library_loggers() -> None:
    """Configure logging levels for third-party libraries."""
    # Reduce noise from libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    # Keep important logs
    logging.getLogger("aiogram.dispatcher").setLevel(logging.INFO)
    logging.getLogger("wb_bot").setLevel(logging.DEBUG)


def setup_structlog() -> None:
    """Setup structlog for structured logging."""
    settings = get_settings()
    
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_timestamp,
        add_request_id,
    ]
    
    if settings.logging.format.lower() == 'json':
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=not settings.is_production())
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger for this class."""
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)


class UserLogger:
    """Logger with user context."""
    
    def __init__(self, user_id: int, logger: Optional[structlog.BoundLogger] = None):
        """
        Initialize user logger.
        
        Args:
            user_id: Telegram user ID
            logger: Base logger instance
        """
        self.user_id = user_id
        self.logger = logger or get_logger("user_actions")
        self.bound_logger = self.logger.bind(user_id=user_id)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with user context."""
        self.bound_logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with user context."""
        self.bound_logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with user context."""
        self.bound_logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with user context."""
        self.bound_logger.debug(message, **kwargs)


class TaskLogger:
    """Logger with monitoring task context."""
    
    def __init__(
        self, 
        task_id: int, 
        user_id: int, 
        warehouse_id: int,
        logger: Optional[structlog.BoundLogger] = None
    ):
        """
        Initialize task logger.
        
        Args:
            task_id: Monitoring task ID
            user_id: User ID
            warehouse_id: Warehouse ID
            logger: Base logger instance
        """
        self.logger = logger or get_logger("monitoring")
        self.bound_logger = self.logger.bind(
            task_id=task_id,
            user_id=user_id,
            warehouse_id=warehouse_id
        )
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with task context."""
        self.bound_logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with task context."""
        self.bound_logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with task context."""
        self.bound_logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with task context."""
        self.bound_logger.debug(message, **kwargs)


def log_api_request(
    method: str,
    url: str,
    status_code: Optional[int] = None,
    response_time: Optional[float] = None,
    error: Optional[str] = None,
    **kwargs
) -> None:
    """
    Log API request with structured data.
    
    Args:
        method: HTTP method
        url: Request URL
        status_code: Response status code
        response_time: Response time in seconds
        error: Error message if request failed
        **kwargs: Additional context
    """
    logger = get_logger("api_requests")
    
    log_data = {
        "method": method,
        "url": url,
        "status_code": status_code,
        "response_time": response_time,
        **kwargs
    }
    
    if error:
        logger.error("API request failed", error=error, **log_data)
    elif status_code and status_code >= 400:
        logger.warning("API request returned error", **log_data)
    else:
        logger.info("API request completed", **log_data)
