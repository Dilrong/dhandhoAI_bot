# app/main.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.config.config import TELEGRAM_TOKEN
from app.handlers.commands import start, screen
from app.handlers.messages import handle_message
from app.handlers.errors import error_handler
from app.utils.logging import setup_logging

logger = setup_logging()

def main():
    logger.info("Starting Dhandho Bot...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 핸들러 등록
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("screen", screen))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 에러 핸들러 등록
    application.add_error_handler(error_handler)
    
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == "__main__":
    main()