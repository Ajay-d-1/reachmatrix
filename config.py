import os
from dotenv import load_dotenv

load_dotenv()

# API Keys — loaded from .env, NEVER hardcoded
OCEAN_API_KEY = os.getenv("OCEAN_API_KEY")
PROSPEO_API_KEY = os.getenv("PROSPEO_API_KEY")
EAZYREACH_API_KEY = os.getenv("EAZYREACH_API_KEY")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

# Sender identity for Brevo
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_NAME = os.getenv("SENDER_NAME")

# Pipeline limits — tuned for free tier constraints
OCEAN_MAX_RESULTS = 10       # protect trial credits
PROSPEO_MAX_PER_DOMAIN = 2   # 10 companies x 2 = 20, well under 75 limit
PROSPEO_CREDIT_WARNING = 30  # warn if credits drop below this
BREVO_DAILY_LIMIT = 300      # free tier hard cap

# Set True during testing, False for live demo
MOCK_MODE = False
