from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.match import Match


def create_match(db: Session, movie_id: str, group_participants: list[int]) -> Match:
    match = Match(movie_id=movie_id, group_participants=group_participants)
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def list_matches_for_group(db: Session, group_participants: list[int], limit: int = 50, offset: int = 0) -> Sequence[Match]:
    stmt = select(Match).where(Match.group_participants == group_participants).order_by(Match.matched_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def mark_match_notified(db: Session, match: Match) -> Match:
    match.is_notified = True
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


