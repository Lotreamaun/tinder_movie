from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.models.swipe import SwipeType, UserSwipe
from app.models.user import User
from app.config import settings

class SwipeService:
    def create_swipe(
        self,
        db: Session,
        user_id: str,
        movie_id: str,
        swipe_type: SwipeType,
        group_participants: list[int],
    ) -> UserSwipe:
        """
        Создает новый свайп с валидацией размера группы.
        
        Args:
            db (Session): Сессия БД
            user_id (str): ID пользователя
            movie_id (str): ID фильма
            swipe_type (SwipeType): Тип свайпа (like/dislike)
            group_participants (list[int]): Список telegram_id участников группы
            
        Returns:
            UserSwipe: Созданный свайп
            
        Raises:
            ValueError: Если размер группы превышает максимальный
        """
        # Валидация размера группы
        if len(group_participants) > settings.MAX_GROUP_SIZE:
            raise ValueError(f"Group size cannot exceed {settings.MAX_GROUP_SIZE} participants")
        
        if len(group_participants) < 2:
            raise ValueError("Group must have at least 2 participants")
            
        swipe = UserSwipe(
            user_id=user_id,
            movie_id=movie_id,
            swipe_type=swipe_type,
            group_participants=group_participants,
        )
        db.add(swipe)
        db.commit()
        db.refresh(swipe)
        return swipe


    def list_user_swipes(self, db: Session, user_id: str, limit: int = 50, offset: int = 0) -> Sequence[UserSwipe]:
        stmt = select(UserSwipe).where(UserSwipe.user_id == user_id).order_by(UserSwipe.swiped_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars())


    def get_swipe(self, db: Session, user_id: str, movie_id: str, group_participants: list[int]) -> Optional[UserSwipe]:
        stmt = select(UserSwipe).where(
            and_(
                UserSwipe.user_id == user_id,
                UserSwipe.movie_id == movie_id,
                UserSwipe.group_participants == group_participants,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def check_match(self, db: Session, movie_id: str, group_participants: list[int]) -> bool:
        """
        Проверяет, поставили ли все участники группы лайк фильму.
        
        Args:
            db (Session): Сессия БД
            movie_id (str): ID фильма
            group_participants (list[int]): Список telegram_id участников группы
            
        Returns:
            bool: True если все участники лайкнули фильм, False иначе
            
        Raises:
            ValueError: Если переданы некорректные параметры
        """
        try:
            # Валидация входных параметров
            if not movie_id:
                raise ValueError("Movie ID cannot be empty")
            
            if not group_participants or len(group_participants) < 2:
                raise ValueError("Group must have at least 2 participants")
                
            if len(group_participants) > settings.MAX_GROUP_SIZE:
                raise ValueError(f"Group size cannot exceed {settings.MAX_GROUP_SIZE} participants")
            
            # Получаем все лайки для данного фильма и группы
            stmt = (
                select(UserSwipe, User.telegram_id)
                .join(User, UserSwipe.user_id == User.id)
                .where(
                    and_(
                        UserSwipe.movie_id == movie_id,
                        UserSwipe.swipe_type == 'like',
                        UserSwipe.group_participants == group_participants
                    )
                )
            )
            results = db.execute(stmt).all()
            
            # Считаем уникальных пользователей по telegram_id, поставивших лайк
            unique_telegram_ids = set(result.telegram_id for result in results)
            
            # Мэтч, если количество уникальных лайков равно количеству участников группы
            return len(unique_telegram_ids) == len(group_participants)
            
        except Exception as e:
            # Логируем ошибку и возвращаем False для безопасности
            from app.logging_config import logger
            logger.error(f"Error in check_match: {e}", exc_info=True)
            return False

swipe_service = SwipeService()