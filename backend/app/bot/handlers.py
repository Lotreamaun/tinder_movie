from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.services.user_service import user_service

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["/help"]]
    user = update.effective_user
    
    if user:
        try:
            db = SessionLocal()
            try:
                # Проверяем, существует ли пользователь
                db_user = user_service.get_user_by_telegram_id(db, user.id)
                
                if not db_user:
                    # Создаем нового пользователя
                    db_user = user_service.create_user(
                        db=db,
                        telegram_id=user.id,
                        first_name=user.first_name,
                        username=user.username
                    )
                    logger.info("Created new user: telegram_id=%s username=%s", user.id, user.username)
                else:
                    # Обновляем имя пользователя, если оно изменилось
                    db_user = user_service.update_user_name(
                        db=db,
                        user=db_user,
                        first_name=user.first_name,
                        username=user.username
                    )
                    logger.info("Updated existing user: telegram_id=%s username=%s", user.id, user.username)
            
            finally:
                db.close()
                
        except IntegrityError as e:
            logger.error("Database integrity error: %s", str(e))
        except Exception as e:
            logger.error("Error processing user: %s", str(e))
    
    await update.message.reply_text(
        "Привет! Я Movie Tinder Bot 👋",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("/help from user_id=%s username=%s", update.effective_user.id, update.effective_user.username)
    await update.message.reply_text(
        "Доступные команды:\n/start — приветствие\n/help — помощь"
    )


def build_app() -> Application:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    return Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()


def run_polling() -> None:
    app = build_app()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    logger.info("Starting Telegram bot polling")
    app.run_polling(close_loop=False)