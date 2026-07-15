import re
import json
import time
import logging
import requests
from typing import List, Tuple
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
    ) -> List[CompetitorResult]:
        logger.info(f"Stage 1 [Mistral]: Finding competitors for domain={domain}")

        # If seed company name/industry are not provided, enrich seed via Apollo
        if not company_name or not industry:
            enriched_name, enriched_ind = self._enrich_seed(domain)
            company_name = company_name or enriched_name or domain.split('.')[0].title()
            industry = industry or enriched_ind or "Technology / B2B SaaS"
            logger.info(f"Stage 1 [Mistral]: Seed context — name='{company_name}', industry='{industry}'")

        if not self.api_key:
            logger.error("Stage 1 [Mistral]: MISTRAL_API_KEY not configured. Cannot discover competitors.")
            return []

        # Call Mistral LLM for structured JSON competitor discovery
        raw_candidates = self._call_mistral_json(domain, company_name, industry)
        if not raw_candidates:
            logger.warning("Stage 1 [Mistral]: No candidates returned from LLM. Never returning static fallback.")
            return []

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
        return verified_results

    def _call_mistral_json(self, domain: str, company_name: str, industry: str, retry: bool = True) -> List[dict]:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "You are a B2B market research assistant. Given a company, return its most "
            "direct, real-world competitors — companies that compete for the same "
            "customers with the same core product or service. Only return companies you "
            "are confident actually exist. Respond with strict JSON only, no prose."
        )

        user_prompt = (
            f"Company: {company_name}\n"
            f"Domain: {domain}\n"
            f"Industry: {industry}\n"
            f"Return the top 5 direct competitors as JSON:\n"
            f'[{{"name": "...", "domain": "..."}}]'
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
                return self._call_mistral_json(domain, company_name, industry, retry=False)

            if resp.status_code != 200:
                logger.error(f"Stage 1 [Mistral]: API error {resp.status_code} — {resp.text[:150]}")
                # Retry once on non-200 if not already retried
                if retry:
                    time.sleep(2)
                    return self._call_mistral_json(domain, company_name, industry, retry=False)
                return []

            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not content:
                logger.error("Stage 1 [Mistral]: Empty content in response choice.")
                return []

            parsed = json.loads(content)
            # Handle if wrapped in {"competitors": [...]} or raw list
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                for key in ["competitors", "companies", "results", "data"]:
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]
                # Check if values inside dict are a list
                for v in parsed.values():
                    if isinstance(v, list):
                        return v
            logger.error(f"Stage 1 [Mistral]: JSON structure unrecognized: {content[:100]}")
            return []

        except json.JSONDecodeError as e:
            logger.error(f"Stage 1 [Mistral]: JSON parse error — {e}")
            if retry:
                logger.info("Stage 1 [Mistral]: Retrying once after JSON decode failure...")
                return self._call_mistral_json(domain, company_name, industry, retry=False)
            return []
        except Exception as e:
            logger.error(f"Stage 1 [Mistral]: Request failed — {e}")
            return []

    def _verify_domain_http(self, domain: str) -> bool:
        """HTTP HEAD request (with GET fallback) to verify domain resolution."""
        for proto in ["https://", "http://"]:
            url = f"{proto}{domain}"
            try:
                # HEAD request first
                r = requests.head(url, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code < 400 or r.status_code in (401, 403):
                    return True
            except requests.exceptions.RequestException:
                try:
                    # Fallback to GET with short timeout if HEAD fails/rejected
                    r_get = requests.get(url, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
                    r_get.close()
                    if r_get.status_code < 400 or r_get.status_code in (401, 403):
                        return True
                except requests.exceptions.RequestException:
                    continue
        return False

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
