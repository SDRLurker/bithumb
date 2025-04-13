import os
from dotenv import load_dotenv
load_dotenv()

# 1. 빗썸 차트 데이터 가져오기 (30일 일봉)
import python_bithumb
df = python_bithumb.get_ohlcv("KRW-BTC", interval="day", count=30)
print(df)
