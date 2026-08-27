from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

import os
import logging
import asyncio
import resend
import uuid

from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List
from datetime import datetime, timezone


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ==========================================
# MONGODB CONNECTION
# ==========================================

mongo_url = os.getenv("MONGO_URL")
db_name = os.getenv("DB_NAME")

if not mongo_url:
    raise RuntimeError(
        f"MONGO_URL was not found. Make sure this file exists:\n{ENV_FILE}"
    )

if not db_name:
    db_name = "mouli_portfolio"

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]


# ==========================================
# FASTAPI APP
# ==========================================

app = FastAPI()

api_router = APIRouter(prefix="/api")


# ==========================================
# MODELS
# ==========================================

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class StatusCheckCreate(BaseModel):
    client_name: str


class ContactMessage(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=10, max_length=5000)


# ==========================================
# ROUTES
# ==========================================

@api_router.get("/")
async def root():
    return {
        "message": "Mouli portfolio API",
        "status": "running"
    }


# ==========================================
# CONTACT FORM
# ==========================================

@api_router.post("/contact")
async def send_contact_message(payload: ContactMessage):

    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("SENDER_EMAIL")

    if not api_key or not sender:
        raise HTTPException(
            status_code=503,
            detail="Contact delivery is not configured yet."
        )

    resend.api_key = api_key

    email_params = {
        "from": sender,
        "to": ["vadapallimouli2008@gmail.com"],
        "reply_to": [str(payload.email)],
        "subject": f"Portfolio message: {payload.subject}",
        "html": (
            f"<h2>New message from {payload.name}</h2>"
            f"<p><strong>Reply to:</strong> {payload.email}</p>"
            f"<p><strong>Subject:</strong> {payload.subject}</p>"
            f"<p>{payload.message.replace(chr(10), '<br>')}</p>"
        ),
    }

    try:
        result = await asyncio.to_thread(
            resend.Emails.send,
            email_params
        )

        return {
            "status": "success",
            "message": "Your message was delivered.",
            "email_id": result.get("id")
        }

    except Exception as exc:
        logger.exception("Resend delivery failed")

        raise HTTPException(
            status_code=502,
            detail=(
                "Message delivery failed. "
                "Please email Mouli directly."
            )
        ) from exc


# ==========================================
# STATUS CHECK ROUTES
# ==========================================

@api_router.post(
    "/status",
    response_model=StatusCheck
)
async def create_status_check(input: StatusCheckCreate):

    status_dict = input.model_dump()

    status_obj = StatusCheck(
        **status_dict
    )

    doc = status_obj.model_dump()

    doc["timestamp"] = (
        doc["timestamp"].isoformat()
    )

    await db.status_checks.insert_one(doc)

    return status_obj


@api_router.get(
    "/status",
    response_model=List[StatusCheck]
)
async def get_status_checks():

    status_checks = await db.status_checks.find(
        {},
        {"_id": 0}
    ).to_list(1000)

    for check in status_checks:

        if isinstance(
            check.get("timestamp"),
            str
        ):
            check["timestamp"] = (
                datetime.fromisoformat(
                    check["timestamp"]
                )
            )

    return status_checks


# ==========================================
# INCLUDE API ROUTER
# ==========================================

app.include_router(api_router)


# ==========================================
# CORS
# ==========================================

cors_origins = os.getenv(
    "CORS_ORIGINS",
    "*"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# SHUTDOWN
# ==========================================

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()