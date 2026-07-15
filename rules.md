markdown# ReachMatrix — Build Rules

Guardrails to hand to your AI coding agent (Antigravity) before it starts
implementing. These exist specifically to prevent v1's failure mode from
happening again.

## Non-Negotiables
1. **Never return hardcoded/static data as if it were a live result.** If a
   provider fails or has low confidence, return an explicit
   `"source": "error"` or `"confidence": "low"` state in the response — never
   silently substitute fixed data.
2. **Every external API call must have:** a timeout, explicit status-code
   handling, and a logged reason on failure. No bare `except: return []` that
   hides *why* something failed.
3. **API keys only ever load from environment variables** via `config.py` —
   never hardcoded, never logged, never committed.
4. **Every stage function must be provider-agnostic.** Call through the
   interface defined in architecture.md, not a vendor-specific method name
   directly in orchestration code.
5. **No single failure should kill the whole pipeline.** If one competitor's
   people-search fails, skip that competitor and continue — don't abort the
   entire run.
6. **Keep the manual approval checkpoint before Stage 4.** Never allow
   auto-send under any flag or shortcut.
7. **PII handling stays disciplined.** No bulk unsupervised sending, no
   emails logged in plaintext to third-party logging services.

## Code Style
- Type-hint all provider interfaces and their return objects.
- Structured logging (JSON-ish, one line per event) instead of bare `print` —
  you want to be able to show real request traces in the interview.
- One provider = one file, under a `providers/` folder.
- At minimum, write tests for the domain-verification logic — that's the
  piece most likely to have silent edge-case bugs (e.g. valid domain, wrong
  company).

## Git Discipline
- Small, single-purpose commits — your existing commit history
  (`fix: update Apollo auth headers`, etc.) is actually good practice, keep
  doing it.
- Confirm `.env` is in `.gitignore` and no real keys ever get committed.

## Definition of Done — Per Stage
A stage is not "done" until it:
- Works correctly against at least 2 well-known test domains **and** 1
  obscure/small company domain (edge case).
- Fails loudly and visibly when a provider is down — never falls back to
  fake data without saying so in the response.
- Has a logged trace you could screenshot or read aloud in an interview to
  explain exactly what happened for a given request.