from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User

class UserService:
    def create_user(self, db: Session, telegram_id: int, first_name: str, username: Optional[str] = None) -> User:
        user = User(telegram_id=telegram_id, first_name=first_name, username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


    def get_user_by_id(self, db: Session, id: str) -> Optional[User]:
        return db.get(User, id)


    def get_user_by_telegram_id(self, db: Session, telegram_id: int) -> Optional[User]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        return db.execute(stmt).scalar_one_or_none()


    def list_users(self, db: Session, limit: int = 50, offset: int = 0) -> Sequence[User]:
        stmt = select(User).order_by(User.last_active.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars())


    def update_user_name(self, db: Session, user: User, first_name: Optional[str] = None, username: Optional[str] = None) -> User:
        if first_name is not None:
            user.first_name = first_name
        if username is not None:
            user.username = username
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


    def delete_user(self, db: Session, user: User) -> None:
        db.delete(user)
        db.commit()

user_service = UserService()