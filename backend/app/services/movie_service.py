from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.movie import Movie

class MovieService:
    def create_movie(
        self,
        db: Session,
        kinopoisk_id: int,
        title: str,
        year: int,
        genre: str,
        poster_url: str,
        title_original: Optional[str] = None,
        description: Optional[str] = None,
        rating: Optional[float] = None,
    ) -> Movie:
        movie = Movie(
            kinopoisk_id=kinopoisk_id,
            title=title,
            title_original=title_original,
            year=year,
            genre=genre,
            poster_url=poster_url,
            description=description,
            rating=rating,
        )
        db.add(movie)
        db.commit()
        db.refresh(movie)
        return movie
    
    def get_random_movie(self, db: Session) -> Optional[Movie]:
        stmt = select(Movie).order_by(func.random()).limit(1)
        return db.execute(stmt).scalar_one_or_none()


    def get_movie_by_id(self, db: Session, id: str) -> Optional[Movie]:
        return db.get(Movie, id)


    def get_movie_by_kinopoisk_id(self, db: Session, kinopoisk_id: int) -> Optional[Movie]:
        stmt = select(Movie).where(Movie.kinopoisk_id == kinopoisk_id)
        return db.execute(stmt).scalar_one_or_none()


    def list_movies(self, db: Session, limit: int = 50, offset: int = 0) -> Sequence[Movie]:
        stmt = select(Movie).order_by(Movie.created_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars())


    def update_movie_active(self, db: Session, movie: Movie, is_active: bool) -> Movie:
        movie.is_active = is_active
        db.add(movie)
        db.commit()
        db.refresh(movie)
        return movie


    def delete_movie(self, db: Session, movie: Movie) -> None:
        db.delete(movie)
        db.commit()

movie_service = MovieService()