from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["/help"]]
    if update.effective_user:
        logger.info("/start from user_id=%s username=%s", update.effective_user.id, update.effective_user.username)
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