from fastapi import APIRouter, HTTPException
from uuid import UUID

from ..services.movie_service import movie_service
from .schemas import MovieResponse, ApiResponse
from ..logging_config import logger

router = APIRouter(prefix="/api/movies", tags=["movies"])

@router.get("/random", response_model=ApiResponse[MovieResponse])
async def get_random_movie() -> ApiResponse[MovieResponse]:
    """
    Получение случайного фильма для свайпов.
    
    Returns:
        ApiResponse[MovieResponse]: Случайный фильм из базы
        
    Raises:
        HTTPException: Если нет доступных фильмов или произошла ошибка
    """
    try:
        movie = await movie_service.get_random_movie()
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

@router.get("/{movie_id}", response_model=ApiResponse[MovieResponse])
async def get_movie(movie_id: UUID) -> ApiResponse[MovieResponse]:
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
        movie = await movie_service.get_movie(movie_id)
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
