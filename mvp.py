import os
from dotenv import load_dotenv
load_dotenv()
import python_bithumb
import json
from openai import OpenAI
import time
import re

def ai_trading():
    # 1. 빗썸 차트 데이터 가져오기 (30일 일봉)
    df = python_bithumb.get_ohlcv("KRW-BTC", interval="day", count=30)

    # 2. AI에게 데이터 제공하고 판단 받기
    API_KEY = os.getenv("GEMINI_API_KEY")
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
        model="gemini-1.5-flash",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert in Bitcoin investing. "
                    "Tell me whether to buy, sell, or hold at the moment based on the chart data provided. "
                    "Response in json format.\n\n"
                    "Response Example:\n"
                    "{\"decision\": \"buy\", \"reason\": \"some technical reason\"}\n"
                    "{\"decision\": \"sell\", \"reason\": \"some technical reason\"}\n"
                    "{\"decision\": \"hold\", \"reason\": \"some technical reason\"}"
                )
            },
            {
            "role": "user",
            "content": df.to_json()
            }
        ]
    )

    # JSON 데이터만 추출
    raw_result = response.choices[0].message.content
    json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
    if json_match:
        result = json.loads(json_match.group())
    else:
        raise ValueError("JSON response could not be extracted.")

    # 3. AI의 판단에 따라 실제로 자동매매 진행하기
    access = os.getenv("BITHUMB_ACCESS_KEY")
    secret = os.getenv("BITHUMB_SECRET_KEY")
    bithumb = python_bithumb.Bithumb(access, secret)

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
        current_price = python_bithumb.get_current_price("KRW-BTC")
        if my_btc * current_price > 5000:
            print("### Sell Order Executed ###")
            bithumb.sell_market_order("KRW-BTC", my_btc*0.997)
        else:
            print("### Sell Order Failed: Insufficient KRW (less than 5000 KRW) ###")
    elif result["decision"] == "hold":
        print("### Hold Position ###")

while True:
    ai_trading()
    time.sleep(10)
