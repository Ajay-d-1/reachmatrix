# Automated Cold Outreach Pipeline

One domain in. Emails out. Zero human steps in between.

## Setup
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env

## Run
python main.py

## Pipeline
1. Ocean.io    — seed domain → lookalike company domains
2. Prospeo     — domains → C-suite/VP contacts + LinkedIn URLs  
3. Eazyreach   — LinkedIn URLs → verified work emails
4. Brevo       — verified emails → personalized outreach sent

## Config
- MOCK_MODE = True  → uses test data (safe for development)
- MOCK_MODE = False → live API calls (use for demo)

## Safety
Always shows a summary and asks for YES confirmation
before any emails are sent.
