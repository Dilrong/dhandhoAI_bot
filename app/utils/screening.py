import time
import pandas as pd
from telegram.ext import ContextTypes
from app.utils.stock import analyze_stock, fetch_nasdaq_tickers, fetch_sp500_tickers
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
            await context.bot.send_message(chat_id=chat_id, text=message)  # await 추가
            message = ""
        
        NASDAQ_TICKERS = fetch_nasdaq_tickers()
        if not NASDAQ_TICKERS:
            message += "나스닥 티커 데이터를 가져오지 못했습니다.\n"
        else:
            nasdaq_results = [
                result for ticker in NASDAQ_TICKERS if (result := analyze_stock(ticker, include_description=False)) is not None
            ]
            if nasdaq_results:
                nasdaq_df = pd.DataFrame(nasdaq_results)
                nasdaq_candidates = nasdaq_df[nasdaq_df["buy_recommendation"] == True]
                if not nasdaq_candidates.empty:
                    message += "=== 나스닥 매수 추천 ===\n"
                    for _, row in nasdaq_candidates.iterrows():
                        message += f"{row['ticker']}: ${row['current_price']} (내재가치: ${row['intrinsic_value']}, 안전마진: {row['safety_margin']}%)\n"
                else:
                    message += "추천 종목 없음\n"
            else:
                message += "분석 가능한 나스닥 종목이 없습니다.\n"
    
    if scope in ["all", "sp500"]:
        message += "\n📈 S&P 500 종목 분석 중...\n"
        if is_manual:
            await context.bot.send_message(chat_id=chat_id, text=message)  # await 추가
            message = ""
        
        SP500_TICKERS = fetch_sp500_tickers()
        if not SP500_TICKERS:
            message += "S&P 500 티커 데이터를 가져오지 못했습니다.\n"
        else:
            sp500_results = [
                result for ticker in SP500_TICKERS if (result := analyze_stock(ticker, include_description=False)) is not None
            ]
            if sp500_results:
                sp500_df = pd.DataFrame(sp500_results)
                sp500_candidates = sp500_df[sp500_df["buy_recommendation"] == True]
                if not sp500_candidates.empty:
                    message += "=== S&P 500 매수 추천 ===\n"
                    for _, row in sp500_candidates.iterrows():
                        message += f"{row['ticker']}: ${row['current_price']} (내재가치: ${row['intrinsic_value']}, 안전마진: {row['safety_margin']}%)\n"
                else:
                    message += "추천 종목 없음\n"
            else:
                message += "분석 가능한 S&P 500 종목이 없습니다.\n"
    
    await context.bot.send_message(chat_id=chat_id, text=message)  # await 추가
    logger.info(f"스크리닝 완료 (scope: {scope})")