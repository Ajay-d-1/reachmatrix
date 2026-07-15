import time
import logging
import requests
from typing import List
from config import PROSPEO_API_KEY, PROSPEO_MAX_PER_DOMAIN
from .base import PeopleSearchProvider, PersonResult

logger = logging.getLogger(__name__)


class ProspeoPeopleSearchProvider(PeopleSearchProvider):
    """
    Stage 2 Provider: Searches and enriches decision makers at target domains via Prospeo API.
    """

    def __init__(self, api_key: str = None, max_per_domain: int = None):
        self.api_key = api_key or PROSPEO_API_KEY
        self.max_per_domain = max_per_domain or PROSPEO_MAX_PER_DOMAIN

    def search_people(
        self, domain: str, seniority: List[str] = None
    ) -> List[PersonResult]:
        if not self.api_key:
            logger.warning(f"Stage 2 [Prospeo]: PROSPEO_API_KEY not set. Cannot search domain {domain}.")
            return []

        # Default seniorities if none passed
        if not seniority:
            seniority = ["Founder/Owner", "C-Suite", "Vice President", "Director"]

        logger.info(f"Stage 2 [Prospeo]: Searching people at domain={domain}")
        persons = self._search_persons(domain, seniority)
        if not persons:
            return []

        contacts: List[PersonResult] = []
        for person in persons[:self.max_per_domain]:
            person_id = person.get("person", {}).get("person_id")
            if not person_id:
                continue

            enriched = self._enrich_person(person_id)
            if enriched:
                contacts.append(enriched)

            time.sleep(0.5)  # rate limit courtesy delay

        logger.info(f"Stage 2 [Prospeo]: Found {len(contacts)} verified decision makers at {domain}")
        return contacts

    def _search_persons(self, domain: str, seniority: List[str]) -> List[dict]:
        url = "https://api.prospeo.io/search-person"
        headers = {
            "X-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "page": 1,
            "filters": {
                "company": {
                    "websites": {
                        "include": [domain]
                    }
                },
                "person_seniority": {
                    "include": seniority
                }
            }
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 429:
                logger.warning(f"Stage 2 [Prospeo]: Rate limited searching {domain}")
                return []
            if resp.status_code != 200:
                logger.error(f"Stage 2 [Prospeo]: Search error {resp.status_code} for {domain} — {resp.text[:100]}")
                return []

            data = resp.json()
            if data.get("error"):
                logger.error(f"Stage 2 [Prospeo]: API returned error for {domain} — {data.get('error_code')}")
                return []

            return data.get("results", [])
        except Exception as e:
            logger.error(f"Stage 2 [Prospeo]: Request exception searching {domain} — {e}")
            return []

    def _enrich_person(self, person_id: str) -> PersonResult:
        url = "https://api.prospeo.io/enrich-person"
        headers = {
            "X-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "only_verified_email": True,
            "data": {
                "person_id": person_id
            }
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 429:
                logger.warning(f"Stage 2 [Prospeo]: Rate limited on enrich for {person_id}")
                return None
            if resp.status_code != 200:
                logger.error(f"Stage 2 [Prospeo]: Enrich error {resp.status_code} for {person_id} — {resp.text[:80]}")
                return None

            data = resp.json()
            if data.get("error"):
                return None

            person = data.get("person", {})
            company = data.get("company", {}) or {}

            name = person.get("full_name", "").strip()
            if not name:
                first = person.get("first_name", "")
                last = person.get("last_name", "")
                name = f"{first} {last}".strip()

            if not name:
                return None

            email_obj = person.get("email", {})
            email = ""
            if isinstance(email_obj, dict):
                email = email_obj.get("email", "")
            elif isinstance(email_obj, str):
                email = email_obj

            if not email or "@" not in email:
                return None

            return {
                "name": name,
                "title": person.get("current_job_title", ""),
                "company": company.get("name", ""),
                "domain": company.get("domain", "") or "",
                "linkedin_url": person.get("linkedin_url", "") or "",
                "email": email,
                "email_verified": True,
                "provider": "prospeo"
            }
        except Exception as e:
            logger.error(f"Stage 2 [Prospeo]: Enrich exception for {person_id} — {e}")
            return None
