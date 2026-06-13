import re
import requests
import logging
from config import OCEAN_MAX_RESULTS, APOLLO_API_KEY, SERPAPI_KEY

logger = logging.getLogger(__name__)

# Domains to always filter out — not companies
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


def find_lookalikes(seed_domain):
    """
    Stage 1: Find companies similar to the seed domain.
    
    Flow:
      1. Apollo enrich  → get company name + industry (free tier, works)
      2. SerpAPI search → find real competitor domains
      3. Fallback       → curated list only if both above fail
    """
    logger.info(f"Stage 1: Finding lookalikes for {seed_domain}")

    # Step 1: get seed company context from Apollo
    company_name, industry = _enrich_seed(seed_domain)
    logger.info(f"Stage 1: Seed — name={company_name}, industry={industry}")

    # Step 2: use SerpAPI to find similar companies
    domains = _serp_lookalikes(seed_domain, company_name, industry)

    if len(domains) >= 3:
        logger.info(f"Stage 1: SerpAPI found {len(domains)} lookalikes — {domains}")
        return domains[:OCEAN_MAX_RESULTS]

    # Step 3: try a broader SerpAPI query
    if len(domains) < 3 and company_name:
        logger.info("Stage 1: First query weak, trying broader search")
        more = _serp_lookalikes_broad(company_name, industry)
        combined = list(dict.fromkeys(domains + more))  # dedupe, preserve order
        if len(combined) >= 2:
            logger.info(f"Stage 1: Broader search added results — {combined}")
            return combined[:OCEAN_MAX_RESULTS]

    # Step 4: curated fallback
    logger.warning("Stage 1: SerpAPI returned nothing useful — using curated fallback")
    return _curated_fallback(seed_domain)[:OCEAN_MAX_RESULTS]


def _enrich_seed(domain):
    """
    GET apollo.io/api/v1/organizations/enrich — works on free tier.
    Returns (company_name, industry).
    """
    try:
        resp = requests.get(
            "https://api.apollo.io/api/v1/organizations/enrich",
            params={"domain": domain},
            headers={
                "X-Api-Key": APOLLO_API_KEY,
                "Cache-Control": "no-cache",
            },
            timeout=10
        )
        if resp.status_code == 200:
            org = resp.json().get("organization", {})
            name = org.get("name", "")
            industry = org.get("industry", "")
            return name, industry
        logger.warning(f"Stage 1: Apollo enrich returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Stage 1: Apollo enrich failed — {e}")
    return "", ""


def _serp_lookalikes(seed_domain, company_name, industry):
    """
    Primary SerpAPI query: targeted competitor search.
    Query: "competitors alternatives to {company_name} {industry} -site:{seed_domain}"
    """
    if not SERPAPI_KEY:
        logger.warning("Stage 1: SERPAPI_KEY not set")
        return []

    if company_name:
        query = f'"{company_name}" competitors OR alternatives {industry}'
    else:
        # strip TLD and use as company name approximation
        name_guess = seed_domain.split('.')[0]
        query = f'{name_guess} competitors alternatives {industry}'

    logger.info(f"Stage 1: SerpAPI primary query — {query}")

    return _run_serp_query(query, seed_domain)


def _serp_lookalikes_broad(company_name, industry):
    """
    Fallback SerpAPI query: broader industry search.
    """
    query = f'top {industry} SaaS companies like {company_name} site:crunchbase.com OR site:g2.com'
    logger.info(f"Stage 1: SerpAPI broad query — {query}")
    return _run_serp_query(query, "")


def _run_serp_query(query, exclude_domain):
    """
    Calls SerpAPI, extracts clean root domains from organic results.
    """
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 10,
                "hl": "en",
                "gl": "us",
            },
            timeout=15
        )

        if resp.status_code != 200:
            logger.warning(f"Stage 1: SerpAPI returned {resp.status_code} — {resp.text[:120]}")
            return []

        data = resp.json()
        results = data.get("organic_results", [])
        domains = []

        for result in results:
            # Try the link field first, fall back to displayed URL
            url = result.get("link", "") or result.get("displayed_link", "")
            domain = _extract_root_domain(url)

            if not domain:
                continue
            if domain in NOISE_DOMAINS:
                continue
            if exclude_domain and domain == exclude_domain:
                continue
            if domain in domains:
                continue

            domains.append(domain)

        logger.info(f"Stage 1: SerpAPI extracted {len(domains)} domains — {domains}")
        return domains

    except Exception as e:
        logger.warning(f"Stage 1: SerpAPI call failed — {e}")
        return []


def _extract_root_domain(url):
    """
    Pulls the root domain (no www, no path, no subdomains) from any URL.
    Returns empty string if extraction fails.
    """
    if not url:
        return ""
    try:
        # Strip protocol
        url = re.sub(r'^https?://', '', url)
        # Take only the host part
        host = url.split('/')[0].split('?')[0].lower().strip()
        # Remove www.
        if host.startswith('www.'):
            host = host[4:]
        # Must have a dot and a TLD (at least 2 chars)
        parts = host.split('.')
        if len(parts) < 2 or len(parts[-1]) < 2:
            return ""
        # Return last two parts (root domain only)
        return '.'.join(parts[-2:])
    except Exception:
        return ""


def _curated_fallback(seed_domain):
    """Last resort — only reached if both Apollo and SerpAPI fail."""
    defaults = [
        "razorpay.com", "cashfree.com", "chargebee.com",
        "freshworks.com", "zoho.com", "clevertap.com",
        "browserstack.com", "postman.com", "hasura.io", "mixpanel.com"
    ]
    return [d for d in defaults if d != seed_domain]
