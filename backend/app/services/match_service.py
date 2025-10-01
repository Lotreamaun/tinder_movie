from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.match import Match

class MatchService:
    def create_match(self, db: Session, movie_id: str, group_participants: list[int]) -> Match:
        match = Match(movie_id=movie_id, group_participants=group_participants)
        db.add(match)
        db.commit()
        db.refresh(match)
        return match


    def list_matches_for_group(self, db: Session, group_participants: list[int], limit: int = 50, offset: int = 0) -> Sequence[Match]:
        stmt = (
        select(Match)
        .where(Match.group_participants == group_participants)
        .order_by(Match.matched_at.desc())
        .limit(limit)
        .offset(offset)
        )
        return list(db.execute(stmt).scalars())
    
    def get_match_by_id(self, db: Session, match_id: str) -> Optional[Match]:
        """
        Получает матч по его ID.
        
        Args:
            db (Session): Сессия БД
            match_id (str): ID матча
            
        Returns:
            Optional[Match]: Найденный матч или None, если матч не найден
        """
        stmt = (
            select(Match)
            .where(Match.id == match_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    def mark_match_notified(self, db: Session, match: Match) -> Match:
        match.is_notified = True
        db.add(match)
        db.commit()
        db.refresh(match)
        return match

match_service = MatchService()