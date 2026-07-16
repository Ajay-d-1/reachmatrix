"""
Live integration test for the hardcoded-industry-fallback fix.

Tests 4 domains across different company types to verify:
1. godrej.com - diversified conglomerate (was returning IT companies before the fix)
2. zomato.com - food delivery (regression check)
3. infosys.com - IT services (regression check)
4. amul.com - mid-size/less-famous (FMCG/dairy — should NOT default to IT)

Requires MISTRAL_API_KEY in .env (APOLLO_API_KEY optional).
"""
import sys
import logging
from providers import MistralDiscoveryProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout
)

IT_DOMAINS = {"tcs.com", "infosys.com", "wipro.com", "hcltech.com", "techmahindra.com"}

provider = MistralDiscoveryProvider()

test_cases = [
    {
        "domain": "godrej.com",
        "expect_industry_contains": ["consumer", "conglomerate", "appliance", "real estate", "FMCG"],
        "must_not_contain_domains": IT_DOMAINS,
        "description": "Diversified conglomerate — must NOT return IT companies",
    },
    {
        "domain": "zomato.com",
        "expect_industry_contains": ["food", "delivery", "restaurant"],
        "must_not_contain_domains": set(),
        "description": "Food delivery — regression check",
    },
    {
        "domain": "infosys.com",
        "expect_industry_contains": ["IT", "technology", "consulting", "services", "software"],
        "must_not_contain_domains": set(),
        "description": "IT services — regression check",
    },
    {
        "domain": "amul.com",
        "expect_industry_contains": ["dairy", "FMCG", "food", "consumer"],
        "must_not_contain_domains": IT_DOMAINS,
        "description": "Mid-size dairy/FMCG — must NOT default to IT",
    },
]

results_summary = []

for tc in test_cases:
    domain = tc["domain"]
    print(f"\n{'='*70}")
    print(f"  TEST: {domain} — {tc['description']}")
    print(f"{'='*70}")

    companies, identified_industry = provider.find_competitors(domain)

    print(f"\n  Identified Industry: {identified_industry}")
    print(f"  Competitors ({len(companies)}):")
    for c in companies:
        print(f"    - {c['name']} ({c['domain']}) [{c['confidence']}/{c['source']}]")

    # Check identified_industry contains at least one expected keyword (case-insensitive)
    industry_lower = identified_industry.lower()
    industry_ok = any(kw.lower() in industry_lower for kw in tc["expect_industry_contains"])

    # Check no forbidden domains leaked in
    comp_domains = {c["domain"] for c in companies}
    leaked = comp_domains & tc["must_not_contain_domains"]

    status = "PASS" if (industry_ok and not leaked) else "FAIL"
    detail = ""
    if not industry_ok:
        detail += f"  Industry '{identified_industry}' did not match any of {tc['expect_industry_contains']}. "
    if leaked:
        detail += f"  Forbidden domains found: {leaked}. "

    results_summary.append((domain, status, detail))
    print(f"\n  >>> {status} {detail}")

print(f"\n\n{'='*70}")
print("  SUMMARY")
print(f"{'='*70}")
all_pass = True
for domain, status, detail in results_summary:
    icon = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"  {icon} {domain}: {status} {detail}")
    if status != "PASS":
        all_pass = False

if all_pass:
    print("\n  All tests PASSED.")
else:
    print("\n  Some tests FAILED.")
    sys.exit(1)
