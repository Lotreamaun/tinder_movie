"""
Мини-скрипт: создает тестового юзера и выводит в консоль.

Как работает:
  python -m app.scripts.verify_user_insert
"""
import uuid

from app.database import SessionLocal
from app.services.user_service import create_user, get_user_by_telegram_id


def main() -> None:
    db = SessionLocal()
    try:
        telegram_id = 999_000_111
        first_name = "Vladimir"
        username = "test_user"

        existing = get_user_by_telegram_id(db, telegram_id)
        if existing:
            print(f"User already exists: id={existing.id}, tg={existing.telegram_id}, name={existing.first_name}")
            return

        user = create_user(db, telegram_id=telegram_id, first_name=first_name, username=username)
        print(f"Created user: id={user.id}, tg={user.telegram_id}, name={user.first_name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()


