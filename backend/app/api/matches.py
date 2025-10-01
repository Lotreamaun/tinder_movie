from fastapi import APIRouter, HTTPException, Depends, Query
from uuid import UUID
from typing import Annotated
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.match_service import match_service
from .schemas import MatchResponse, ApiResponse
from ..logging_config import logger

router = APIRouter(prefix="/api/matches", tags=["matches"])

@router.get("/group", response_model=ApiResponse[list[MatchResponse]])
def get_group_matches(
    participants: Annotated[str, Query(
        description="Список telegram_id через запятую, пример: 123,456,789",
        example="123456789,987654321",
        regex="^[0-9]+(,[0-9]+)*$"
    )], 
    db: Session = Depends(get_db)
) -> ApiResponse[list[MatchResponse]]:
    """
    Получение всех матчей для группы участников.
    
    Args:
        participants (str): Строка с telegram_id участников через запятую
        
    Returns:
        ApiResponse[list[MatchResponse]]: Список матчей группы
        
    Raises:
        HTTPException: Если возникла ошибка при получении матчей или неверный формат данных
    """
    try:
        # Преобразуем строку с ID в список чисел
        try:
            group_participants = [int(p.strip()) for p in participants.split(',')]
            if not group_participants:
                raise ValueError("Group participants list cannot be empty")
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid participants format: {str(e)}"
            )

        matches = match_service.list_matches_for_group(db=db, group_participants=group_participants)
        return ApiResponse(success=True, data=matches)
    except ValueError as e:
        logger.warning(f"Invalid group data: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get group matches: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/{match_id}", response_model=ApiResponse[MatchResponse])
def get_match(match_id: UUID, db: Session = Depends(get_db)) -> ApiResponse[MatchResponse]:
    """
    Получение конкретного матча по ID.
    
    Args:
        match_id (UUID): ID матча
        
    Returns:
        ApiResponse[MatchResponse]: Данные матча
        
    Raises:
        HTTPException: Если матч не найден
    """
    try:
        match = match_service.get_match_by_id(db=db, match_id = match_id)
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
        return ApiResponse(success=True, data=match)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get match: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
