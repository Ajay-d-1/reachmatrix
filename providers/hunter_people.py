import logging
import requests
from typing import List
from config import HUNTER_API_KEY
from .base import PeopleSearchProvider, PersonResult

logger = logging.getLogger(__name__)


class HunterPeopleSearchProvider(PeopleSearchProvider):
    """
    Stage 2 Fallback Provider: Searches contacts at target domains via Hunter.io API when Prospeo returns nothing.
    """

    def __init__(self, api_key: str = None, max_results: int = 2):
        self.api_key = api_key or HUNTER_API_KEY
        self.max_results = max_results

    def search_people(
        self, domain: str, seniority: List[str] = None
    ) -> List[PersonResult]:
        if not self.api_key:
            logger.warning(f"Stage 2 [Hunter]: HUNTER_API_KEY not set. Cannot run fallback search for {domain}.")
            return []

        target_titles = ["ceo", "cto", "coo", "cfo", "cpo", "vp", "founder", "co-founder", "director", "head", "chief", "president"]

        url = "https://api.hunter.io/v2/domain-search"
        params = {
            "domain": domain,
            "api_key": self.api_key,
            "type": "personal",
            "seniority": "senior,executive",
            "limit": 10
        }

        try:
            logger.info(f"Stage 2 [Hunter Fallback]: Searching people at domain={domain}")
            resp = requests.get(url, params=params, timeout=12)
            if resp.status_code == 429:
                logger.warning(f"Stage 2 [Hunter]: Rate limited searching {domain}")
                return []
            if resp.status_code != 200:
                logger.error(f"Stage 2 [Hunter]: Error {resp.status_code} for {domain} — {resp.text[:100]}")
                return []

            data = resp.json().get("data", {})
            emails_list = data.get("emails", [])
            if not emails_list:
                return []

            contacts: List[PersonResult] = []
            for item in emails_list:
                email = item.get("value", "").strip()
                if not email or "@" not in email:
                    continue

                first = item.get("first_name", "") or ""
                last = item.get("last_name", "") or ""
                name = f"{first} {last}".strip()
                if not name:
                    name = email.split('@')[0].replace('.', ' ').title()

                title = item.get("position", "") or ""
                title_lower = title.lower()

                # Check if position/title matches target leadership roles
                is_senior = any(t in title_lower for t in target_titles) or item.get("seniority") in ["senior", "executive"]
                if not is_senior:
                    continue

                # Check email verification status or confidence
                ver_status = item.get("verification", {}).get("status", "") if isinstance(item.get("verification"), dict) else ""
                confidence = item.get("confidence", 0) or 0
                is_verified = (ver_status == "valid") or (confidence >= 80)

                if not is_verified:
                    continue

                result: PersonResult = {
                    "name": name,
                    "title": title or "Executive",
                    "company": data.get("organization", "") or domain.split('.')[0].title(),
                    "domain": domain,
                    "linkedin_url": item.get("linkedin", "") or "",
                    "email": email,
                    "email_verified": True,
                    "provider": "hunter"
                }
                contacts.append(result)
                if len(contacts) >= self.max_results:
                    break

            logger.info(f"Stage 2 [Hunter Fallback]: Found {len(contacts)} contacts for {domain}")
            return contacts

        except Exception as e:
            logger.error(f"Stage 2 [Hunter]: Exception searching {domain} — {e}")
            return []
