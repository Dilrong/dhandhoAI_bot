import yfinance as yf
import pandas as pd
import requests
from functools import lru_cache
from typing import List, Optional, Dict, Any
from app.config.config import OPEN_ROUTER_API_KEY, OPEN_ROUTER_API_URL
from app.utils.logging import setup_logging
from app.utils.pe_mapping import INDUSTRY_PE, SECTOR_FALLBACK

logger = setup_logging()

NASDAQ_TICKERS: List[str] = []
SP500_TICKERS: List[str] = []

def fetch_sp500_tickers() -> List[str]:
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url, attrs={"id": "constituents"})
        sp500_df = tables[0]
        tickers = sp500_df["Symbol"].str.replace(".", "-").tolist()
        logger.info(f"Successfully fetched {len(tickers)} S&P 500 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 tickers | error: {e}")
        return []

def fetch_nasdaq_tickers() -> List[str]:
    try:
        url = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        tickers = [item["symbol"] for item in data["data"]["data"]["rows"]]
        logger.info(f"Successfully fetched {len(tickers)} Nasdaq-100 tickers from Nasdaq API")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch Nasdaq-100 tickers from Nasdaq API | error: {e}")
        return []

NASDAQ_TICKERS = fetch_nasdaq_tickers()
SP500_TICKERS = fetch_sp500_tickers()

@lru_cache(maxsize=128)
def fetch_stock_data(ticker: str, period: str = "5y") -> Optional[pd.DataFrame]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, auto_adjust=True)
        if df.empty:
            logger.warning(f"{ticker} historical data is empty")
            return None
        logger.info(f"Successfully fetched {ticker} data | rows: {len(df)}")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch {ticker} data | error: {e}")
        return None

@lru_cache(maxsize=128)
def fetch_stock_info(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        logger.info(f"Successfully fetched {ticker} info")
        return info
    except Exception as e:
        logger.error(f"Failed to fetch {ticker} info | error: {e}")
        return {}

def fetch_stock_description(ticker: str) -> str:
    if not OPEN_ROUTER_API_KEY or not OPEN_ROUTER_API_URL:
        logger.warning("Open Router API credentials not configured")
        return "주식 요약을 가져올 수 없습니다."
    headers = {
        "Authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "user", "content": f"{ticker} 주식에 대한 간단한 설명을 1문장으로 한국어로 제공해 주세요."}
        ],
        "max_tokens": 50,
    }
    try:
        response = requests.post(OPEN_ROUTER_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        description = result["choices"][0]["message"]["content"].strip()
        logger.info(f"Successfully fetched {ticker} description: {description}")
        return description
    except requests.Timeout:
        logger.error(f"Open Router API timeout for {ticker}")
        return f"{ticker}에 대한 요약을 가져오는 데 시간이 초과되었습니다."
    except Exception as e:
        logger.error(f"Failed to fetch {ticker} description via Open Router | error: {e}")
        return f"{ticker}에 대한 요약을 가져올 수 없습니다."

def get_industry_pe(industry: str, sector: str, trailing_pe: Optional[float] = None) -> float:
    industry_pe = INDUSTRY_PE.get(industry)
    if industry_pe is None:
        mapped_industry = SECTOR_FALLBACK.get(sector, "Total Market")
        industry_pe = INDUSTRY_PE.get(mapped_industry, 20.0)  # 기본값을 20으로 현실화
        logger.debug(f"Industry '{industry}' not found, using fallback '{mapped_industry}' PE: {industry_pe}")
    
    # 현실적인 P/E로 조정: 상한선 30, 주식 trailingPE 반영
    if trailing_pe and trailing_pe > 0:
        realistic_pe = min(max(trailing_pe * 1.2, 15.0), 30.0)  # trailingPE의 1.2배, 15~30 범위
        if industry_pe > 30:
            logger.warning(f"Industry PE {industry_pe} too high, adjusted to {realistic_pe} based on trailing PE {trailing_pe}")
            return realistic_pe
    return min(industry_pe, 30.0)  # 상한선 30 적용

@lru_cache(maxsize=128)
def analyze_stock(ticker: str, safety_margin_threshold: float = 0.3, include_description: bool = True) -> Optional[Dict[str, Any]]:
    df = fetch_stock_data(ticker)
    if df is None:
        return None
    
    info = fetch_stock_info(ticker)
    if not info:
        return None
    
    current_price = df["Close"].iloc[-1]
    eps = info.get("trailingEps")
    if eps is None or eps <= 0:
        logger.warning(f"{ticker} EPS unavailable or invalid: {eps}")
        return None
    
    industry = info.get("industry", "Default")
    sector = info.get("sector", "Default")
    trailing_pe = info.get("trailingPE", current_price / eps if eps > 0 else None)
    industry_pe = get_industry_pe(industry, sector, trailing_pe)
    intrinsic_value = eps * industry_pe
    discount = ((intrinsic_value - current_price) / intrinsic_value) if intrinsic_value > 0 else 0
    safety_margin = discount * 100

    if intrinsic_value > current_price * 5:  # 내재가치가 주가의 5배 이상이면 경고
        logger.warning(f"{ticker} intrinsic value {intrinsic_value} seems high (current price: {current_price})")

    pe_discount = ((industry_pe - trailing_pe) / industry_pe * 100) if trailing_pe and industry_pe else 0
    
    moat = (info.get("profitMargins", 0) > 0.1) and (info.get("returnOnEquity", 0) > 0.15)
    consistency = df["Close"].pct_change().std() < 0.03
    cagr = ((df["Close"].iloc[-1] / df["Close"].iloc[0]) ** (1 / (len(df) / 252)) - 1) if len(df) > 0 else 0
    track_record = (len(df) > 252 * 3) and (cagr > 0.05)
    
    result = {
        "ticker": ticker,
        "current_price": round(current_price, 2),
        "trailing_pe": round(trailing_pe, 2) if trailing_pe else None,
        "industry_pe": round(industry_pe, 2),
        "intrinsic_value": round(intrinsic_value, 2),
        "safety_margin": round(safety_margin, 2),
        "pe_discount": round(pe_discount, 2),
        "moat": moat,
        "consistency": consistency,
        "track_record": track_record,
        "cagr": round(cagr * 100, 2),
        "is_nasdaq100": ticker in NASDAQ_TICKERS,
        "is_sp500": ticker in SP500_TICKERS,
    }
    
    if include_description:
        result["description"] = fetch_stock_description(ticker)
    
    weights = {"moat": 0.4, "consistency": 0.3, "track_record": 0.3}
    score = sum(weights[k] * result[k] for k in weights)
    result["score"] = round(score, 2)
    result["buy_recommendation"] = (discount > safety_margin_threshold) and (score >= 0.6)
    
    logger.info(f"{ticker} | EPS: {eps}, Current Price: {current_price}, "
                f"Intrinsic Value: {intrinsic_value}, Safety Margin: {safety_margin}%")
    logger.info(f"{ticker} analyze done | score = {result['score']} | recommend = {result['buy_recommendation']}")
    
    return result