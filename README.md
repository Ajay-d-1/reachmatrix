# ReachMatrix — Automated B2B Outreach Pipeline

One domain in. Personalised emails out. Zero manual steps.

## Live Demo
https://reachmatrix-2.onrender.com

## How It Works

INPUT → company.domain (single string, only human input)

STAGE 1 — DISCOVER (Prospeo)
Finds companies in the same market as the seed domain
by analysing job histories of its C-suite employees.
Output: list of similar company domains

STAGE 2 — PROSPECT (Prospeo)  
For each company domain, finds C-suite and VP-level
decision makers using search-person API, then enriches
each person via enrich-person API to get verified emails.
Output: contacts with name, title, company, email

STAGE 3 — VERIFY (Internal)
Filters contacts to only those with valid verified emails.
Drops anyone without a confirmed work email address.
Output: clean verified contact list

STAGE 4 — OUTREACH (Brevo)
Sends personalised transactional email to each contact.
Every email uses the contact's name and company.
Output: sent/failed summary

## Architecture

outreach_pipeline/
├── main.py              # Orchestrator — runs all 4 stages
├── config.py            # All constants and API keys
├── stage1_discover.py   # Prospeo-based company discovery
├── stage2_prospeo.py    # Decision-maker search and enrich
├── stage3_eazyreach.py  # Email verification filter
├── stage4_brevo.py      # Brevo transactional email sender
├── utils.py             # Dedup, CXO filter, safety checkpoint
├── app.py               # Flask API server
└── templates/
    └── index.html       # ReachMatrix web dashboard

## Tech Stack
- Python + Flask (backend API)
- Prospeo API (company discovery + contact enrichment)
- Brevo API (transactional email)
- Gunicorn (production server)
- Render (deployment)
- Vercel (frontend hosting)

## Why These Decisions

Ocean.io free tier does not support the lookalike API.
SubSpace FAQ acknowledged this and approved alternatives.
Prospeo job history data provides equivalent discovery.

Eazyreach credits were unavailable at scale.
Prospeo enrich-person API returns verified emails directly
making a separate resolution step unnecessary.

Gunicorn timeout set to 300s because pipeline makes
multiple sequential API calls taking 60-90 seconds total.

## Setup

pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env

## Run Locally

python app.py
# Visit http://localhost:5000

## Environment Variables

PROSPEO_API_KEY=
BREVO_API_KEY=
SENDER_EMAIL=
SENDER_NAME=
