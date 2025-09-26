from pydantic import BaseModel
from typing import Optional, Generic, TypeVar
from datetime import datetime
from uuid import UUID

# Базовые схемы
T = TypeVar('T')
class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None

# User schemas
class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: str

class UserResponse(BaseModel):
    id: UUID
    telegram_id: int
    username: Optional[str] = None
    first_name: str
    last_active: datetime

# Swipe schemas
class SwipeCreate(BaseModel):
    movie_id: UUID
    swipe_type: str  # 'like' или 'dislike'
    group_participants: list[int]  # список telegram_id участников

class SwipeResponse(BaseModel):
    id: UUID
    user_id: UUID
    movie_id: UUID
    swipe_type: str
    swiped_at: datetime
    group_participants: list[int]

# Movie schemas
class MovieBase(BaseModel):
    title: str
    title_original: Optional[str] = None
    year: int
    genre: str
    poster_url: str
    description: Optional[str] = None
    rating: Optional[float] = None

class MovieResponse(MovieBase):
    id: UUID
    kinopoisk_id: int
    created_at: datetime
    is_active: bool

# Match schemas
class MatchResponse(BaseModel):
    id: UUID
    movie_id: UUID
    matched_at: datetime
    is_notified: bool
    group_participants: list[int]
    movie: MovieResponse
