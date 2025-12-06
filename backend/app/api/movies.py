from fastapi import APIRouter, HTTPException
from fastapi import Depends
from uuid import UUID
from sqlalchemy.orm import Session

from ..services.movie_service import movie_service
from .schemas import MovieResponse, ApiResponse
from ..logging_config import logger
from ..database import get_db
from ..config import settings

router = APIRouter(prefix="/api/movies", tags=["movies"])

@router.get("/random", response_model=ApiResponse[MovieResponse])
def get_random_movie(db: Session = Depends(get_db)) -> ApiResponse[MovieResponse]:
    """
    Получение случайного фильма для свайпов.
    
    Returns:
        ApiResponse[MovieResponse]: Случайный фильм из базы
        
    Raises:
        HTTPException: Если нет доступных фильмов или произошла ошибка
    """
    try:
        movie = movie_service.get_random_movie(db=db)
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

