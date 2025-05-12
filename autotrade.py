import os
from dotenv import load_dotenv
import python_bithumb
import pandas as pd
import json
from openai import OpenAI
import time
import ta
from ta.utils import dropna
import time
import requests

load_dotenv()

def add_indicators(df):
    # 볼린저 밴드
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_bbm'] = indicator_bb.bollinger_mavg()
    df['bb_bbh'] = indicator_bb.bollinger_hband()
    df['bb_bbl'] = indicator_bb.bollinger_lband()

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close=df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    # 이동평균선
    df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()

    return df

def get_fear_and_greed_index():
     url = "https://api.alternative.me/fng/"
     response = requests.get(url)
     if response.status_code == 200:
         data = response.json()
         return data['data'][0]
     else:
         print(f"Failed to fetch Fear and Greed Index. Status code: {response.status_code}")
         return None

def get_bitcoin_news():
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_news",
        "q": "btc",
        "api_key": serpapi_key
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
        data = response.json()
        news_results = data.get("news_results", [])
        headlines = []
        for item in news_results:
            headlines.append({
                "title": item.get("title", ""),
                "date": item.get("date", "")
            })
        return headlines[:5]  # 최신 5개의 뉴스 헤드라인만 반환
    except requests.RequestException as e:
        print(f"Error fetching news: {e}")
        return []

def ai_trading():
    # Bithumb 객체 생성
    access = os.getenv("BITHUMB_ACCESS_KEY")
    secret = os.getenv("BITHUMB_SECRET_KEY")
    bithumb = python_bithumb.Bithumb(access, secret)

    # 1. 현재 투자 상태 조회
    all_balances = bithumb.get_balances()
    filtered_balances = [balance for balance in all_balances if balance['currency'] in ['BTC', 'KRW']]
    
    # 2. 오더북(호가 데이터) 조회
    orderbook = python_bithumb.get_orderbook("KRW-BTC")
    
    # 3. 차트 데이터 조회 및 보조지표 추가
    # 30일 일봉 데이터
    df_daily = python_bithumb.get_ohlcv("KRW-BTC", interval="day", count=30)
    df_daily = dropna(df_daily)
    df_daily = add_indicators(df_daily)
    
    # 24시간 시간봉 데이터
    df_hourly = python_bithumb.get_ohlcv("KRW-BTC", interval="minute60", count=24)
    df_hourly = dropna(df_hourly)
    df_hourly = add_indicators(df_hourly)

    # 4. 공포 탐욕 지수 가져오기
    fear_greed_index = get_fear_and_greed_index()

    # 5. 뉴스 헤드라인 가져오기
    news_headlines = get_bitcoin_news()

    # AI에게 데이터 제공하고 판단 받기
    API_KEY = os.getenv("GEMINI_API_KEY")
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
    model="gemini-1.5-flash",
    messages=[
        {
        "role": "system",
        "content": """You are an expert in Bitcoin investing. Analyze the provided data including technical indicators and tell me whether to buy, sell, or hold at the moment. Consider the following indicators in your analysis:
        - Technical indicators and market data
        - Recent news headlines and their potential impact on Bitcoin price
        - The Fear and Greed Index and its implications
        - Overall market sentiment
        
        Response in json format.

        Response Example:
        {"decision": "buy", "reason": "some technical, fundamental, and sentiment-based reason"}
        {"decision": "sell", "reason": "some technical, fundamental, and sentiment-based reason"}
        {"decision": "hold", "reason": "some technical, fundamental, and sentiment-based reason"}"""
        },
        {
        "role": "user",
        "content": f"""Current investment status: {json.dumps(filtered_balances)}
Orderbook: {json.dumps(orderbook)}
Daily OHLCV with indicators (30 days): {df_daily.to_json()}
Hourly OHLCV with indicators (24 hours): {df_hourly.to_json()}
Recent news headlines: {json.dumps(news_headlines)}
Fear and Greed Index: {json.dumps(fear_greed_index)}"""
        }
    ],
    response_format={
        "type": "json_object"
    }
    )
    result = response.choices[0].message.content

    # AI의 판단에 따라 실제로 자동매매 진행하기
    result = json.loads(result)

    my_krw = bithumb.get_balance("KRW")
    my_btc = bithumb.get_balance("BTC")

    print("### AI Decision: ", result["decision"].upper(), "###")
    print(f"### Reason: {result['reason']} ###")

    if result["decision"] == "buy":
        if my_krw > 5000:
            print("### Buy Order Executed ###")
            bithumb.buy_market_order("KRW-BTC", my_krw*0.997)
        else:
            print("### Buy Order Failed: Insufficient KRW (less than 5000 KRW) ###")
    elif result["decision"] == "sell":
        current_price = python_bithumb.get_current_price(ticker="KRW-BTC")
        if my_btc * current_price > 5000:
            print("### Sell Order Executed ###")
            bithumb.sell_market_order("KRW-BTC", my_btc*0.997)
        else:
            print("### Sell Order Failed: Insufficient BTC (less than 5000 KRW worth) ###")
    elif result["decision"] == "hold":
        print("### Hold Position ###")

while True:
    try:
        ai_trading()
        time.sleep(600) # 10분 간격으로 실행(너무 빈번한 API 호출 방지)
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(60) # 오류 발생 시 1분 후 재시도
