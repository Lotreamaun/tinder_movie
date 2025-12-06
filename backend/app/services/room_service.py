from typing import Optional, Sequence
import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.user import User
from app.config import settings


class RoomService:
    """Сервис для управления комнатами"""

    def generate_room_code(self) -> str:
        """Генерирует уникальный 6-символьный код комнаты (буквы + цифры)"""
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=6))
            # Проверяем уникальность (будет проверено при создании)
            return code

    def create_room(self, db: Session, creator: User) -> Room:
        """
        Создает новую комнату и добавляет создателя в участники.

        Args:
            db: Сессия БД
            creator: Пользователь-создатель

        Returns:
            Room: Созданная комната
        """
        # Генерируем уникальный код
        while True:
            room_code = self.generate_room_code()
            existing = self.get_room_by_code(db, room_code)
            if not existing:
                break

        # Создаем комнату
        room = Room(
            id=room_code,
            creator_id=str(creator.id),
            participants=[creator.telegram_id]  # Создатель автоматически входит в комнату
        )

        db.add(room)
        db.commit()
        db.refresh(room)

        return room

    def get_room_by_code(self, db: Session, room_code: str) -> Optional[Room]:
        """
        Получает комнату по коду.

        Args:
            db: Сессия БД
            room_code: Код комнаты

        Returns:
            Optional[Room]: Найденная комната или None
        """
        stmt = select(Room).where(Room.id == room_code)
        return db.execute(stmt).scalar_one_or_none()

    def join_room(self, db: Session, user: User, room_code: str) -> Room:
        """
        Добавляет пользователя в комнату.

        Args:
            db: Сессия БД
            user: Пользователь, который хочет присоединиться
            room_code: Код комнаты

        Returns:
            Room: Обновленная комната

        Raises:
            ValueError: Если комната не найдена или пользователь уже в ней
        """
        room = self.get_room_by_code(db, room_code)
        if not room:
            raise ValueError(f"Комната с кодом '{room_code}' не найдена")

        if user.telegram_id in room.participants:
            raise ValueError("Вы уже в этой комнате")

        # Проверяем лимит участников
        if len(room.participants) >= settings.MAX_ROOM_SIZE:
            raise ValueError(f"Комната заполнена (максимум {settings.MAX_ROOM_SIZE} участников)")

        # Добавляем пользователя
        room.participants.append(user.telegram_id)
        db.add(room)
        db.commit()
        db.refresh(room)

        return room

    def leave_room(self, db: Session, user: User, room_code: str) -> Room:
        """
        Удаляет пользователя из комнаты.

        Args:
            db: Сессия БД
            user: Пользователь, который хочет выйти
            room_code: Код комнаты

        Returns:
            Room: Обновленная комната

        Raises:
            ValueError: Если комната не найдена или пользователь не в ней
        """
        room = self.get_room_by_code(db, room_code)
        if not room:
            raise ValueError(f"Комната с кодом '{room_code}' не найдена")

        if user.telegram_id not in room.participants:
            raise ValueError("Вы не состоите в этой комнате")

        # Удаляем пользователя
        room.participants.remove(user.telegram_id)

        # Если комната пуста - удаляем её
        if not room.participants:
            db.delete(room)
            db.commit()
            raise ValueError("Комната была удалена (последний участник вышел)")

        db.add(room)
        db.commit()
        db.refresh(room)

        return room

    def get_room_info(self, db: Session, room_code: str) -> dict:
        """
        Получает информацию о комнате и её участниках.

        Args:
            db: Сессия БД
            room_code: Код комнаты

        Returns:
            dict: Информация о комнате с именами участников

        Raises:
            ValueError: Если комната не найдена
        """
        room = self.get_room_by_code(db, room_code)
        if not room:
            raise ValueError(f"Комната с кодом '{room_code}' не найдена")

        # Получаем пользователей по telegram_id
        from app.services.user_service import user_service
        participants = user_service.get_users_by_telegram_ids(db, room.participants)

        # Формируем информацию об участниках
        participants_info = []
        for participant in participants:
            participants_info.append({
                "telegram_id": participant.telegram_id,
                "first_name": participant.first_name,
                "username": participant.username
            })

        return {
            "room_code": room.id,
            "creator_id": room.creator_id,
            "participants_count": len(room.participants),
            "participants": participants_info,
            "created_at": room.created_at
        }

    def get_user_current_room(self, db: Session, user: User) -> Optional[Room]:
        """
        Получает текущую комнату пользователя (первую найденную).

        Args:
            db: Сессия БД
            user: Пользователь

        Returns:
            Optional[Room]: Текущая комната пользователя или None
        """
        stmt = select(Room).where(Room.participants.contains([user.telegram_id]))
        return db.execute(stmt).first()

    def list_user_rooms(self, db: Session, user: User, limit: int = 10) -> Sequence[Room]:
        """
        Получает список комнат пользователя.

        Args:
            db: Сессия БД
            user: Пользователь
            limit: Максимальное количество комнат

        Returns:
            Sequence[Room]: Список комнат пользователя
        """
        stmt = select(Room).where(Room.participants.contains([user.telegram_id])).limit(limit)
        return list(db.execute(stmt).scalars())


room_service = RoomService()
