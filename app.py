from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging
import os

from stage1_discover import find_lookalikes
from stage2_prospeo import find_decision_makers
from stage3_Verify import resolve_emails
from stage4_brevo import send_outreach
from utils import deduplicate_contacts, filter_cxo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/run-pipeline", methods=["POST"])
def run_pipeline():
    data = request.json
    seed_domain = data.get("domain")
    
    if not seed_domain:
        return jsonify({"error": "domain is required"}), 400

    logger.info(f"Starting pipeline for {seed_domain}")
    
    try:
        # Stage 1: Discover Lookalikes
        domains = find_lookalikes(seed_domain)
        if not domains:
            return jsonify({"error": "Stage 1 failed: No lookalike companies found"}), 500
            
        # Stage 2: Prospect Decision Makers
        contacts = find_decision_makers(domains)
        if not contacts:
            return jsonify({"error": "Stage 2 failed: No contacts found"}), 500
            
        contacts = filter_cxo(contacts)
        contacts = deduplicate_contacts(contacts)
        
        # Stage 3: Verify Emails
        verified = resolve_emails(contacts)
        
        return jsonify({
            "status": "success",
            "contacts": verified,
            "metrics": {
                "companies": len(domains),
                "prospects": len(contacts),
                "verified": len(verified)
            }
        })
    except Exception as e:
        import traceback
        logger.error(f"Pipeline error: {e}")
        return jsonify({
            "error": True,
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route("/api/send-emails", methods=["POST"])
def send_emails():
    data = request.json
    contacts = data.get("contacts", [])
    seed_domain = data.get("seed_domain", "")
    
    if not contacts or not seed_domain:
        return jsonify({"error": "contacts and seed_domain are required"}), 400

    logger.info(f"Starting outreach to {len(contacts)} contacts")
    try:
        results = send_outreach(contacts, seed_domain)
        return jsonify({
            "status": "success",
            "sent": results["sent"],
            "failed": results["failed"]
        })
    except Exception as e:
        logger.error(f"Outreach error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
