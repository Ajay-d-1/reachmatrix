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
    Gets the industry of the seed company using Apollo
    organization enrichment endpoint.
    """
    url = "https://api.apollo.io/v1/organizations/enrich"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY
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
            keywords = org.get("keywords", [])
            logger.info(f"Stage 1: Seed industry — {industry}")
            return industry

    except Exception as e:
        logger.warning(f"Stage 1: Could not get industry — {e}")

    return ""


def _search_similar_companies(seed_domain, industry):
    """
    Searches Apollo for companies in the same industry
    as the seed domain. Excludes the seed itself.
    """
    url = "https://api.apollo.io/v1/mixed_companies/search"

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    payload = {
        "page": 1,
        "per_page": 15,
        "organization_industries": [industry] if industry else [],
        "organization_num_employees_ranges": ["11,500"],
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=15
        )

        if response.status_code != 200:
            logger.warning(f"Stage 1: Apollo search returned {response.status_code}")
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
