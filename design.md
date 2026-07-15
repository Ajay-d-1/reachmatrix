 ReachMatrix — Technical Design

## 1. Provider Interfaces

```python
class CompetitorDiscoveryProvider(ABC):
    def find_competitors(
        self, domain: str, company_name: str, industry: str
    ) -> list[CompetitorResult]:
        ...

class CompetitorResult(TypedDict):
    name: str
    domain: str
    source: Literal["llm_verified", "llm_unverified"]
    confidence: Literal["high", "medium", "low"]


class PeopleSearchProvider(ABC):
    def search_people(
        self, domain: str, seniority: list[str]
    ) -> list[PersonResult]:
        ...

class PersonResult(TypedDict):
    name: str
    title: str
    company: str
    domain: str
    linkedin_url: str
    email: str
    email_verified: bool
    provider: Literal["prospeo", "hunter"]
```

## 2. LLM Prompt Contract (Stage 1) — Mistral API

Endpoint: `https://api.mistral.ai/v1/chat/completions`, JSON mode enabled.

**System prompt:**
> You are a B2B market research assistant. Given a company, return its most
> direct, real-world competitors — companies that compete for the same
> customers with the same core product or service. Only return companies you
> are confident actually exist. Respond with strict JSON only, no prose.

**User prompt template:**
Company: {company_name}
Domain: {domain}
Industry: {industry}
Return the top 5 direct competitors as JSON:
[{"name": "...", "domain": "..."}]

- Use `temperature=0` for determinism/repeatability.
- Parse and validate the JSON strictly; if parsing fails, retry once, then
  fall to an explicit error/low-confidence state (never fabricate).

## 3. Domain Verification Logic
For each LLM-suggested domain:
1. HTTP HEAD request — confirm it resolves with a 2xx/3xx.
2. (Optional, budget-permitting) Cross-check via the existing Apollo
   `organizations/enrich` key — compare the returned company name against
   the LLM's suggested name for a fuzzy-match confidence score.
3. Tag the result `confidence: high` if both checks pass, `medium` if only
   the HEAD check passes, `low` (and flagged in the API response) otherwise.

## 4. API Contracts

### `POST /api/run-pipeline`
**Request:**
```json
{ "domain": "swiggy.com" }
```
**Response (success):**
```json
{
  "status": "success",
  "companies": [
    {"name": "Zomato", "domain": "zomato.com", "source": "llm_verified", "confidence": "high"}
  ],
  "contacts": [
    {"name": "...", "title": "...", "company": "Zomato", "email": "...", "email_verified": true, "provider": "prospeo"}
  ],
  "metrics": {"companies": 5, "prospects": 12, "verified": 9}
}
```
**Response (low confidence / partial failure):**
```json
{
  "status": "partial",
  "warning": "Competitor discovery had low confidence for this domain",
  "companies": [...],
  "contacts": [...]
}
```

## 5. Error / Confidence States (UI-facing)
- `source`: `llm_verified` | `llm_unverified`
- `confidence`: `high` | `medium` | `low`
- `provider`: which vendor actually answered (`prospeo` vs `hunter`) —
  surfaced for transparency, not hidden.
- Note: Mistral's free tier is low-RPM. If Stage 1 ever needs to run several
  seed domains back-to-back (e.g. batch testing before the interview), add a
  small delay between requests or expect occasional 429s — handle with
  retry-with-backoff, not a silent fallback.

## 6. Frontend Notes (`templates/index.html`)
- Show a small source/confidence badge per company row and per contact row.
  This turns "why did it pick these companies" from a weakness into a
  feature you can explain live: the founder sees exactly where each result
  came from and how confident the system is.
- If `status: "partial"`, show the warning banner instead of hiding it.