from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi import Depends
from fastapi import Header
from uuid import UUID
from sqlalchemy.orm import Session

from ..services.movie_service import movie_service
from ..services.user_service import user_service
from ..services.room_service import room_service
from .schemas import MovieResponse, ApiResponse
from ..logging_config import logger
from ..database import get_db
from ..config import settings

router = APIRouter(prefix="/api/movies", tags=["movies"])

@router.get("/random", response_model=ApiResponse[MovieResponse], responses={
    400: {"description": "Некорректный room_code или пользователь не состоит в комнате"},
    404: {"description": "Нет доступных фильмов"},
    500: {"description": "Внутренняя ошибка сервера"}
})
def get_random_movie(
    telegram_id: Annotated[Optional[int], Header(description="Telegram ID пользователя")] = None,
    room_code: Annotated[Optional[str], Query(
        description="Код комнаты: фильм выдаётся из общего колода комнаты (пример: ABC123)"
    )] = None,
    db: Session = Depends(get_db)
) -> ApiResponse[MovieResponse]:
    """
    Получение фильма для свайпов.

    Без `room_code` возвращает случайный фильм из базы (прежнее поведение).

    С `room_code` возвращает следующий непросвайпанный фильм из общего
    упорядоченного колода комнаты — все участники видят одну последовательность,
    и матч становится достижимым. Для этого обязателен заголовок `telegram-id`
    (проверяется, что пользователь состоит в комнате).

    Returns:
        ApiResponse[MovieResponse]: Фильм для свайпов

    Raises:
        HTTPException: Если нет доступных фильмов или произошла ошибка
    """
    user = None
    if telegram_id is not None:
        user = user_service.get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    if room_code:
        if user is None:
            raise HTTPException(
                status_code=400,
                detail="telegram_id header is required when room_code is provided"
            )
        room = room_service.get_room_by_code(db, room_code)
        if not room or user.telegram_id not in room.participants:
            raise HTTPException(
                status_code=400,
                detail="User is not a member of this room"
            )

    try:
        movie = movie_service.get_random_movie(db=db, user=user, room_code=room_code)
        if not movie:
            raise HTTPException(
                status_code=404,
                detail="No movies available"
            )
        return ApiResponse(success=True, data=movie)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get random movie: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get movie"
        )

@router.get("/{id}", response_model=ApiResponse[MovieResponse])
def get_movie(id: UUID, db: Session = Depends(get_db)) -> ApiResponse[MovieResponse]:
    """
    Получение фильма по ID.

    Args:
        movie_id (UUID): ID фильма

    Returns:
        ApiResponse[MovieResponse]: Данные фильма

    Raises:
        HTTPException: Если фильм не найден
    """
    try:
        movie = movie_service.get_movie_by_id(db=db, id=str(id))
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        return ApiResponse(success=True, data=movie)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get movie: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
