from fastapi import APIRouter

router = APIRouter(prefix="/outreach", tags=["outreach"])


@router.get("/stub")
async def outreach_stub() -> dict:
    return {
        "status": "planned",
        "features": [
            "Email Sequence",
            "LinkedIn InMail templates",
            "WhatsApp outreach",
            "CRM tracking",
            "Reply-rate analytics",
            "A/B testing",
        ],
    }
