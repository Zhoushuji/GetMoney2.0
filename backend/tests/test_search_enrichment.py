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
    contact = service._build_contact(lead, people, soup)
    assert contact is not None
    assert contact.personal_email == 'jane.doe@apogeeagrotech.com'
    assert 'email:info@apogeeagrotech.com' in (contact.potential_contacts or {}).get('items', [])
    assert contact.whatsapp == '+919876543210'
