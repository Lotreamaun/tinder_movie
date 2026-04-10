"""
API-эндпоинты для работы с комнатами: 
получение текущей комнаты пользователя, информации о комнате и участниках.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Annotated
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.user_service import user_service
from ..services.room_service import room_service
from .schemas import ApiResponse
from ..logging_config import logger

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("/my", response_model=ApiResponse[dict])
def get_my_room(
    telegram_id: Annotated[int, Header(description="Telegram ID пользователя")],
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    """
    Получает текущую комнату пользователя с информацией об участниках.

    Args:
        telegram_id: Telegram ID пользователя из заголовка
        db: Сессия БД

    Returns:
        Информация о комнате и участниках, или None если пользователь не в комнате
    """
    try:
        user = user_service.get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        room = room_service.get_user_current_room(db, user)
        if not room:
            return ApiResponse(success=True, data=None)

        room_info = room_service.get_room_info(db, room.id)
        return ApiResponse(success=True, data=room_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user room: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
