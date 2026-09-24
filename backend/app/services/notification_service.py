"""
Сервис для отправки уведомлений в Telegram
"""
import asyncio
import threading
from telegram import Bot
from telegram.error import TelegramError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.match import Match
from app.models.room import Room
from app.models.user import User
from app.services.movie_service import movie_service
from app.logging_config import logger


class NotificationService:
    """Сервис для отправки уведомлений о матчах"""
    
    def __init__(self):
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN не задан, уведомления не будут отправляться")
            self.bot = None
        else:
            self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    async def _send_match_notification_async(self, match_id: str, movie_id: str, group_participants: list[int]) -> bool:
        """
        Асинхронная отправка уведомления о матче всем участникам группы.
        
        Args:
            match_id: ID матча
            movie_id: ID фильма
            group_participants: Список telegram_id участников группы
            
        Returns:
            bool: True если хотя бы одно уведомление отправлено успешно
        """
        if not self.bot:
            logger.warning("Bot not initialized, skipping notification")
            return False
        
        # Создаем новую сессию БД для асинхронного контекста
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            # Получаем информацию о фильме
            movie = movie_service.get_movie_by_id(db, movie_id)
            if not movie:
                logger.error(f"Movie {movie_id} not found for match {match_id}")
                return False
            
            # Формируем сообщение
            message = "🎬 Найден матч!\n\n"
            message += f"Фильм: {movie.title}"
            if movie.year:
                message += f" ({movie.year})"
            message += "\n\nВсе участники группы лайкнули этот фильм!"
            
            success_count = 0
            # Отправляем каждому участнику группы
            for telegram_id in group_participants:
                try:
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message
                    )
                    success_count += 1
                    logger.info(f"Match notification sent to user {telegram_id} for match {match_id}")
                except TelegramError as e:
                    logger.error(f"Failed to send notification to {telegram_id}: {e}")
            
            return success_count > 0
        finally:
            db.close()
    
    def send_match_notification(self, match: Match, db: Session) -> None:
        """
        Отправляет уведомление о матче в фоновом режиме (не блокирует).
        
        Args:
            match: Объект матча
            db: Сессия БД (используется только для чтения данных перед запуском фоновой задачи)
        """
        # Извлекаем данные до запуска фоновой задачи
        match_id = str(match.id)
        movie_id = str(match.movie_id)
        group_participants = match.group_participants.copy()
        
        def run_async():
            """Запускает асинхронную функцию в новом event loop"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self._send_match_notification_async(match_id, movie_id, group_participants)
                )
                loop.close()
            except Exception as e:
                logger.error(f"Error in async notification task: {e}", exc_info=True)
        
        # Запускаем в отдельном потоке, чтобы не блокировать основной поток
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        logger.info(f"Notification task started for match {match_id}")

    async def _send_room_join_notification_async(
        self,
        room_code: str,
        recipients: list[int],
        joined_name: str,
        participants_count: int,
    ) -> bool:
        """
        Асинхронная отправка уведомления о присоединении нового участника
        остальным участникам комнаты.

        Args:
            room_code: Код комнаты
            recipients: Список telegram_id получателей (без самого присоединившегося)
            joined_name: Отображаемое имя присоединившегося пользователя
            participants_count: Итоговое число участников комнаты

        Returns:
            bool: True если хотя бы одно уведомление отправлено успешно
        """
        if not self.bot:
            logger.warning("Bot not initialized, skipping room join notification")
            return False

        message = (
            f"🆕 В комнату {room_code} присоединился новый участник: {joined_name}\n\n"
            f"👥 Теперь участников: {participants_count}"
        )

        success_count = 0
        for telegram_id in recipients:
            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message
                )
                success_count += 1
                logger.info(f"Room join notification sent to user {telegram_id} for room {room_code}")
            except TelegramError as e:
                logger.error(f"Failed to send room join notification to {telegram_id}: {e}")

        return success_count > 0

    def send_room_join_notification(self, room: Room, joined_user: User, db: Session) -> None:
        """
        Отправляет уведомление остальным участникам комнаты о присоединении
        нового человека в фоновом режиме (не блокирует).

        Args:
            room: Комната после присоединения (participants уже включает joined_user)
            joined_user: Пользователь, который присоединился
            db: Сессия БД (не используется — все нужные данные извлекаются из
                ORM-объектов до запуска фоновой задачи)
        """
        room_code = room.id
        recipients = [tid for tid in room.participants if tid != joined_user.telegram_id]
        if not recipients or not self.bot:
            return

        joined_name = joined_user.first_name
        if joined_user.username:
            joined_name += f" (@{joined_user.username})"
        participants_count = len(room.participants)

        def run_async():
            """Запускает асинхронную функцию в новом event loop"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self._send_room_join_notification_async(
                        room_code, recipients, joined_name, participants_count
                    )
                )
                loop.close()
            except Exception as e:
                logger.error(f"Error in async room join notification task: {e}", exc_info=True)

        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        logger.info(f"Room join notification task started for room {room_code}")


notification_service = NotificationService()

