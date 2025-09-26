from fastapi import APIRouter, HTTPException
from uuid import UUID

from ..services.match_service import match_service
from .schemas import MatchResponse, ApiResponse
from ..logging_config import logger

router = APIRouter(prefix="/api/matches", tags=["matches"])

@router.get("/group", response_model=ApiResponse[list[MatchResponse]])
async def get_group_matches(group_participants: list[int]) -> ApiResponse[list[MatchResponse]]:
    """
    Получение всех матчей для группы участников.
    
    Args:
        group_participants (list[int]): Список telegram_id участников группы
        
    Returns:
        ApiResponse[list[MatchResponse]]: Список матчей группы
        
    Raises:
        HTTPException: Если возникла ошибка при получении матчей
    """
    try:
        matches = await match_service.get_group_matches(group_participants)
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
async def get_match(match_id: UUID) -> ApiResponse[MatchResponse]:
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
        match = await match_service.get_match(match_id)
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
