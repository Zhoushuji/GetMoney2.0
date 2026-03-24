import asyncio
from bs4 import BeautifulSoup

from app.services.contact.intelligence import ContactIntelligenceService
from app.services.search.company_extractor import CompanyNameExtractor
from app.services.search.social_links import extract_facebook, extract_linkedin_company


def test_company_name_extractor_prefers_meta_and_cleans_title():
    soup = BeautifulSoup(
        '<html><head><meta property="og:site_name" content="Best Apogee Agrotech - 20 Lakh INR"></head></html>',
        'html.parser',
    )
    item = {"title": "Buy Cheap Valves | Example"}
    extracted = asyncio.run(CompanyNameExtractor().extract(item, 'https://www.apogeeagrotech.com', soup))
    assert extracted.value == 'Apogee Agrotech'
    assert extracted.source == 'og:site_name'


def test_social_link_filters_keep_company_pages_only():
    assert extract_facebook('https://www.facebook.com/sharer.php?u=x https://www.facebook.com/apogee.agro') == 'https://www.facebook.com/apogee.agro'
    assert extract_linkedin_company('https://www.linkedin.com/in/person https://www.linkedin.com/company/apogee-agro/') == 'https://www.linkedin.com/company/apogee-agro'
    assert extract_linkedin_company('https://www.linkedin.com/in/ks-agrotech-private-limited-914903195/') == 'https://www.linkedin.com/in/ks-agrotech-private-limited-914903195'


def test_company_name_extractor_ignores_placeholder_and_prefers_domain_brand_for_generic_titles():
    soup = BeautifulSoup('<html><head><title>Future home of something quite cool.</title></head></html>', 'html.parser')
    item = {"title": "Laser Land Leveller Manufacturers - TradeIndia"}
    extracted = asyncio.run(CompanyNameExtractor().extract(item, 'https://www.tradeindia.com', soup))
    assert extracted.value == 'Tradeindia'


def test_contact_service_rejects_generic_personal_email_and_keeps_potential_contacts():
    service = ContactIntelligenceService()
    soup = BeautifulSoup(
        '''
        <html><body>
        <a href="https://www.linkedin.com/in/jane-doe">Jane Doe</a>
        <div>Jane Doe Chief Executive Officer Apogee Agrotech</div>
        <div>WhatsApp +91 98765 43210</div>
        <div>info@apogeeagrotech.com jane.doe@apogeeagrotech.com</div>
        </body></html>
        ''',
        'html.parser',
    )
    lead = type('Lead', (), {'id': __import__('uuid').uuid4(), 'website': 'https://apogeeagrotech.com', 'company_name': 'Apogee Agrotech'})
    people = service._verify_people(service._extract_linkedin_people(soup, lead.company_name), lead.company_name)
    potentials = service._extract_potential_contacts(lead.website, soup)
    contact = service._build_contact(lead, people, potentials)
    assert contact is not None
    assert contact.personal_email == 'jane.doe@apogeeagrotech.com'
    assert contact.whatsapp == '+919876543210'


def test_contact_service_safe_whatsapp_access_with_empty_list():
    service = ContactIntelligenceService()
    soup = BeautifulSoup(
        '''
        <html><body>
        <a href="https://www.linkedin.com/in/jane-doe">Jane Doe</a>
        <div>Jane Doe Chief Executive Officer Apogee Agrotech</div>
        <div>jane.doe@apogeeagrotech.com</div>
        </body></html>
        ''',
        'html.parser',
    )
    lead = type('Lead', (), {'id': __import__('uuid').uuid4(), 'website': 'https://apogeeagrotech.com', 'company_name': 'Apogee Agrotech'})
    people = service._verify_people(service._extract_linkedin_people(soup, lead.company_name), lead.company_name)
    potentials = service._extract_potential_contacts(lead.website, soup)
    contact = service._build_contact(lead, people, potentials)
    assert contact is not None
    assert contact.whatsapp is None


def test_potential_contacts_excludes_sales_email_from_general_contacts():
    service = ContactIntelligenceService()
    soup = BeautifulSoup(
        "<html><body>sales@apogeeagrotech.com info@apogeeagrotech.com</body></html>",
        "html.parser",
    )
    extracted = service._extract_potential_contacts("https://apogeeagrotech.com", soup)
    assert "sales@apogeeagrotech.com" not in extracted.get("generic_emails", [])
    assert "email:sales@apogeeagrotech.com" not in extracted.get("all", [])
