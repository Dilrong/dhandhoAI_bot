# app/handlers/errors.py
from telegram import Update
from telegram.ext import ContextTypes
import telegram.error
from app.utils.logging import setup_logging

logger = setup_logging()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(f"Exception occurred: {error}")

    user_message = None

    if isinstance(error, telegram.error.Conflict):
        logger.error("Conflict detected: Multiple bot instances running.")
        user_message = "봇 충돌이 발생했습니다. 한 번에 하나의 인스턴스만 실행해주세요."
    elif isinstance(error, telegram.error.NetworkError):
        logger.error("Network issue encountered.")
        user_message = "네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    elif isinstance(error, telegram.error.BadRequest):
        logger.error("Bad request sent to Telegram API.")
        user_message = "잘못된 요청입니다. 입력을 확인해주세요."
    elif isinstance(error, telegram.error.InvalidToken):  # Unauthorized 대신 InvalidToken 사용
        logger.error("Invalid token: Unauthorized access.")
        user_message = "봇 토큰이 유효하지 않습니다. 관리자에게 문의해주세요."
    else:
        logger.error("Unhandled exception.")
        user_message = "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    if update and update.message and user_message:
        await update.message.reply_text(user_message)