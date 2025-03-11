from telegram import Update
from telegram.ext import ContextTypes
from app.utils.stock import analyze_stock
from app.utils.logging import setup_logging

logger = setup_logging()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    logger.info(f"사용자 요청: {ticker} 분석")
    analysis = analyze_stock(ticker)
    if analysis:
        message = (
            f"📊 {ticker} 분석 결과\n"
            f"현재가: ${analysis['current_price']}\n"
            f"내재가치: ${analysis['intrinsic_value']}\n"
            f"안전마진: ${analysis['safety_margin']}%\n"
            f"매수추천: {'✅ 예' if analysis['buy_recommendation'] else '❌ 아니오'}\n"
            f"주식설명: {analysis['description']}\n"
        )
    else:
        message = f"❌ {ticker} 데이터를 가져올 수 없습니다."
    await update.message.reply_text(message)
    logger.info(f"{ticker} 분석 결과 전송 완료")