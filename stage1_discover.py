import requests
import logging
from config import OCEAN_MAX_RESULTS, APOLLO_API_KEY

logger = logging.getLogger(__name__)

def find_lookalikes(seed_domain):
    """
    Stage 1: Uses Apollo.io Organization Search API to find
    companies similar to the seed domain.
    Filters by same industry as the seed company.
    Falls back to curated list if API fails.
    """
    logger.info(f"Stage 1: Finding lookalikes for {seed_domain}")

    # First get the seed company's industry
    industry = _get_company_industry(seed_domain)

    # Then search for similar companies in that industry
    domains = _search_similar_companies(seed_domain, industry)

    if domains and len(domains) >= 3:
        logger.info(f"Stage 1: Found {len(domains)} real lookalikes via Apollo")
        return domains[:OCEAN_MAX_RESULTS]

    logger.warning("Stage 1: Apollo returned nothing — using curated fallback")
    return _curated_fallback(seed_domain)[:OCEAN_MAX_RESULTS]


def _get_company_industry(domain):
    """
    Auth: X-Api-Key in header (not request body)
    Method: GET with domain as query param
    """
    url = "https://api.apollo.io/api/v1/organizations/enrich"

    headers = {
        "X-Api-Key": APOLLO_API_KEY,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }

    try:
        response = requests.get(
            url,
            params={"domain": domain},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            org = data.get("organization", {})
            industry = org.get("industry", "")
            logger.info(f"Stage 1: Seed industry — {industry}")
            return industry
        else:
            logger.warning(f"Stage 1: Apollo enrich {response.status_code}")

    except Exception as e:
        logger.warning(f"Stage 1: Industry lookup failed — {e}")

    return ""


def _search_similar_companies(seed_domain, industry):
    """
    Auth: X-Api-Key in header
    Method: POST with filters in body
    """
    url = "https://api.apollo.io/api/v1/mixed_companies/search"

    headers = {
        "X-Api-Key": APOLLO_API_KEY,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }

    payload = {
        "page": 1,
        "per_page": 15,
        "organization_num_employees_ranges": ["11,1000"],
    }

    if industry:
        payload["organization_industries"] = [industry]

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=15
        )

        if response.status_code == 403:
            logger.warning("Stage 1: Apollo plan doesn't support search")
            return []

        if response.status_code != 200:
            logger.warning(f"Stage 1: Apollo search {response.status_code} — {response.text[:100]}")
            return []

        data = response.json()
        companies = data.get("organizations", [])

        domains = []
        for company in companies:
            domain = company.get("primary_domain", "")
            if domain and domain != seed_domain and "." in domain:
                domains.append(domain.lower().strip())

        logger.info(f"Stage 1: Apollo returned {len(domains)} companies")
        return domains

    except Exception as e:
        logger.warning(f"Stage 1: Apollo search error — {e}")
        return []


def _curated_fallback(seed_domain):
    """Last resort fallback if Apollo fails."""
    defaults = [
        "razorpay.com", "cashfree.com", "chargebee.com",
        "freshworks.com", "zoho.com", "clevertap.com",
        "browserstack.com", "postman.com", "hasura.io", "mixpanel.com"
    ]
    return [d for d in defaults if d != seed_domain]
