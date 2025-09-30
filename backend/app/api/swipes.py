from fastapi import APIRouter, HTTPException, Depends, Header
from uuid import UUID
from typing import Annotated
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.swipe_service import swipe_service
from ..services.user_service import user_service
from .schemas import SwipeCreate, SwipeResponse, ApiResponse
from ..logging_config import logger

router = APIRouter(prefix="/api/swipes", tags=["swipes"])

@router.post("/", response_model=ApiResponse[SwipeResponse], responses={
    404: {"description": "Пользователь не найден"},
    400: {"description": "Некорректные данные свайпа"},
    500: {"description": "Внутренняя ошибка сервера"}
})
def create_swipe(
    swipe: SwipeCreate,
    telegram_id: Annotated[int, Header(description="Telegram ID пользователя")],
    db: Session = Depends(get_db)
) -> ApiResponse[SwipeResponse]:
    """
    Создание нового свайпа.
    
    Args:
        swipe (SwipeCreate): Данные свайпа
        telegram_id (int): Telegram ID пользователя из заголовка запроса
        db (Session): Сессия базы данных
        
    Returns:
        ApiResponse[SwipeResponse]: Созданный свайп
        
    Raises:
        HTTPException: Если пользователь не найден, фильм не найден или возникла другая ошибка
    """
    try:
        # Получаем пользователя по telegram_id
        user = user_service.get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Создаем свайп
        db_swipe = swipe_service.create_swipe(db=db, **swipe.model_dump(), user_id=str(user.id))
        
        # Проверяем на матч если это лайк
        if swipe.swipe_type == 'like':
            match_found = swipe_service.check_match(
                movie_id=swipe.movie_id,
                group_participants=swipe.group_participants
            )
            if match_found:
                logger.info(f"Match found for movie {swipe.movie_id} and group {swipe.group_participants}")
                
        return ApiResponse(success=True, data=db_swipe)
    
    except ValueError as e:
        logger.warning(f"Invalid swipe data: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create swipe: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/user/{user_id}", response_model=ApiResponse[list[SwipeResponse]])
async def get_user_swipes(user_id: UUID) -> ApiResponse[list[SwipeResponse]]:
    """
    Получение всех свайпов пользователя.
    
    Args:
        user_id (UUID): ID пользователя
        
    Returns:
        ApiResponse[list[SwipeResponse]]: Список свайпов пользователя
        
    Raises:
        HTTPException: Если пользователь не найден
    """
    try:
        # Проверяем существование пользователя
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        swipes = await swipe_service.get_user_swipes(user_id)
        return ApiResponse(success=True, data=swipes)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user swipes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
