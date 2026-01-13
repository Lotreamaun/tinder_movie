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
        log_level: Уровень логирования 
        (DEBUG — детальная информация для отладки, INFO — основная информация, WARNING — предупреждения, ERROR — ошибки)
        log_file: Путь к файлу логов
        
    Returns:
        Настроенный логгер
    """
    # Создаем папку для логов
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Настройка форматирования
    formatter = logging.Formatter(
        """
        Формат логирования:
        %(asctime)s — дата и время
        %(name)s — имя логгера (tinder_movie)
        %(levelname)s — уровень логирования (DEBUG, INFO, WARNING, ERROR)
        %(message)s — сообщение
        datefmt='%Y-%m- %H:%M:%S' — формат даты и времени (2026-01-11 12:00:00)
        """
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Основной логгер
    """
    Функция logging.getLogger() создает и возвращает экземпляр класса с заданным именем:
    внутри logging есть реестр логгеров, который хранит все созданные логгеры и их экземпляры
    если логгер с таким именем уже существует, то функция вернет его экземпляр
    если нет, то функция создаст новый логгер с именем 'tinder_movie' и вернет его экземпляр
    """
    logger = logging.getLogger('tinder_movie')
    
    """
    Функция getattr() возвращает значение атрибута с именем log_level.upper() из модуля logging,
    log_level.upper() - это строка 'INFO', 'DEBUG', 'WARNING', 'ERROR' в верхнем регистре
    getattr() получает числовое значение уровня логирования из модуля logging,
    потому что уровени логирования — это числовые константы, которые определены в модуле logging.
    Например, logging.INFO – 20, logging.DEBUG – 10, logging.WARNING – 30, logging.ERROR – 40.
    После установки уровня логер не будет пропускать сообщения ниже этого уровня.
    """
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие хендлеры
    logger.handlers.clear()
    
    # Консольный хендлер
    """
    StreamHeandler() — это вывод логов в консоль
    setLevel() — устанавливает тот же уровень логирования, что и у логгер
    setFormatter() — применяет наш formatter
    addHandler() — добавляет этот хендлер к логгеру, чтобы сообщения отправлялись в консоль
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый хендлер (ротация по дням)
    """
    Хендлер — это компонент, который определяет куда и как записывать логи.
    TimedRotatingFileHandler() — это хендлер, который записывает логи в файл:
    
        Args:
            log_file = "logs/app.log" - базовое имя файла, куда записываются логи
            when:'midnight': когда ротировать (есть секунды, минуты, часы, дни и тд)
            interval=1: каждый день
            backupCount=30: сколько резервных копий хранить

    Ротирование - это создание, переименование и уделание файлов логов

    Каждый день логер создает новый файл app.log, а предыдущий переименовывается в дату (напр. app.log.2025-11-11)
    """
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30  # храним 30 дней
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Отдельный файл только для ошибок
    error_log_file = str(log_path.parent / "errors.log")
    error_handler = logging.handlers.TimedRotatingFileHandler(
        # Логика создания хендлера такая же, как и в блоке выше
        error_log_file,
        when='midnight',
        interval=1,
        backupCount=90  # храним 90 дней
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Функция возвращает настроенный объект логгера
    return logger

# Создаем экземпляр для импорта в другие модули
logger = setup_logging()