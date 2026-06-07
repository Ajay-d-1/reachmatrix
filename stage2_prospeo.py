import requests
import time
import logging
from config import PROSPEO_API_KEY, PROSPEO_MAX_PER_DOMAIN

logger = logging.getLogger(__name__)


def find_decision_makers(domains):
    """
    Stage 2: Takes list of domains, returns C-suite/VP
    contacts with LinkedIn URLs.
    Uses Prospeo's new Search Person API + Enrich Person API.
    
    Two steps:
    1. search-person: finds people by company domain (no email yet)
    2. enrich-person: takes person_id, returns verified email
    """
    logger.info("Stage 2: Each run costs ~25-30 Prospeo credits. Use wisely.")
    all_contacts = []

    for domain in domains:
        logger.info(f"Stage 2: Searching decision-makers at {domain}")
        contacts = _search_and_enrich(domain)

        if contacts:
            all_contacts.extend(contacts)
            logger.info(f"Stage 2: {len(contacts)} contacts at {domain}")
        else:
            logger.warning(f"Stage 2: No contacts at {domain} — skipping")

    logger.info(f"Stage 2: Total contacts found: {len(all_contacts)}")
    return all_contacts


def _search_and_enrich(domain):
    """
    Step 1: Search for C-suite/VP people at this domain.
    Step 2: Enrich each person to get their verified email.
    """
    # Step 1 — find people
    persons = _search_persons(domain)
    if not persons:
        return []

    # Step 2 — enrich each to get email + LinkedIn
    contacts = []
    for person in persons[:PROSPEO_MAX_PER_DOMAIN]:
        person_id = person.get("person", {}).get("person_id")
        if not person_id:
            continue

        enriched = _enrich_person(person_id)
        if enriched:
            contacts.append(enriched)
        
        time.sleep(0.5)  # small delay to avoid rate limits

    return contacts


def _search_persons(domain):
    """
    Calls Prospeo Search Person API with company website filter.
    Filters for C-suite and VP seniority only.
    Returns raw results list.
    """
    url = "https://api.prospeo.io/search-person"

    headers = {
        "X-KEY": PROSPEO_API_KEY,
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
                "include": [
                    "Founder/Owner",
                    "C-Suite",
                    "Vice President",
                    "Director"
                ]
            }
        }
    }

    try:
        response = requests.post(url, json=payload,
                                 headers=headers, timeout=15)

        if response.status_code == 429:
            logger.warning("Stage 2: Rate limited. Waiting 5s...")
            time.sleep(5)
            response = requests.post(url, json=payload,
                                     headers=headers, timeout=15)

        if response.status_code != 200:
            logger.error(f"Stage 2: Search error {response.status_code} "
                         f"for {domain} — {response.text[:100]}")
            return []

        data = response.json()
        
        if data.get("error"):
            logger.error(f"Stage 2: API error for {domain} — "
                         f"{data.get('error_code')}")
            return []

        results = data.get("results", [])
        logger.info(f"Stage 2: Found {len(results)} people at {domain}")
        return results

    except requests.exceptions.Timeout:
        logger.error(f"Stage 2: Timeout searching {domain}")
        return []
    except Exception as e:
        logger.error(f"Stage 2: Error searching {domain} — {e}")
        return []


def _enrich_person(person_id):
    """
    Calls Prospeo Enrich Person API to get verified email.
    person_id must be inside a 'data' object — that's the correct format.
    only_verified_email=True means we don't waste credits on unverified emails.
    """
    url = "https://api.prospeo.io/enrich-person"

    headers = {
        "X-KEY": PROSPEO_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "only_verified_email": True,
        "data": {
            "person_id": person_id
        }
    }

    try:
        response = requests.post(url, json=payload,
                                 headers=headers, timeout=15)

        if response.status_code != 200:
            logger.error(f"Stage 2: Enrich error {response.status_code} "
                         f"for person {person_id} — {response.text[:80]}")
            return None

        data = response.json()

        if data.get("error"):
            logger.warning(f"Stage 2: No match for {person_id} "
                           f"— {data.get('error_code')}")
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

        # Email is nested inside an object
        email_obj = person.get("email", {})
        email = ""
        if isinstance(email_obj, dict):
            email = email_obj.get("email", "")
        elif isinstance(email_obj, str):
            email = email_obj

        return {
            "name": name,
            "title": person.get("current_job_title", ""),
            "company": company.get("name", ""),
            "domain": company.get("domain", ""),
            "linkedin_url": person.get("linkedin_url", ""),
            "email": email,
        }

    except Exception as e:
        logger.error(f"Stage 2: Enrich exception for {person_id} — {e}")
        return None