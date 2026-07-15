how about grok ,gemini or mistral as its free and are u asking me to replace prospeo with appolo api key and let the remaining keys be the same


Weighed free API trade-offs, endorsed Mistral, flagged Apollo key limitations
Weighed free API trade-offs, endorsed Mistral, flagged Apollo key limitations
Good questions — quick real-world check on each, since "free" claims shift fast:

Gemini — genuinely the most generous free tier of the three (Flash models, ~15 requests/min, ~1,500/day as of now). The catch: Google's free tier terms explicitly exclude commercial use and say they may use your prompts/outputs to improve their models. Since this is going into something you're pitching to a founder as a product for his company, that's not just a technicality — it's the kind of thing that could bite you specifically in this scenario.

Grok — heads up, the free tier is only on grok.com / the X app (~10 prompts every 2 hours), not the API. The actual xAI API is pay-per-token like everyone else; new accounts get some sign-up credit, not an ongoing free tier.

Mistral — this is honestly your best free option. Their "Experiment" tier on La Plateforme is a real no-card-required free tier (rate-limited, but generous enough for one structured JSON call per pipeline run), and it doesn't carry the same "no commercial use" language Gemini's free tier does. Worth double-checking their current terms on your own console before you commit, since these things move monthly, but it's the cleanest of the three for what you're building.

That said — worth knowing: your Stage 1 call is one small structured JSON request per pipeline run (~5 competitors). Even on Claude or GPT's paid tier this costs a fraction of a cent per run. So "free vs. paid" barely matters on cost here — it matters on reliability and commercial-use terms. If it were me pitching this to a founder, I'd still lean toward a proper paid key (even a cheap one) specifically so I could say "no data-training clause, no rate-limit surprise mid-demo." But Mistral's free tier is a legitimate way to prototype Phase 1 this week before deciding.

On Prospeo vs. Apollo — my suggestion in architecture.md was Apollo as primary, Prospeo kept as an automatic fallback, not a full swap. One flag on that: check your Apollo plan — their People Search API with email export/verified-email access is usually gated to a paid plan, their free tier is quite limited for exports specifically (separate from the free "organizations/enrich" endpoint you're already using in Stage 1, which is a different, more open endpoint). If you don't want to maintain two integrations under time pressure, fully replacing Prospeo with Apollo is simpler and totally fine — the fallback pattern is a nice-to-have for the interview story, not a requirement.

Everything else — Brevo, sender identity — stays exactly as-is.

yeah apollo main function is for enterprises its free plan is of not any use what shall we do


Evaluated Apollo's limitations and advocated retaining Prospeo instead
Evaluated Apollo's limitations and advocated retaining Prospeo instead
Good catch — and the pricing confirms it. Apollo in 2026 is priced per-seat ($49–119/user/month) as a bundled sales platform (CRM, dialer, sequencers, the works), and its free tier gives you ~100 email credits and almost no mobile/export credits — genuinely not built for "call an API once per pipeline run." There's also a fine-print detail worth knowing: Apollo's terms say their data is for internal business use only — using it to power an external product/offering you resell isn't permitted. Since this could become an actual product for the founder's company, that's a real constraint, not just a pricing annoyance.

My revised recommendation: don't switch to Apollo at all. Keep Prospeo.

You already have working Prospeo integration code, and it's the right shape for this problem — it's a pay-per-credit email finder/verifier (~$0.01/verified email in some comparisons), not a per-seat SaaS suite. You're paying for exactly the thing you need (verified emails), not a dialer and sequencer you'll never touch.

If you want redundancy (a second provider to fail over to, which is a nice thing to say in an interview), the better-fit options are other credit-based finder/verifier tools rather than Apollo:

Hunter.io — email finder + verifier, has a real free tier (25 searches/month) and affordable paid plans, no per-seat pricing
RocketReach — similar people-search-by-domain model, credit-based
Either works as a Prospeo fallback without the licensing and cost mismatch Apollo brings.

So the updated plan: Stage 1 gets rebuilt with an LLM (Mistral free tier to start), Stage 2 stays on Prospeo as primary — which means that part of your codebase barely needs to change, it just needs Stage 1 to stop feeding it garbage domains. Want me to update 2_architecture.md and 4_phases.md to reflect Prospeo-stays instead of Apollo-swap, so the docs you hand to Antigravity are accurate?

yeah update it and i also got hunter.io api key and mistral api key now update it


Copy output files to writable workspace for editing
Copy output files to writable workspace for editing
Now let me update each doc with the confirmed providers: Mistral (LLM), Prospeo (primary people-search), Hunter.io (fallback).


Reconciled API utility and prepared tech stack updates
Reconciled API utility and prepared tech stack updates
Now update phases.md:


Update setup phase and stage phases with confirmed providers
Update setup phase and stage phases with confirmed providers
Now update design.md's prompt contract and provider field references:


Edited 2 files
Edited 2 files
Now let me overwrite the files in outputs with the updated versions and re-present them.


Ran a command, read a file
Ran a command, read a file
Updated. Locked in now: Mistral for Stage 1 competitor discovery, Prospeo stays primary for Stage 2 (unchanged, since it already works), Hunter.io as the fallback when Prospeo comes up empty for a domain. Apollo's existing key gets a smaller, cheaper role — only for the domain-verification cross-check in Stage 1, not discovery or people search.

PRD.md and rules.md don't need changes — they're provider-agnostic by design.

Ready to start Phase 1 whenever you are — want me to write the actual MistralCompetitorProvider implementation next?


2 architecture
Document · MD 

4 phases
Document · MD 

5 design
Document · MD 
i am finding it slightly difficult to add this is in the workspace so can u give it as text now along with all the changes plans from this files specified


Identified outdated references and standardized documentation for clarity
Identified outdated references and standardized documentation for clarity
Good catch on my end too — I spotted two leftover references to the old Apollo plan I should fix before handing this over. Here's everything, fully updated and consolidated as plain text so you can paste directly into your workspace.

1_PRD.md
markdown
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
2_architecture.md
markdown
# ReachMatrix — Architecture (v2)

## 1. System Overview
Seed Domain
|
v
Stage 1: Competitor Discovery
(Mistral LLM reasoning -> candidate competitors)
(Domain verification -> confirm real, live domains)
|
v
Stage 2: People Search
(Prospeo primary -> Hunter.io fallback)
(Filter: Founder / C-suite / VP / Director)
|
v
Stage 3: Email Verification & Filtering
(Keep only contacts with a verified work email)
|
v
Safety Checkpoint <-- human review, required
|
v
Stage 4: Outreach Dispatch (Brevo)


## 2. Why the Redesign

v1's Stage 1 tried to infer competitors from SerpAPI search-result snippets. This
is fundamentally the wrong tool: search results for "X competitors" are
SEO-gamed and noisy, so the pipeline routinely fell back to a static hardcoded
list — which is why the output looked the same regardless of input.

v2 replaces search-scraping with an **LLM reasoning step**. LLMs have broad,
reliable business-domain knowledge baked in from training — they know Zomato is
Swiggy's competitor and TCS/Wipro/Accenture are Infosys's without needing to
parse a single search result. A lightweight verification pass then confirms the
LLM's suggested domains are real, live companies (guards against hallucination).

**Confirmed providers (v2):**
- LLM: **Mistral API** (La Plateforme) — see design.md for the prompt contract
- People search: **Prospeo** (unchanged, primary) with **Hunter.io** as fallback
- Email dispatch: **Brevo** (unchanged)

Apollo was evaluated and dropped for people-search: it's priced per-seat as a
bundled sales-engagement suite ($49–119/user/month) rather than per-lookup, its
free tier is unusable for anything beyond casual browsing (~100 email credits,
almost no export/mobile credits), and its terms restrict data use to internal
business purposes — not ideal if this pipeline becomes a product you're
building for someone else's company. Prospeo is already integrated, priced
per-verified-email rather than per-seat, and is the right shape for "call an
API once per contact" rather than "run a full sales team through a CRM."
The existing Apollo key is kept, but only for a small verification role (see
Stage 1 below).

## 3. Component Breakdown

### Stage 1 — Competitor Discovery
- `CompetitorDiscoveryProvider` interface
  - `MistralCompetitorProvider` (primary): single structured call to the
    Mistral API — see design.md for the exact prompt contract.
  - `DomainVerifier`: confirms each candidate domain is live (HTTP HEAD) and,
    optionally, cross-checks the company name via the existing Apollo
    `organizations/enrich` free endpoint (already integrated in v1 — kept
    only for this lightweight verification purpose, not for lookalike
    discovery or people search) for a confidence score.
  - No hardcoded fallback list. If the LLM + verification genuinely can't
    produce confident results, the API returns an explicit low-confidence /
    error state — never fabricated data presented as real.

### Stage 2 — People Search
- `PeopleSearchProvider` interface
  - `ProspeoPeopleSearchProvider` (primary, unchanged) — company-domain
    filter + seniority filter (Founder/C-suite/VP/Director), search-person +
    enrich-person flow already built in v1.
  - `HunterPeopleSearchProvider` (fallback) — used automatically if Prospeo
    returns nothing for a given domain. Gives you real redundancy without
    Apollo's per-seat pricing or usage restrictions.
  - Runs concurrently across competitor domains (v1 ran this sequentially
    with a `time.sleep(0.5)` between calls — a real bottleneck).

### Stage 3 — Verification
- Unchanged logic: keep only contacts with a non-empty, verified email.
- Optional upgrade: run a second-opinion check (ZeroBounce/NeverBounce) if
  budget allows, for higher deliverability confidence.

### Stage 4 — Outreach
- Brevo integration stays as-is.
- The hardcoded "demo contact" (your own email, always prepended) gets moved
  behind an explicit `DEMO_MODE` flag — so it's never silently mixed into a
  real client's results, but you can still flip it on for your interview demo.

## 4. Tech Stack
- Backend: Python + Flask (unchanged)
- LLM: Mistral API (Stage 1 reasoning)
- People data: Prospeo (primary, unchanged) + Hunter.io (fallback)
- Domain verification: existing Apollo `organizations/enrich` key, repurposed
  for confidence-checking only (not lookalike discovery, not people search)
- Email: Brevo (unchanged)
- Deployment: Render + Gunicorn (unchanged), all config via env vars

## 5. Provider Abstraction — Why It Matters
Every external data source sits behind a small interface, configured via env
var, so swapping or adding a provider is a config change, not a rewrite. This
is also a strong interview point: *"if one provider's coverage is thin for a
niche market, we fail over automatically — the orchestration logic doesn't
care which vendor answered."*

## 6. What Stays Unchanged
- Overall 4-stage orchestration in `main.py` / `app.py`
- Dedup and CXO filtering logic (`utils.py`)
- The manual safety checkpoint before sending
- Flask API shape (`/api/run-pipeline`, `/api/send-emails`)

This is a targeted rebuild of Stage 1 and an upgrade of Stage 2 — not a
rewrite of the whole system.