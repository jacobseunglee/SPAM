"""Logging configuration for SPAM (Scripting Proxmox Automation Magic)"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    enable_console: bool = True
) -> logging.Logger:
    """
    Setup logging configuration for SPAM
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        log_format: Custom log format (optional)
        enable_console: Whether to enable console logging
    
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Default log format
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)


def configure_spam_logging() -> logging.Logger:
    """Configure default logging for SPAM application"""
    log_level = os.getenv('SPAM_LOG_LEVEL', 'INFO')
    log_file = os.getenv('SPAM_LOG_FILE')
    
    if not log_file:
        # Default log file location
        log_dir = Path.home() / '.spam' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / 'spam.log')
    
    return setup_logging(
        level=log_level,
        log_file=log_file,
        enable_console=True
    )


# Logger instances for different modules
def get_clone_logger() -> logging.Logger:
    return get_logger('spam.clone')


def get_status_logger() -> logging.Logger:
    return get_logger('spam.status')


def get_snapshot_logger() -> logging.Logger:
    return get_logger('spam.snapshot')


def get_utils_logger() -> logging.Logger:
    return get_logger('spam.utils')


def get_config_logger() -> logging.Logger:
    return get_logger('spam.config')