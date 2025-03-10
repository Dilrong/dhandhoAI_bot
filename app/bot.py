import yfinance as yf
import pandas as pd
import schedule
import time
import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from .logging_config import setup_logging

logger = setup_logging()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN is not Found.")
    raise ValueError("TELEGRAM_TOKEN is not Found.")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def fetch_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        sp500_df = tables[0]
        logger.info("Success get S&P 500")
        return sp500_df['Symbol'].tolist()
    except Exception as e:
        logger.error(f"Failed S&P 500 | error: {e}")
        return []

def fetch_nasdaq_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        nasdaq_df = tables[3]
        logger.info("Success get Nasdaq 100")
        return nasdaq_df['Symbol'].tolist()
    except Exception as e:
        logger.error(f"Failed Nasdaq 100 | error: {e}")
        return []

NASDAQ_TICKERS = fetch_nasdaq_tickers()
SP500_TICKERS = fetch_sp500_tickers()

def fetch_stock_data(ticker, period="5y"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if not df.empty:
            logger.info(f"Success get {ticker} data")
            return df
        else:
            logger.warning(f"{ticker} data is empty")
            return None
    except Exception as e:
        logger.error(f"Failed get  {ticker} data | error: {e}")
        return None

def fetch_stock_description(ticker):
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY is not found.")
        return "설명 없음"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": f"{ticker} 주식에 대한 간단한 설명을 1~2문장으로 제공해주세요."}
        ],
        "max_tokens": 50
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        description = result['choices'][0]['message']['content'].strip()
        logger.info(f"Success get {ticker} description: {description}")
        return description
    except Exception as e:
        logger.error(f"Failed OpenRouter API ({ticker}) | error: {e}")
        return f"Failed get {ticker} data"

def analyze_stock(ticker):
    df = fetch_stock_data(ticker)
    if df is None:
        return None
    current_price = df['Close'][-1]
    info = yf.Ticker(ticker).info
    try:
        eps = info.get('trailingEps', 0)
        logger.info(f"{ticker} EPS: {eps}")
        intrinsic_value = eps * 15
        discount = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else 0
        safety_margin = discount * 100
    except Exception as e:
        logger.error(f"{ticker} analyze error: {e}")
        return None
    
    description = fetch_stock_description(ticker)
    result = {
        'ticker': ticker,
        'current_price': round(current_price, 2),
        'intrinsic_value': round(intrinsic_value, 2),
        'safety_margin': round(safety_margin, 2),
        'moat': info.get('profitMargins', 0) > 0.1,
        'consistency': df['Close'].pct_change().std() < 0.03,
        'track_record': len(df) > 252 * 3,
        'description': description
    }
    conditions_met = sum([result['moat'], result['consistency'], result['track_record']])
    result['buy_recommendation'] = (discount > 0.3) and (conditions_met >= 2)
    logger.info(f"{ticker} analyze done | recommand = {result['buy_recommendation']}")
    return result

def daily_screening(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    logger.info("일일 스크리닝 시작")
    message = f"📅 {time.strftime('%Y-%m-%d 09:00')} 스크리닝 결과\n"
    message += "\n📈 나스닥 종목 분석 중...\n"
    nasdaq_results = [analyze_stock(ticker) for ticker in NASDAQ_TICKERS[:10] if analyze_stock(ticker)]
    nasdaq_df = pd.DataFrame(nasdaq_results)
    nasdaq_candidates = nasdaq_df[nasdaq_df['buy_recommendation'] == True]
    if not nasdaq_candidates.empty:
        message += "=== 나스닥 매수 추천 ===\n"
        for _, row in nasdaq_candidates.iterrows():
            message += f"{row['ticker']}: ${row['current_price']} (내재가치: ${row['intrinsic_value']}, 안전마진: {row['safety_margin']}%)\n"
    else:
        message += "추천 종목 없음\n"
    message += "\n📈 S&P 500 종목 분석 중...\n"
    sp500_results = [analyze_stock(ticker) for ticker in SP500_TICKERS[:10] if analyze_stock(ticker)]
    sp500_df = pd.DataFrame(sp500_results)
    sp500_candidates = sp500_df[sp500_df['buy_recommendation'] == True]
    if not sp500_candidates.empty:
        message += "=== S&P 500 매수 추천 ===\n"
        for _, row in sp500_candidates.iterrows():
            message += f"{row['ticker']}: ${row['current_price']} (내재가치: ${row['intrinsic_value']}, 안전마진: {row['safety_margin']}%)\n"
    else:
        message += "추천 종목 없음\n"
    context.bot.send_message(chat_id=chat_id, text=message)
    logger.info("일일 스크리닝 완료")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    welcome_message = (
        "매일 아침 9시에 나스닥과 S&P 500 종목을 스크리닝하여 단도원칙에 맞는 종목을 드립니다.\n"
        "또는 종목 티커(예: AAPL)를 입력하면 분석 결과를 드립니다.\n"
    )
    await update.message.reply_text(welcome_message)
    context.job_queue.run_daily(daily_screening, time=time(hour=0, minute=0), chat_id=chat_id)
    logger.info(f"사용자 {chat_id} 시작 명령 실행")

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
            f"매수 추천: {'✅ 예' if analysis['buy_recommendation'] else '❌ 아니오'}"
        )
    else:
        message = f"❌ {ticker} 데이터를 가져올 수 없습니다."
    await update.message.reply_text(message)
    logger.info(f"{ticker} 분석 결과 전송 완료")

def main():
    logger.info("Starting Dhandho Bot...")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == "__main__":
    main()