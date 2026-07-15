# ReachMatrix — Product Requirements Document (PRD)

## 1. Problem Statement
ReachMatrix is meant to take a single company domain and automatically produce a
verified, ready-to-send outreach list of decision-makers at that company's real
competitors. The current implementation fails at the first step: competitor
discovery is done via generic web-search scraping (SerpAPI), which is unreliable
and falls back to a **hardcoded, input-independent list of companies** whenever
the search doesn't return enough results — which is most of the time. This means
searching "swiggy.com" and "infosys.com" can return the same irrelevant list.

## 2. Who This Is For
B2B sales/growth/founders who want to go from "one company domain" to "a
reviewed, verified list of decision-makers at similar companies" with no manual
research — a lightweight alternative to manually using Apollo/ZoomInfo/Clay.

## 3. Goals (v2)
- **G1 — Real competitor discovery.** `swiggy.com` → Zomato, Zepto, Blinkit-type
  results. `infosys.com` → TCS, Wipro, Accenture, HCL-type results. Input-specific,
  every time.
- **G2 — Real decision-makers.** Founder/CEO/CTO/COO/CFO/VP/Director-level
  contacts at each competitor, sourced from a real people-data provider.
- **G3 — Verified emails only.** No contact reaches the outreach stage without a
  verified work email.
- **G4 — Human review before send.** Keep the existing safety checkpoint — no
  auto-send, ever.
- **G5 — Transparency over fake confidence.** If discovery genuinely can't find
  good data for a niche/obscure company, the system says so explicitly. It never
  silently substitutes hardcoded data and presents it as a real result.

## 4. Non-Goals (v2)
- No CRM / long-term contact history (future consideration)
- No multi-channel outreach (LinkedIn, phone, SMS) — email only
- No email copy A/B testing
- No multi-tenant auth — single-operator demo tool for now

## 5. Core User Flow
1. User enters a seed domain.
2. System identifies real direct competitors (with a source/confidence indicator).
3. System finds senior decision-makers at each competitor.
4. System resolves and verifies a work email per person.
5. User reviews the full list (name, title, company, email, confidence).
6. User explicitly approves → system sends a personalized email via Brevo.
7. User sees a sent/failed summary.

## 6. Success Criteria
- Competitor list is visibly and correctly tied to the input domain across at
  least 5 varied test companies (well-known + one obscure/small company).
- ≥ 80% of surfaced contacts have a real, verified, deliverable email.
- Zero instances of hardcoded/static data being returned as if it were live.
- End-to-end run completes in well under Gunicorn's timeout (target: < 60s).
- Founder/interviewer can ask "why did it pick these competitors?" and get a
  defensible, explainable answer (not "it's the fallback list").

## 7. Constraints
- Final interview round in 3+ days — must be reliably working on the **live
  deployment**, not just localhost.
- Paid API budget now available: Mistral + Hunter.io confirmed.
- Must hold up under live technical questioning, not just look good in a demo.