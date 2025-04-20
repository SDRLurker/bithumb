import os
from dotenv import load_dotenv
import python_bithumb
import pandas as pd
import json
from openai import OpenAI
import time
import ta
from ta.utils import dropna

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
        - Bollinger Bands (bb_bbm, bb_bbh, bb_bbl)
        - RSI (rsi)
        - MACD (macd, macd_signal, macd_diff)
        - Moving Averages (sma_20, ema_12)
        
        Response in json format.

        Response Example:
        {"decision": "buy", "reason": "some technical reason"}
        {"decision": "sell", "reason": "some technical reason"}
        {"decision": "hold", "reason": "some technical reason"}"""
        },
        {
        "role": "user",
        "content": f"Current investment status: {json.dumps(filtered_balances)}\nOrderbook: {json.dumps(orderbook)}\nDaily OHLCV with indicators (30 days): {df_daily.to_json()}\nHourly OHLCV with indicators (24 hours): {df_hourly.to_json()}"
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
    import time
    time.sleep(10)
    ai_trading()
