"""
Настройка логирования для Movie Tinder Bot
"""
import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str = "logs/app.log") -> logging.Logger:
    """
    Настройка системы логирования
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        log_file: Путь к файлу логов
        
    Returns:
        Настроенный логгер
    """
    # Создаем папку для логов
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Настройка форматирования
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Основной логгер
    logger = logging.getLogger('tinder_movie')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие хендлеры
    logger.handlers.clear()
    
    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый хендлер (ротация по дням)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30  # храним 30 дней
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Отдельный файл для ошибок
    error_log_file = str(log_path.parent / "errors.log")
    error_handler = logging.handlers.TimedRotatingFileHandler(
        error_log_file,
        when='midnight',
        interval=1,
        backupCount=90  # храним 90 дней
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger
