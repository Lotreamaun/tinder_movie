from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated
from uuid import UUID
from sqlalchemy.orm import Session
from ..database import get_db

from ..services.user_service import user_service
from .schemas import UserCreate, UserResponse, ApiResponse
from ..logging_config import logger

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/", response_model=ApiResponse[UserResponse])
def create_user(user: UserCreate, db: Session = Depends(get_db)) -> ApiResponse[UserResponse]:
    """
    Создание нового пользователя.
    
    Args:
        user (UserCreate): Данные пользователя
        
    Returns:
        ApiResponse[UserResponse]: Созданный пользователь
        
    Raises:
        HTTPException: Если пользователь с таким telegram_id уже существует
    """
    try:
        db_user = user_service.create_user(db=db, **user.model_dump())
        return ApiResponse(success=True, data=db_user)
    except Exception as e:
        logger.error(f"Failed to create user: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.get("/id/{id}", response_model=ApiResponse[UserResponse])
def get_user(id: UUID, db: Session = Depends(get_db)) -> ApiResponse[UserResponse]:
    """
    Получение пользователя по ID.
    
    Args:
        id (UUID): ID пользователя
        
    Returns:
        ApiResponse[UserResponse]: Данные пользователя
        
    Raises:
        HTTPException: Если пользователь не найден
    """
    try:
        user = user_service.get_user_by_id(db=db, id=str(id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return ApiResponse(success=True, data=user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/telegram_id/{telegram_id}", response_model=ApiResponse[UserResponse])
def get_user_by_telegram(telegram_id: int, db: Session = Depends(get_db)) -> ApiResponse[UserResponse]:
    try:
        user = user_service.get_user_by_telegram_id(db=db, telegram_id=telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return ApiResponse(success=True, data=user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )