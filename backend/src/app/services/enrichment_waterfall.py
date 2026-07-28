import logging
import httpx
import dns.resolver
from typing import Optional, Tuple, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

async def check_unipile_profile(provider_id: str, account_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Tier 1: Check Unipile's native user profile for public email/phone.
    """
    if not settings.UNIPILE_API_KEY or not account_id:
        return None, None
        
    url = f"{settings.UNIPILE_BASE_URL.rstrip('/')}/users/{provider_id}"
    headers = {
        "X-API-KEY": settings.UNIPILE_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"account_id": account_id}, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                emails = data.get("emails", [])
                phones = data.get("phone_numbers", [])
                
                email = emails[0].get("email") if emails else None
                # phone_numbers structure varies, try to extract first string
                phone = None
                if phones:
                    if isinstance(phones[0], dict):
                        phone = phones[0].get("number")
                    else:
                        phone = str(phones[0])
                        
                return email, phone
    except Exception as e:
        logger.warning(f"Failed to check Unipile profile for {provider_id}: {e}")
        
    return None, None


async def enrich_email_waterfall(first_name: str, last_name: str, company_domain: str, linkedin_url: str) -> Optional[str]:
    """
    Tier 2: Waterfall email enrichment.
    """
    # 1. Prospeo
    if settings.PROSPEO_API_KEY and linkedin_url:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.prospeo.io/linkedin-email-finder",
                    headers={"X-KEY": settings.PROSPEO_API_KEY},
                    json={"url": linkedin_url},
                    timeout=10.0
                )
                if res.status_code == 200:
                    data = res.json()
                    email = data.get("response", {}).get("email", {}).get("email")
                    if email:
                        logger.info(f"Email found via Prospeo for {linkedin_url}")
                        return email
        except Exception as e:
            logger.warning(f"Prospeo API failed: {e}")

    # 2. Local MX Ping Fallback
    if first_name and last_name and company_domain:
        domain = company_domain.lower().replace(' ', '')
        if not domain.endswith('.com') and '.' not in domain:
            domain += '.com'
            
        permutations = [
            f"{first_name.lower()}@{domain}",
            f"{first_name.lower()}.{last_name.lower()}@{domain}",
            f"{first_name.lower()[0]}{last_name.lower()}@{domain}",
        ]
        
        try:
            # Just do a quick MX check for the domain, actual SMTP ping is too complex for this tier
            answers = dns.resolver.resolve(domain, 'MX')
            if answers:
                # We know the domain receives email. We can optimistically return the most common format.
                logger.info(f"Domain {domain} has valid MX records. Attempting permutation fallback.")
                return permutations[0]
        except Exception as e:
            logger.warning(f"MX lookup failed for {domain}: {e}")

    return None


async def enrich_phone_waterfall(linkedin_url: str) -> Optional[str]:
    """
    Tier 3: Waterfall phone enrichment.
    """
    # 1. Kaspr
    if settings.KASPR_API_KEY and linkedin_url:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.kaspr.io/v1/enrich",
                    headers={"Authorization": f"Bearer {settings.KASPR_API_KEY}"},
                    json={"linkedin_url": linkedin_url},
                    timeout=10.0
                )
                if res.status_code == 200:
                    data = res.json()
                    phones = data.get("phones", [])
                    if phones:
                        logger.info(f"Phone found via Kaspr for {linkedin_url}")
                        return phones[0]
        except Exception as e:
            logger.warning(f"Kaspr API failed: {e}")

    return None
