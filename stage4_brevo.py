import requests
import logging
from config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME

logger = logging.getLogger(__name__)


def send_outreach(contacts, seed_domain):
    """
    Stage 4: Sends personalized outreach email to each contact.

    Args:
        contacts: verified contact list from Stage 3
        seed_domain: original seed (used to personalize copy)
    Returns:
        dict with sent and failed counts
    """
    results = {"sent": 0, "failed": 0}

    for contact in contacts:
        success = _send_single(contact, seed_domain)
        if success:
            results["sent"] += 1
            logger.info(f"Stage 4: Sent to {contact['name']} "
                        f"at {contact['email']}")
        else:
            results["failed"] += 1
            logger.warning(f"Stage 4: Failed for {contact['name']}")

    logger.info(f"Stage 4: Done. {results['sent']} sent, "
                f"{results['failed']} failed")
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

    subject = f"Quick question — {contact.get('company', 'your team')}"

    # Personalized email body — this is yours to own
    body = f"""Hi {contact.get('name', 'there').split()[0]},

Came across {contact.get('company', 'your company')} while researching teams doing interesting work in fintech infrastructure.

We're building tools that automate the exact kind of outreach pipeline you're reading right now — sourcing, prospecting, and emailing in one shot, zero manual steps.

Thought it might be relevant given what {contact.get('company', 'your team')} is working on.

Worth a 15-minute call this week?

Best,
{SENDER_NAME}
ajay@reachmatrix.me
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
        response = requests.post(url, json=payload,
                                 headers=headers, timeout=10)

        if response.status_code in [200, 201]:
            return True
        else:
            logger.error(f"Stage 4: Brevo error {response.status_code} "
                         f"— {response.text}")
            return False

    except Exception as e:
        logger.error(f"Stage 4: Exception sending to "
                     f"{contact.get('email')} — {e}")
        return False
