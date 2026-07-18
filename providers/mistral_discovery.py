import re
import json
import time
import socket
import logging
import requests
from typing import Dict, List, Tuple
from config import MISTRAL_API_KEY, APOLLO_API_KEY, OCEAN_MAX_RESULTS
from .base import CompetitorDiscoveryProvider, CompetitorResult

logger = logging.getLogger(__name__)

# Noise domains to exclude even if suggested by LLM
NOISE_DOMAINS = {
    'linkedin.com', 'google.com', 'youtube.com', 'wikipedia.org',
    'reddit.com', 'crunchbase.com', 'glassdoor.com', 'g2.com',
    'capterra.com', 'twitter.com', 'facebook.com', 'instagram.com',
    'bloomberg.com', 'techcrunch.com', 'forbes.com', 'producthunt.com',
    'github.com', 'medium.com', 'substack.com', 'trustpilot.com',
    'getapp.com', 'softwareadvice.com', 'similarweb.com', 'builtwith.com',
    'apollo.io', 'zoominfo.com', 'clearbit.com', 'quora.com',
    'yahoo.com', 'ycombinator.com', 'apple.com', 'semrush.com',
    'trustradius.com', 'sharetribe.com', 'owler.com', 'apistemic.com'
}


class MistralDiscoveryProvider(CompetitorDiscoveryProvider):
    """
    Stage 1 Provider: Discovers competitors using Mistral AI JSON completions
    and verifies each domain via HTTP resolution + optional Apollo enrichment cross-check.
    """

    def __init__(self, api_key: str = None, apollo_key: str = None):
        self.api_key = api_key or MISTRAL_API_KEY
        self.apollo_key = apollo_key or APOLLO_API_KEY
        self.model = "mistral-small-latest"

    def find_competitors(
        self, domain: str, company_name: str = "", industry: str = ""
    ) -> Tuple[List[CompetitorResult], str]:
        logger.info(f"Stage 1 [Mistral]: Finding competitors for domain={domain}")

        # If seed company name/industry are not provided, enrich seed via Apollo
        enriched_ind = ""
        if not company_name or not industry:
            enriched_name, enriched_ind = self._enrich_seed(domain)
            company_name = company_name or enriched_name or domain.split('.')[0].title()
            # Only use Apollo's industry if it actually returned one.
            # NEVER substitute a hardcoded guess — let the LLM determine it.
            industry = industry or enriched_ind or ""
            logger.info(
                f"Stage 1 [Mistral]: Seed context — name='{company_name}', "
                f"industry='{industry or '(unknown — will be LLM-determined)'}'"
            )

        if not self.api_key:
            logger.error("Stage 1 [Mistral]: MISTRAL_API_KEY not configured. Cannot discover competitors.")
            self.resolved_seed_domain = self._extract_root_domain(domain) or domain
            return [], ""

        # Build the industry hint: only include a real hint if we got one from
        # Apollo or the caller.  Otherwise pass "unknown" so the LLM relies on
        # its own knowledge rather than trusting a fabricated label.
        industry_hint = industry if industry else "unknown"

        # Call Mistral LLM for structured JSON competitor discovery
        raw_candidates, identified_industry, seed_domain_from_llm = self._call_mistral_json(
            domain, company_name, industry_hint
        )
        logger.info(
            f"Stage 1 [Mistral]: Self-identified industry for {company_name}: {identified_industry}"
        )

        clean_input = self._extract_root_domain(domain)
        if clean_input and self._verify_domain_http(clean_input):
            self.resolved_seed_domain = clean_input
        elif seed_domain_from_llm:
            clean_seed = self._extract_root_domain(seed_domain_from_llm) or seed_domain_from_llm.strip().lower()
            if self._verify_domain_http(clean_seed):
                self.resolved_seed_domain = clean_seed
            else:
                self.resolved_seed_domain = clean_input or domain
        else:
            self.resolved_seed_domain = clean_input or domain

        if not raw_candidates:
            logger.warning("Stage 1 [Mistral]: No candidates returned from LLM. Never returning static fallback.")
            return [], identified_industry

        # Verify candidate domains
        verified_results: List[CompetitorResult] = []
        seen_domains = {domain.lower()}

        for candidate in raw_candidates:
            raw_name = candidate.get("name", "").strip()
            raw_domain = candidate.get("domain", "").strip()
            clean_domain = self._extract_root_domain(raw_domain)

            if not clean_domain or clean_domain in seen_domains or clean_domain in NOISE_DOMAINS:
                continue

            seen_domains.add(clean_domain)

            # Step 1: HTTP resolution check
            http_ok = self._verify_domain_http(clean_domain)

            # Step 2: Apollo cross-check (optional, for high confidence)
            apollo_match = False
            if http_ok and self.apollo_key:
                apollo_name, _ = self._enrich_seed(clean_domain)
                if apollo_name and self._names_match(raw_name, apollo_name):
                    apollo_match = True

            # Assign confidence and source tagged per design.md rules
            if http_ok and apollo_match:
                confidence = "high"
                source = "llm_verified"
            elif http_ok:
                confidence = "medium"
                source = "llm_verified"
            else:
                confidence = "low"
                source = "llm_unverified"

            result: CompetitorResult = {
                "name": raw_name or clean_domain.split('.')[0].title(),
                "domain": clean_domain,
                "source": source,
                "confidence": confidence
            }
            verified_results.append(result)
            logger.info(f"Stage 1 [Mistral]: Verified competitor '{result['name']}' ({clean_domain}) -> confidence={confidence}, source={source}")

            if len(verified_results) >= OCEAN_MAX_RESULTS:
                break

        logger.info(f"Stage 1 [Mistral]: Completed discovery, returning {len(verified_results)} verified competitors.")
        return verified_results, identified_industry

    def _call_mistral_json(
        self, domain: str, company_name: str, industry_hint: str, retry: bool = True
    ) -> Tuple[List[dict], str, str]:
        """Call Mistral for two-step reasoning: identify industry and seed domain, then find competitors.

        Returns (candidates_list, identified_industry, seed_domain_extracted).
        """
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "You are a B2B market research assistant. Given a company query or domain, "
            "first identify its official primary root web domain (e.g. 'ril.com' for Reliance Industries) "
            "in 'seed_domain'. Next determine what business the company is actually in — be specific "
            "(e.g. 'diversified conglomerate: consumer goods, appliances, real estate' "
            "rather than just 'conglomerate') in 'identified_industry'. Then return its most direct, real-world "
            "competitors — companies that compete for the same customers in the same "
            "core business in 'competitors'. If the company is diversified across multiple unrelated "
            "business lines, choose its most prominent or historically core line of "
            "business and find competitors in that specific segment. Only return "
            "companies you are confident actually exist. Respond with strict JSON only, "
            "no prose."
        )

        user_prompt = (
            f"Company/Query: {company_name or domain}\n"
            f"Domain Input: {domain}\n"
            f"Known industry hint (may be incomplete or wrong — verify against your "
            f"own knowledge before trusting it): {industry_hint}\n"
            f"Return JSON in this exact shape:\n"
            f'{{"seed_domain": "...", "identified_industry": "...", "competitors": [{{"name": "...", "domain": "..."}}]}}'
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 429 and retry:
                logger.warning("Stage 1 [Mistral]: Rate limited (429). Waiting 3s and retrying once...")
                time.sleep(3)
                return self._call_mistral_json(domain, company_name, industry_hint, retry=False)

            if resp.status_code != 200:
                logger.error(f"Stage 1 [Mistral]: API error {resp.status_code} — {resp.text[:150]}")
                # Retry once on non-200 if not already retried
                if retry:
                    time.sleep(2)
                    return self._call_mistral_json(domain, company_name, industry_hint, retry=False)
                return [], "", ""

            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not content:
                logger.error("Stage 1 [Mistral]: Empty content in response choice.")
                return [], "", ""

            parsed = json.loads(content)

            # Extract identified_industry and seed_domain from the response dict
            identified_industry = ""
            seed_domain_extracted = ""
            candidates: List[dict] = []

            if isinstance(parsed, dict):
                identified_industry = parsed.get("identified_industry", "")
                seed_domain_extracted = parsed.get("seed_domain", "").strip()
                # Extract competitors list from known keys
                for key in ["competitors", "companies", "results", "data"]:
                    if key in parsed and isinstance(parsed[key], list):
                        candidates = parsed[key]
                        break
                # Fallback: any list value in the dict
                if not candidates:
                    for v in parsed.values():
                        if isinstance(v, list):
                            candidates = v
                            break
            elif isinstance(parsed, list):
                # Legacy format: raw list with no identified_industry
                candidates = parsed

            if not candidates and not identified_industry:
                logger.error(f"Stage 1 [Mistral]: JSON structure unrecognized: {content[:100]}")

            return candidates, identified_industry, seed_domain_extracted

        except json.JSONDecodeError as e:
            logger.error(f"Stage 1 [Mistral]: JSON parse error — {e}")
            if retry:
                logger.info("Stage 1 [Mistral]: Retrying once after JSON decode failure...")
                return self._call_mistral_json(domain, company_name, industry_hint, retry=False)
            return [], "", ""
        except Exception as e:
            logger.error(f"Stage 1 [Mistral]: Request failed — {e}")
            return [], "", ""

    def _verify_domain_http(self, domain: str) -> bool:
        """Verify domain resolution using fast DNS checks and realistic browser HTTP headers."""
        if not domain:
            return False
        # Step 1: Fast DNS check
        dns_ok = False
        for candidate in [domain, f"www.{domain}"]:
            try:
                ip = socket.gethostbyname(candidate)
                if ip and ip not in ("0.0.0.0", "127.0.0.1"):
                    dns_ok = True
                    break
            except Exception:
                pass
        if not dns_ok:
            return False

        # Step 2: Fast HTTP/HTTPS check with realistic browser headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        for prefix in ["https://", "https://www.", "http://", "http://www."]:
            url = f"{prefix}{domain}"
            try:
                r = requests.head(url, timeout=(2, 3), allow_redirects=True, headers=headers)
                if r.status_code < 400 or r.status_code in (401, 403, 405, 406, 429, 503):
                    return True
            except Exception:
                try:
                    r_get = requests.get(url, timeout=(2, 3), allow_redirects=True, headers=headers, stream=True)
                    r_get.close()
                    if r_get.status_code < 400 or r_get.status_code in (401, 403, 405, 406, 429, 503):
                        return True
                except Exception:
                    continue
        return dns_ok

    def _enrich_seed(self, domain: str) -> Tuple[str, str]:
        """Calls Apollo enrich endpoint for seed organization details."""
        if not self.apollo_key:
            return "", ""
        try:
            resp = requests.get(
                "https://api.apollo.io/api/v1/organizations/enrich",
                params={"domain": domain},
                headers={"X-Api-Key": self.apollo_key, "Cache-Control": "no-cache"},
                timeout=8
            )
            if resp.status_code == 200:
                org = resp.json().get("organization", {})
                return org.get("name", ""), org.get("industry", "")
            logger.warning(f"Stage 1 [Apollo Enrich]: status {resp.status_code} for {domain}")
        except Exception as e:
            logger.warning(f"Stage 1 [Apollo Enrich]: failed for {domain} — {e}")
        return "", ""

    def _names_match(self, name1: str, name2: str) -> bool:
        if not name1 or not name2:
            return False
        n1 = re.sub(r'[^a-z0-9]', '', name1.lower())
        n2 = re.sub(r'[^a-z0-9]', '', name2.lower())
        if n1 == n2:
            return True
        if len(n1) >= 3 and n1 in n2:
            return True
        if len(n2) >= 3 and n2 in n1:
            return True
        # Check initials/acronyms (e.g. Tata Consultancy Services -> tcs)
        init1 = "".join([w[0].lower() for w in re.findall(r'[a-zA-Z0-9]+', name1) if w])
        init2 = "".join([w[0].lower() for w in re.findall(r'[a-zA-Z0-9]+', name2) if w])
        if (init1 and init1 == n2) or (init2 and init2 == n1) or (init1 == init2 and len(init1) >= 2):
            return True
        return False

    def _extract_root_domain(self, url: str) -> str:
        if not url:
            return ""
        try:
            url = re.sub(r'^https?://', '', url)
            host = url.split('/')[0].split('?')[0].lower().strip()
            if host.startswith('www.'):
                host = host[4:]
            parts = host.split('.')
            if len(parts) < 2 or len(parts[-1]) < 2:
                return ""
            return '.'.join(parts[-2:])
        except Exception:
            return ""
