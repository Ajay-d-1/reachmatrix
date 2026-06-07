import sys
import logging
from stage1_discover import find_lookalikes
from stage2_prospeo import find_decision_makers
from stage3_eazyreach import resolve_emails
from stage4_brevo import send_outreach
from utils import deduplicate_contacts, filter_cxo, safety_checkpoint
from config import MOCK_MODE

logger = logging.getLogger(__name__)


def run_pipeline(seed_domain):
    print(f"\n{'='*55}")
    print(f"  OUTREACH PIPELINE STARTING")
    print(f"  Seed domain: {seed_domain}")
    if MOCK_MODE:
        print(f"  ⚠️  MOCK MODE ON — Stage 1 using test data")
    print(f"{'='*55}\n")

    # ── STAGE 1 ──────────────────────────────────────────
    print("📡 Stage 1/4 — Finding lookalike companies...")
    domains = find_lookalikes(seed_domain)

    if not domains:
        print("❌ Stage 1 returned no domains. Exiting.")
        sys.exit(1)
    print(f"✅ {len(domains)} companies found\n")

    # ── STAGE 2 ──────────────────────────────────────────
    print("👤 Stage 2/4 — Finding decision-makers...")
    contacts = find_decision_makers(domains)

    if not contacts:
        print("❌ No contacts found. Exiting.")
        sys.exit(1)

    # Filter to C-suite/VP only, remove duplicates
    contacts = filter_cxo(contacts)
    contacts = deduplicate_contacts(contacts)
    print(f"✅ {len(contacts)} decision-makers found after filtering\n")

    # ── STAGE 3 ──────────────────────────────────────────
    print("📧 Stage 3/4 — Resolving work emails...")
    verified = resolve_emails(contacts)

    if not verified:
        print("❌ No emails resolved. Exiting.")
        sys.exit(1)
    print(f"✅ {len(verified)} emails verified\n")

    # ── SAFETY CHECKPOINT ────────────────────────────────
    proceed = safety_checkpoint(verified)
    if not proceed:
        sys.exit(0)

    # ── STAGE 4 ──────────────────────────────────────────
    print("\n🚀 Stage 4/4 — Sending outreach emails...")
    results = send_outreach(verified, seed_domain)

    # ── FINAL REPORT ─────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  PIPELINE COMPLETE")
    print(f"  ✅ Sent    : {results['sent']}")
    print(f"  ❌ Failed  : {results['failed']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    seed = input("Enter seed domain (e.g. stripe.com): ").strip()
    if not seed:
        print("No domain entered. Exiting.")
        sys.exit(1)
    run_pipeline(seed)
