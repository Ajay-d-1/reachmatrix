from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging
import os
import traceback

from providers import (
    MistralDiscoveryProvider,
    ProspeoPeopleSearchProvider,
    HunterPeopleSearchProvider,
    CompetitorResult,
    PersonResult,
)
from stage3_Verify import resolve_emails
from stage4_brevo import send_outreach
from utils import deduplicate_contacts, filter_cxo

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize modular providers
discovery_provider = MistralDiscoveryProvider()
prospeo_provider = ProspeoPeopleSearchProvider()
hunter_provider = HunterPeopleSearchProvider()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/run-pipeline", methods=["POST"])
def run_pipeline():
    data = request.json or {}
    seed_domain = data.get("domain", "").strip()
    
    if not seed_domain:
        return jsonify({"error": "domain is required"}), 400

    logger.info(f"Starting v2 pipeline for seed domain: {seed_domain}")
    
    try:
        # Stage 1: Competitor Discovery (Mistral + Verification)
        companies: list[CompetitorResult] = discovery_provider.find_competitors(seed_domain)
        if not companies:
            logger.warning(f"No competitors discovered or verified for {seed_domain}. Returning explicit status without static fallback.")
            return jsonify({
                "status": "error",
                "error": "Competitor discovery returned no results or low confidence for this domain. No static fallback applied.",
                "companies": [],
                "contacts": [],
                "metrics": {"companies": 0, "prospects": 0, "verified": 0}
            }), 404

        # Check confidence overall for warning / partial status
        low_confidence_count = sum(1 for c in companies if c["confidence"] == "low" or c["source"] == "llm_unverified")
        status = "partial" if low_confidence_count > 0 or len(companies) < 2 else "success"

        # Stage 2a: People Search on SEED domain (separate dataset)
        seed_contacts_verified: list[PersonResult] = []
        try:
            logger.info(f"Stage 2a: Prospecting decision makers at SEED domain ({seed_domain})")
            seed_people = prospeo_provider.search_people(seed_domain)
            if not seed_people:
                logger.info(f"Stage 2a: Primary provider returned 0 for seed {seed_domain}. Failing over to Hunter.io...")
                seed_people = hunter_provider.search_people(seed_domain)
            if seed_people:
                seed_filtered = filter_cxo(seed_people)
                seed_unique = deduplicate_contacts(seed_filtered)
                seed_contacts_verified = resolve_emails(seed_unique)
                # Tag each seed contact
                for sc in seed_contacts_verified:
                    sc["is_seed"] = True
                logger.info(f"Stage 2a: Found {len(seed_contacts_verified)} verified seed contacts at {seed_domain}")
            else:
                logger.info(f"Stage 2a: No decision makers found for seed domain {seed_domain}. Continuing.")
        except Exception as seed_err:
            logger.warning(f"Stage 2a: Seed domain people search failed — {seed_err}. Degrading gracefully.")
            seed_contacts_verified = []

        # Stage 2b: People Search across competitor domains (Prospeo -> Hunter fallback)
        all_contacts: list[PersonResult] = []
        raw_prospects_count = 0

        for comp in companies:
            comp_domain = comp["domain"]
            logger.info(f"Stage 2b: Prospecting decision makers at {comp['name']} ({comp_domain})")
            
            # Primary provider (Prospeo)
            domain_contacts = prospeo_provider.search_people(comp_domain)
            
            # Fallback provider (Hunter) if primary returned nothing
            if not domain_contacts:
                logger.info(f"Stage 2b: Primary provider returned 0 for {comp_domain}. Failing over to Hunter.io...")
                domain_contacts = hunter_provider.search_people(comp_domain)

            raw_prospects_count += len(domain_contacts)
            all_contacts.extend(domain_contacts)

        # Stage 3: Verification & Filtering
        filtered_contacts = filter_cxo(all_contacts)
        unique_contacts = deduplicate_contacts(filtered_contacts)
        verified_contacts = resolve_emails(unique_contacts)

        response_payload = {
            "status": status,
            "companies": companies,
            "contacts": verified_contacts,
            "seed_contacts": seed_contacts_verified,
            "metrics": {
                "companies": len(companies),
                "prospects": raw_prospects_count,
                "verified": len(verified_contacts),
                "seed_verified": len(seed_contacts_verified)
            }
        }

        if status == "partial":
            response_payload["warning"] = "Competitor discovery had low confidence for this domain"

        logger.info(f"Pipeline completed: status={status}, companies={len(companies)}, verified_contacts={len(verified_contacts)}")
        return jsonify(response_payload)

    except Exception as e:
        logger.error(f"Pipeline exception: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/send-emails", methods=["POST"])
def send_emails():
    data = request.json or {}
    contacts = data.get("contacts", [])
    seed_domain = data.get("seed_domain", "")
    
    if not contacts or not seed_domain:
        return jsonify({"error": "contacts and seed_domain are required"}), 400

    logger.info(f"Starting outreach dispatch for {len(contacts)} contacts (seed={seed_domain})")
    try:
        results = send_outreach(contacts, seed_domain)
        return jsonify({
            "status": "success",
            "sent": results["sent"],
            "failed": results["failed"]
        })
    except Exception as e:
        logger.error(f"Outreach exception: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
