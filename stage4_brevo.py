import requests
import logging
from config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME, DEMO_MODE

logger = logging.getLogger(__name__)


def send_outreach(contacts, seed_domain):
    """
    Stage 4: Sends personalized outreach email to each contact.

    Args:
        contacts: verified contact list from Stage 3/pipeline
        seed_domain: original seed (used to personalize copy)
    Returns:
        dict with sent and failed counts
    """
    if DEMO_MODE:
        logger.info("Stage 4: DEMO_MODE=True — prepending demo contact for live email delivery check.")
        demo_contact = {
            "name": "Ajay D",
            "title": "Builder",
            "company": "ReachMatrix",
            "email": "ajajayd96@gmail.com",
            "domain": "reachmatrix.me"
        }
        contacts = [demo_contact] + list(contacts)[:3]
    else:
        contacts = list(contacts)[:4]  # limit batch size per run
    
    results = {"sent": 0, "failed": 0}

    for contact in contacts:
        success = _send_single(contact, seed_domain)
        if success:
            results["sent"] += 1
            logger.info(f"Stage 4: Sent to {contact['name']} at {contact['email']}")
        else:
            results["failed"] += 1
            logger.warning(f"Stage 4: Failed for {contact['name']} at {contact.get('email')}")

    logger.info(f"Stage 4: Done. {results['sent']} sent, {results['failed']} failed")
    return results


def _send_single(contact, seed_domain):
    """
    Sends one email via Brevo transactional API.
    Personalized with contact's name and company.
    """
    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY
    }

    subject = f"Automating outreach for {contact.get('company', 'your team')}"

    body = f"""Hi {contact.get('name', 'there').split()[0]},

I came across {contact.get('company', 'your company')} while building an automated outreach pipeline — and thought this might be relevant.

ReachMatrix finds companies similar to your best customers, identifies their decision makers, verifies contact details, and sends personalised outreach automatically. One domain in, emails out — zero manual steps.

Built this in 3 days as part of a project. Happy to show you how it works in 15 minutes.

Worth a quick call this week?

Best,
Ajay D
ajay@reachmatrix.me
reachmatrix.me
"""

    payload = {
        "sender": {
            "name": SENDER_NAME,
            "email": SENDER_EMAIL
        },
        "to": [
            {
                "email": contact.get("email"),
                "name": contact.get("name", "")
            }
        ],
        "subject": subject,
        "textContent": body
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code in [200, 201]:
            return True
        else:
            logger.error(f"Stage 4: Brevo error {response.status_code} — {response.text}")
            return False

    except Exception as e:
        logger.error(f"Stage 4: Exception sending to {contact.get('email')} — {e}")
        return False
