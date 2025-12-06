from typing import Optional, Sequence

from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload

from app.models.match import Match

class MatchService:
    def check_existing_match(self, db: Session, movie_id: str, group_participants: list[int]) -> Optional[Match]:
        """
        Проверяет, существует ли уже матч для данного фильма и группы.
        
        Args:
            db (Session): Сессия БД
            movie_id (str): ID фильма
            group_participants (list[int]): Список telegram_id участников группы
            
        Returns:
            Optional[Match]: Существующий матч или None
        """
        stmt = select(Match).where(
            and_(
                Match.movie_id == movie_id,
                Match.group_participants == group_participants
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def create_match(self, db: Session, movie_id: str, group_participants: list[int]) -> Match:
        """
        Создает новый матч, если он еще не существует.
        
        Args:
            db (Session): Сессия БД
            movie_id (str): ID фильма
            group_participants (list[int]): Список telegram_id участников группы
            
        Returns:
            Match: Созданный или существующий матч
        """
        # Проверяем, не существует ли уже такой матч
        existing_match = self.check_existing_match(db, movie_id, group_participants)
        if existing_match:
            return existing_match
            
        # Создаем новый матч
        match = Match(movie_id=movie_id, group_participants=group_participants)
        db.add(match)
        db.commit()
        db.refresh(match)
        
        # Отправляем уведомления в фоне (не блокируем создание матча)
        try:
            from app.services.notification_service import notification_service
            notification_service.send_match_notification(match, db)
            # Помечаем как отправленное (предполагаем успех)
            # В реальности уведомление может не отправиться, но для MVP это приемлемо
            match.is_notified = True
            db.add(match)
            db.commit()
        except Exception as e:
            from app.logging_config import logger
            logger.error(f"Failed to send match notification: {e}", exc_info=True)
            # Не падаем, матч уже создан
        
        return match


    def list_matches_for_group(self, db: Session, group_participants: list[int], limit: int = 50, offset: int = 0) -> Sequence[Match]:
        stmt = (
        select(Match)
        .where(Match.group_participants == group_participants)
        .order_by(Match.matched_at.desc())
        .limit(limit)
        .offset(offset)
        )
        return list(db.execute(stmt).scalars())
    
    def get_match_by_id(self, db: Session, match_id: str) -> Optional[Match]:
        """
        Получает матч по его ID.
        
        Args:
            db (Session): Сессия БД
            match_id (str): ID матча
            
        Returns:
            Optional[Match]: Найденный матч или None, если матч не найден
        """
        stmt = (
            select(Match)
            .where(Match.id == match_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    def mark_match_notified(self, db: Session, match: Match) -> Match:
        match.is_notified = True
        db.add(match)
        db.commit()
        db.refresh(match)
        return match

match_service = MatchService()