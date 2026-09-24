from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.services.user_service import user_service
from app.services.room_service import room_service

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
        "🎬 Movie Tinder Bot - команды:\n\n"
        "🚀 Основные:\n"
        "/start — приветствие и регистрация\n"
        "/help — эта справка\n\n"
        "🏠 Комнаты:\n"
        "/create_room — создать новую комнату\n"
        "/join_room <КОД> — присоединиться к комнате\n"
        "/leave_room — выйти из текущей комнаты\n"
        "/room_info — показать участников комнаты\n\n"
        "💡 Как пользоваться:\n"
        "1. Один человек создает комнату (/create_room)\n"
        "2. Другие присоединяются по коду (/join_room ABC123)\n"
        "3. Все участники видят одинаковые фильмы\n"
        "4. При взаимных лайках создается матч!"
    )


async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Создает новую комнату и добавляет пользователя в неё"""
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return

    try:
        db = SessionLocal()
        try:
            # Получаем пользователя из БД
            db_user = user_service.get_user_by_telegram_id(db, user.id)
            if not db_user:
                await update.message.reply_text("❌ Сначала выполните /start для регистрации")
                return

            # Проверяем, не в комнате ли уже пользователь
            current_room = room_service.get_user_current_room(db, db_user)
            if current_room:
                await update.message.reply_text(
                    f"❌ Вы уже в комнате {current_room.id}\n"
                    "Сначала выйдите из неё командой /leave_room"
                )
                return

            # Создаем комнату
            room = room_service.create_room(db, db_user)

            await update.message.reply_text(
                f"🏠 Комната создана!\n\n"
                f"📋 Код комнаты: `{room.id}`\n"
                f"👥 Участники: 1 (вы)\n\n"
                f"📤 Поделитесь кодом с друзьями!\n"
                f"Они смогут присоединиться командой:\n"
                f"`/join_room {room.id}`",
                parse_mode='Markdown'
            )

            logger.info("Room created: %s by user %s", room.id, user.id)

        finally:
            db.close()

    except Exception as e:
        logger.error("Error creating room for user %s: %s", user.id, str(e))
        await update.message.reply_text("❌ Произошла ошибка при создании комнаты")


async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Присоединяется к комнате по коду"""
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return

    # Получаем код комнаты из аргументов
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Укажите код комнаты!\n\n"
            "Пример: `/join_room ABC123`\n\n"
            "Получите код у создателя комнаты"
        )
        return

    room_code = args[0].upper()  # Код всегда в верхнем регистре

    try:
        db = SessionLocal()
        try:
            # Получаем пользователя из БД
            db_user = user_service.get_user_by_telegram_id(db, user.id)
            if not db_user:
                await update.message.reply_text("❌ Сначала выполните /start для регистрации")
                return

            # Проверяем, не в комнате ли уже пользователь
            current_room = room_service.get_user_current_room(db, db_user)
            if current_room:
                await update.message.reply_text(
                    f"❌ Вы уже в комнате {current_room.id}\n"
                    "Сначала выйдите из неё командой /leave_room"
                )
                return

            # Присоединяемся к комнате
            room = room_service.join_room(db, db_user, room_code)

            await update.message.reply_text(
                f"✅ Вы присоединились к комнате `{room_code}`!\n\n"
                f"👥 Участников: {len(room.participants)}\n\n"
                f"🎬 Теперь вы видите одинаковые фильмы с другими участниками!\n"
                f"Используйте кнопки лайк/дизлайк для свайпов.",
                parse_mode='Markdown'
            )

            logger.info("User %s joined room %s", user.id, room_code)

        finally:
            db.close()

    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")
    except Exception as e:
        logger.error("Error joining room for user %s: %s", user.id, str(e))
        await update.message.reply_text("❌ Произошла ошибка при присоединении к комнате")


async def leave_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выходит из текущей комнаты"""
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return

    try:
        db = SessionLocal()
        try:
            # Получаем пользователя из БД
            db_user = user_service.get_user_by_telegram_id(db, user.id)
            if not db_user:
                await update.message.reply_text("❌ Сначала выполните /start для регистрации")
                return

            # Находим текущую комнату пользователя
            current_room = room_service.get_user_current_room(db, db_user)
            if not current_room:
                await update.message.reply_text("❌ Вы не состоите ни в одной комнате")
                return

            # Выходим из комнаты
            room = room_service.leave_room(db, db_user, current_room.id)

            await update.message.reply_text(
                f"✅ Вы вышли из комнаты `{current_room.id}`\n\n"
                f"👥 Осталось участников: {len(room.participants)}\n\n"
                f"🏠 Для создания новой комнаты используйте /create_room"
            )

            logger.info("User %s left room %s", user.id, current_room.id)

        finally:
            db.close()

    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")
    except Exception as e:
        logger.error("Error leaving room for user %s: %s", user.id, str(e))
        await update.message.reply_text("❌ Произошла ошибка при выходе из комнаты")


async def room_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о текущей комнате"""
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Не удалось определить пользователя")
        return

    try:
        db = SessionLocal()
        try:
            # Получаем пользователя из БД
            db_user = user_service.get_user_by_telegram_id(db, user.id)
            if not db_user:
                await update.message.reply_text("❌ Сначала выполните /start для регистрации")
                return

            # Находим текущую комнату пользователя
            current_room = room_service.get_user_current_room(db, db_user)
            if not current_room:
                await update.message.reply_text(
                    "❌ Вы не состоите ни в одной комнате\n\n"
                    "🏠 Создайте комнату: /create_room\n"
                    "🔗 Присоединитесь: /join_room <КОД>"
                )
                return

            # Получаем информацию о комнате
            room_info_data = room_service.get_room_info(db, current_room.id)

            # Формируем сообщение (обычный текст — имя/юзернейм участника приходят
            # от пользователя и не должны интерпретироваться как Markdown-разметка)
            message = f"🏠 Комната {room_info_data['room_code']}\n\n"
            message += f"👥 Участники ({room_info_data['participants_count']}):\n"

            for participant in room_info_data['participants']:
                name = participant['first_name']
                if participant['username']:
                    name += f" (@{participant['username']})"
                message += f"• {name}\n"

            message += f"\n📅 Создана: {room_info_data['created_at'].strftime('%d.%m.%Y %H:%M')}"

            await update.message.reply_text(message)

            logger.info("Room info shown for user %s, room %s", user.id, current_room.id)

        finally:
            db.close()

    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")
    except Exception as e:
        logger.error("Error getting room info for user %s: %s", user.id, str(e))
        await update.message.reply_text("❌ Произошла ошибка при получении информации о комнате")


def build_app() -> Application:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    return Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()


def run_polling() -> None:
    app = build_app()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # Команды управления комнатами
    app.add_handler(CommandHandler("create_room", create_room))
    app.add_handler(CommandHandler("join_room", join_room))
    app.add_handler(CommandHandler("leave_room", leave_room))
    app.add_handler(CommandHandler("room_info", room_info))

    logger.info("Starting Telegram bot polling")
    app.run_polling(close_loop=False)