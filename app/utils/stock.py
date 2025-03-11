import yfinance as yf
import pandas as pd
import requests
from app.config.config import OPEN_ROUTER_API_KEY, OPEN_ROUTER_API_URL
from app.utils.logging import setup_logging
from app.utils.pe_mappings import industry_map, sector_fallback, pe_map

logger = setup_logging()

NASDAQ_TICKERS = []
SP500_TICKERS = []

def fetch_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        sp500_df = tables[0]
        logger.info("Success get S&P 500")
        return sp500_df["Symbol"].tolist()
    except Exception as e:
        logger.error(f"Failed S&P 500 | error: {e}")
        return []

def fetch_nasdaq_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        nasdaq_df = tables[3]
        logger.info("Success get Nasdaq 100")
        return nasdaq_df["Ticker"].tolist()  # 'Symbol' 대신 'Ticker'로 수정 (문서 기준)
    except Exception as e:
        logger.error(f"Failed Nasdaq 100 | error: {e}")
        return []

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
        logger.error(f"Failed get {ticker} data | error: {e}")
        return None

def fetch_stock_description(ticker):
    if not OPEN_ROUTER_API_KEY:
        logger.warning("OPEN_ROUTER_API_KEY is not found.")
        return ""

    headers = {
        "Authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "user", "content": f"{ticker} 주식에 대한 간단한 설명을 1문장으로 말해줘"}
        ],
    }

    try:
        response = requests.post(OPEN_ROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        description = result["choices"][0]["message"]["content"].strip()
        logger.info(f"Success get {ticker} description: {description}")
        return description
    except Exception as e:
        logger.error(f"Failed OpenRouter API ({ticker}) | error: {e}")
        return f"Failed get {ticker} data"

def get_industry_pe(ticker, info):
    industry = info.get("industry", "Unknown")
    sector = info.get("sector", "Unknown")
    
    nyu_industry = industry_map.get(industry)
    if nyu_industry and nyu_industry in pe_map and not pd.isna(pe_map[nyu_industry]):
        pe = pe_map[nyu_industry]
    else:
        nyu_industry = sector_fallback.get(sector, "Total Market")
        pe = pe_map.get(nyu_industry, 15)
    
    logger.info(f"{ticker} industry P/E: {pe} (Yahoo Industry: {industry}, Mapped NYU Industry: {nyu_industry})")
    return pe

def analyze_stock(ticker, safety_margin_threshold=0.3, min_conditions=2):
    df = fetch_stock_data(ticker)
    if df is None:
        return None
    
    current_price = df["Close"][-1]
    info = yf.Ticker(ticker).info
    
    eps = info.get("trailingEps")
    if eps is None or eps <= 0:
        logger.warning(f"{ticker} EPS unavailable or invalid")
        return None
    logger.info(f"{ticker} EPS: {eps}")
    
    intrinsic_value = eps * get_industry_pe(ticker, info)
    discount = (
        (intrinsic_value - current_price) / intrinsic_value
        if intrinsic_value > 0
        else 0
    )
    safety_margin = discount * 100
    
    # 나머지 로직 동일
    moat = (info.get("profitMargins", 0) > 0.1) and (info.get("returnOnEquity", 0) > 0.15)
    consistency = df["Close"].pct_change().std() < 0.03
    cagr = ((df["Close"][-1] / df["Close"][0]) ** (1 / (len(df) / 252)) - 1) if len(df) > 0 else 0
    track_record = (len(df) > 252 * 3) and (cagr > 0.05)
    
    description = fetch_stock_description(ticker)
    result = {
        "ticker": ticker,
        "current_price": round(current_price, 2),
        "intrinsic_value": round(intrinsic_value, 2),
        "safety_margin": round(safety_margin, 2),
        "moat": moat,
        "consistency": consistency,
        "track_record": track_record,
        "cagr": round(cagr * 100, 2),
        "description": description,
    }
    weights = {"moat": 0.4, "consistency": 0.3, "track_record": 0.3}
    score = sum([weights[k] * result[k] for k in weights])
    result["score"] = round(score, 2)
    result["buy_recommendation"] = (discount > safety_margin_threshold) and (score >= 0.6)
    
    logger.info(f"{ticker} analyze done | score = {result['score']} | recommend = {result['buy_recommendation']}")
    return result