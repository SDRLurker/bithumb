import os
from dotenv import load_dotenv
load_dotenv()

print(os.getenv("BITHUMB_ACCESS_KEY"))
print(os.getenv("BITHUMB_SECRET_KEY"))
print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("GEMINI_API_KEY"))
