import logging

logger = logging.getLogger(__name__)


def resolve_emails(contacts):
    """
    Stage 3: Filters contacts to only those where Prospeo
    already returned a verified email.
    
    Eazyreach is no longer needed — Prospeo's enrich-person
    API already returns verified work emails directly.
    
    Args:
        contacts: list of contact dicts from Stage 2
    Returns:
        same list but only contacts with non-empty email
    """
    verified = []

    for contact in contacts:
        email = contact.get("email", "").strip()

        if email and "@" in email:
            verified.append(contact)
            logger.info(f"Stage 3: Verified {contact.get('name')} "
                        f"→ {email}")
        else:
            logger.warning(f"Stage 3: No email for "
                           f"{contact.get('name')} — dropping")

    logger.info(f"Stage 3: {len(verified)}/{len(contacts)} "
                f"contacts have verified emails")
    return verified