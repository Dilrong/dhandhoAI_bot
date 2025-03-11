# app/utils/screening.py
import time
import pandas as pd
from telegram.ext import ContextTypes
from app.utils.stock import analyze_stock, NASDAQ_TICKERS, SP500_TICKERS
from app.utils.logging import setup_logging

logger = setup_logging()

def daily_screening(context: ContextTypes.DEFAULT_TYPE):
    """매일 자동 실행되는 스크리닝"""
    chat_id = context.job.chat_id
    logger.info("일일 스크리닝 시작")
    manual_screening(context, chat_id, scope="all", is_manual=False)

async def manual_screening(context: ContextTypes.DEFAULT_TYPE, chat_id, scope="all", is_manual=True):
    """수동 또는 자동 스크리닝 실행"""
    if is_manual:
        logger.info(f"사용자 {chat_id}가 수동 스크리닝 요청 (scope: {scope})")
    
    timestamp = time.strftime('%Y-%m-%d %H:%M')
    message = f"📅 {timestamp} 스크리닝 결과\n"
    
    # 스크리닝 범위 설정
    if scope in ["all", "nasdaq"]:
        message += "\n📈 나스닥 종목 분석 중...\n"
        if is_manual:
            context.bot.send_message(chat_id=chat_id, text=message)  # 진행 상황 알림
            message = ""  # 초기화
        
        nasdaq_results = [
            analyze_stock(ticker) for ticker in NASDAQ_TICKERS[:10] if analyze_stock(ticker)
        ]
        nasdaq_df = pd.DataFrame(nasdaq_results)
        nasdaq_candidates = nasdaq_df[nasdaq_df["buy_recommendation"] == True]
        if not nasdaq_candidates.empty:
            message += "=== 나스닥 매수 추천 ===\n"
            for _, row in nasdaq_candidates.iterrows():
                message += f"{row['ticker']}: ${row['current_price']} (내재가치: ${row['intrinsic_value']}, 안전마진: {row['safety_margin']}%)\n"
        else:
            message += "추천 종목 없음\n"
    
    if scope in ["all", "sp500"]:
        message += "\n📈 S&P 500 종목 분석 중...\n"
        if is_manual:
            context.bot.send_message(chat_id=chat_id, text=message)  # 진행 상황 알림
            message = ""
        
        sp500_results = [
            analyze_stock(ticker) for ticker in SP500_TICKERS[:10] if analyze_stock(ticker)
        ]
        sp500_df = pd.DataFrame(sp500_results)
        sp500_candidates = sp500_df[sp500_df["buy_recommendation"] == True]
        if not sp500_candidates.empty:
            message += "=== S&P 500 매수 추천 ===\n"
            for _, row in sp500_candidates.iterrows():
                message += f"{row['ticker']}: ${row['current_price']} (내재가치: ${row['intrinsic_value']}, 안전마진: {row['safety_margin']}%)\n"
        else:
            message += "추천 종목 없음\n"
    
    context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"스크리닝 완료 (scope: {scope})")