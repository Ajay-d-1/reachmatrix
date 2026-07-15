import sys
import logging
from providers import (
    MistralDiscoveryProvider,
    ProspeoPeopleSearchProvider,
    HunterPeopleSearchProvider,
    CompetitorResult,
    PersonResult,
)
from stage3_Verify import resolve_emails
from stage4_brevo import send_outreach
from utils import deduplicate_contacts, filter_cxo, safety_checkpoint
from config import DEMO_MODE

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Initialize providers
discovery_provider = MistralDiscoveryProvider()
prospeo_provider = ProspeoPeopleSearchProvider()
hunter_provider = HunterPeopleSearchProvider()


def run_pipeline(seed_domain: str):
    print(f"\n{'='*60}")
    print(f"  REACHMATRIX v2 — B2B OUTREACH PIPELINE")
    print(f"  Seed domain : {seed_domain}")
    print(f"  DEMO_MODE   : {DEMO_MODE}")
    print(f"{'='*60}\n")

    # ── STAGE 1 ──────────────────────────────────────────
    print("📡 Stage 1/4 — Competitor Discovery (Mistral LLM + Verification)...")
    companies: list[CompetitorResult] = discovery_provider.find_competitors(seed_domain)

    if not companies:
        print("❌ Stage 1 returned no verified competitors. Exiting (No static fallback).")
        sys.exit(1)

    print(f"✅ {len(companies)} competitors discovered:\n")
    for i, c in enumerate(companies, 1):
        print(f"   {i}. {c['name']} ({c['domain']}) | source: {c['source']} | confidence: {c['confidence'].upper()}")
    print()

    # ── STAGE 2 ──────────────────────────────────────────
    print("👤 Stage 2/4 — Prospecting Decision Makers (Prospeo + Hunter fallback)...")
    all_contacts: list[PersonResult] = []

    for comp in companies:
        comp_domain = comp["domain"]
        contacts = prospeo_provider.search_people(comp_domain)
        if not contacts:
            print(f"   ⚠️ Prospeo returned 0 contacts for {comp_domain}. Failing over to Hunter.io...")
            contacts = hunter_provider.search_people(comp_domain)
        if contacts:
            print(f"   found {len(contacts)} contacts at {comp['name']} via {contacts[0]['provider']}")
            all_contacts.extend(contacts)

    if not all_contacts:
        print("❌ No contacts found across any competitor. Exiting.")
        sys.exit(1)

    # Filter & Deduplicate
    contacts_filtered = filter_cxo(all_contacts)
    contacts_unique = deduplicate_contacts(contacts_filtered)
    print(f"\n✅ {len(contacts_unique)} decision-makers after leadership filter and deduplication.\n")

    # ── STAGE 3 ──────────────────────────────────────────
    print("📧 Stage 3/4 — Verifying Work Emails...")
    verified = resolve_emails(contacts_unique)

    if not verified:
        print("❌ No emails verified. Exiting.")
        sys.exit(1)
    print(f"✅ {len(verified)} verified work emails ready for review.\n")

    # ── SAFETY CHECKPOINT ────────────────────────────────
    proceed = safety_checkpoint(verified)
    if not proceed:
        sys.exit(0)

    # ── STAGE 4 ──────────────────────────────────────────
    print("\n🚀 Stage 4/4 — Sending Outreach via Brevo...")
    results = send_outreach(verified, seed_domain)

    # ── FINAL REPORT ─────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  ✅ Sent   : {results['sent']}")
    print(f"  ❌ Failed : {results['failed']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    seed = input("Enter seed domain (e.g. stripe.com or swiggy.com): ").strip()
    if not seed:
        print("No domain entered. Exiting.")
        sys.exit(1)
    run_pipeline(seed)
