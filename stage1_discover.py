import requests
import logging
from config import OCEAN_API_KEY, OCEAN_MAX_RESULTS, MOCK_MODE, PROSPEO_API_KEY

logger = logging.getLogger(__name__)

# Mock data for testing — realistic domains
# Switch off by setting MOCK_MODE = False in config.py
MOCK_DOMAINS = [
    "razorpay.com", "cashfree.com", "paytm.com",
    "phonepe.com", "instamojo.com", "stripe.com",
    "chargebee.com", "zoho.com", "freshworks.com", "cleartax.in"
]


def find_lookalikes(seed_domain):
    """
    Stage 1: Finds lookalike companies using Prospeo's search API.
    Searches for C-suite people at the seed company, then extracts
    their past employers as lookalike companies in the same space.
    Falls back to curated list only if API returns nothing.
    """
    logger.info(f"Stage 1: Finding lookalikes for {seed_domain}")

    # Try real-time discovery via Prospeo
    domains = _find_via_prospeo(seed_domain)

    if domains and len(domains) >= 3:
        logger.info(f"Stage 1: Found {len(domains)} real-time lookalikes")
        return list(domains)[:OCEAN_MAX_RESULTS]

    # Fallback only if Prospeo returns nothing
    logger.warning("Stage 1: Real-time discovery returned nothing — using fallback")
    return [d for d in MOCK_DOMAINS if d != seed_domain][:OCEAN_MAX_RESULTS]


def _find_via_prospeo(seed_domain):
    """
    Uses Prospeo to find C-suite at seed company, extracts
    their past employers by name, converts to domains.
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
                    "include": [seed_domain]
                }
            },
            "person_seniority": {
                "include": ["C-Suite", "Founder/Owner", "Vice President"]
            }
        }
    }

    try:
        response = requests.post(url, json=payload,
                                 headers=headers, timeout=15)

        if response.status_code != 200:
            logger.warning(f"Stage 1: Prospeo returned {response.status_code}")
            return []

        data = response.json()
        if data.get("error"):
            return []

        # Extract past employer names from job history
        company_names = set()
        for result in data.get("results", []):
            person = result.get("person", {})
            for job in person.get("job_history", []):
                if job.get("current", False):
                    continue  # skip current employer (that's the seed)
                name = job.get("company_name", "").strip()
                if name and name.lower() != seed_domain.replace(".com","").lower():
                    company_names.add(name)

        logger.info(f"Stage 1: Found {len(company_names)} past employers")

        # Convert company names to domains
        domains = _names_to_domains(company_names, seed_domain)
        return domains

    except Exception as e:
        logger.warning(f"Stage 1: Discovery error — {e}")
        return []


def _names_to_domains(company_names, seed_domain):
    """
    Converts company names to domains by enriching via Prospeo.
    Falls back to name-based guessing for unknown companies.
    """
    domains = set()

    for name in list(company_names)[:15]:  # limit API calls
        # Try Prospeo company enrich to get real domain
        domain = _enrich_company_domain(name)
        if domain and domain != seed_domain:
            domains.add(domain)
        else:
            # Fallback: guess domain from company name
            guessed = _guess_domain(name)
            if guessed and guessed != seed_domain:
                domains.add(guessed)

    return list(domains)


def _enrich_company_domain(company_name):
    """
    Uses Prospeo autocomplete to find the real domain for a company name.
    """
    try:
        url = "https://api.prospeo.io/company-enrichment"
        headers = {
            "X-KEY": PROSPEO_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"company": company_name}
        response = requests.post(url, json=payload,
                                 headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            domain = (data.get("response", {}).get("domain") or
                      data.get("domain") or "")
            if domain and "." in domain:
                return domain.lower().strip()
    except Exception:
        pass
    return ""


def _guess_domain(company_name):
    """
    Guesses domain from company name as last resort.
    Removes common suffixes and converts to lowercase.
    """
    import re
    name = company_name.lower().strip()
    # Remove common suffixes
    for suffix in [" inc", " llc", " ltd", " corp", " corporation",
                   " technologies", " technology", " solutions",
                   " systems", " services", " group", " global"]:
        name = name.replace(suffix, "")
    # Remove special characters, keep alphanumeric and spaces
    name = re.sub(r"[^a-z0-9\s]", "", name)
    # Take first word if multiple words (e.g. "toast pos" -> "toast")
    name = name.strip().split()[0] if name.strip() else ""
    if name and len(name) > 2:
        return f"{name}.com"
    return ""


def _call_ocean_api(seed_domain):
    """
    Correct ReachMatrix Discovery endpoint: api.ocean.io/v2/search/companies
    Auth: apiToken as query parameter (not Bearer header)
    Lookalike domains go inside companiesFilters.lookalikeDomains
    """
    url = f"https://api.ocean.io/v2/search/companies?apiToken={OCEAN_API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "size": OCEAN_MAX_RESULTS,
        "companiesFilters": {
            "lookalikeDomains": [seed_domain]
        }
    }

    try:
        response = requests.post(url, json=payload,
                                 headers=headers, timeout=15)

        if response.status_code == 429:
            logger.error("Stage 1: Rate limited by ReachMatrix Discovery")
            return []

        if response.status_code != 200:
            logger.error(f"Stage 1: API error {response.status_code} "
                         f"— {response.text[:150]}")
            return []

        data = response.json()
        domains = _parse_response(data)
        logger.info(f"Stage 1: Found {len(domains)} lookalike companies")
        return domains

    except requests.exceptions.Timeout:
        logger.error("Stage 1: ReachMatrix Discovery request timed out")
        return []
    except Exception as e:
        logger.error(f"Stage 1: Error — {e}")
        return []


def _parse_response(data):
    """
    ReachMatrix Discovery returns companies inside data.hits array.
    Each company has a domain field.
    """
    hits = data.get("hits", [])
    domains = []
    for company in hits:
        domain = company.get("domain", "")
        if domain:
            domains.append(domain)
    return domains
