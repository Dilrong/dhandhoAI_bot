# app/handlers/commands.py
import time
from telegram import Update
from telegram.ext import ContextTypes
from app.utils.screening import daily_screening, manual_screening
from app.utils.logging import setup_logging

logger = setup_logging()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    welcome_message = (
        "매일 아침 9시에 나스닥과 S&P 500 종목을 스크리닝하여 단도원칙에 맞는 종목을 드립니다.\n"
        "또는 종목 티커(예: AAPL)를 입력하면 분석 결과를 드립니다.\n"
        "/screen 명령어로 즉시 스크리닝을 실행할 수 있습니다.\n"
        "사용법: /screen [all|nasdaq|sp500] (기본값: all)\n"
    )
    await update.message.reply_text(welcome_message)
    context.job_queue.run_daily(
        daily_screening, time=time(hour=0, minute=0), chat_id=chat_id
    )
    logger.info(f"사용자 {chat_id} 시작 명령 실행")

async def screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """수동으로 스크리닝 실행"""
    chat_id = update.message.chat_id
    args = context.args  # 명령어 뒤 인자
    scope = args[0].lower() if args else "all"
    
    if scope not in ["all", "nasdaq", "sp500"]:
        await update.message.reply_text(
            "잘못된 범위입니다. 사용법: /screen [all|nasdaq|sp500]"
        )
        return
    
    logger.info(f"사용자 {chat_id}가 /screen 명령어 실행 (scope: {scope})")
    await update.message.reply_text(f"📈 {scope.upper()} 스크리닝을 시작합니다...")
    
    # manual_screening 호출
    await manual_screening(context, chat_id, scope=scope, is_manual=True)
    
    logger.info(f"사용자 {chat_id} 스크리닝 완료")