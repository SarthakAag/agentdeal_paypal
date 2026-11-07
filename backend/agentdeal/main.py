
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

# Load environment variables before application configuration.
from backend.agentdeal import paypal_client  # noqa: F401

from backend.agentdeal.assist import router as assist_router
from backend.agentdeal.auth import router as auth_router
from backend.agentdeal.db import init_db
from backend.agentdeal.marketplace import router as marketplace_router
from backend.agentdeal.messages import (
    router as messages_router,
    init_messages_table,
)
from backend.agentdeal.negotiation import Deal, negotiate
from backend.agentdeal.notifications import router as notifications_router
from backend.agentdeal.payments import router as payments_router
from backend.agentdeal.views import router as views_router


# --------------------------------------------------
# Session configuration
# --------------------------------------------------

_secret = os.getenv("SESSION_SECRET")

if not _secret:
    if os.getenv("DEMO_MODE") == "1":
        _secret = "dev-only-change-me"
    else:
        raise RuntimeError(
            "Set SESSION_SECRET in environment variables"
        )


# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="AgentDeal API",
    description=(
        "AI agents negotiate deals; PayPal holds, "
        "captures, voids and refunds the money"
    ),
    version="0.9.0",
)


# --------------------------------------------------
# CORS configuration
# --------------------------------------------------

frontend_url = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173"
).rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

init_db()

# Creates the buyer-seller chat table.
init_messages_table()


# --------------------------------------------------
# Session middleware
# --------------------------------------------------

app.add_middleware(
    SessionMiddleware,
    secret_key=_secret,
    same_site="none" if frontend_url.startswith("https://") else "lax",
    https_only=os.getenv("HTTPS_ONLY") == "1",
)


# --------------------------------------------------
# API router registration
# --------------------------------------------------

app.include_router(views_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(marketplace_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(assist_router, prefix="/api")

# Buyer-seller conversation endpoints.
app.include_router(messages_router, prefix="/api")

# Notification endpoints.
app.include_router(notifications_router, prefix="/api")


# --------------------------------------------------
# Original baseline negotiation endpoint
# --------------------------------------------------

class NegotiationRequest(BaseModel):
    product: str = Field(min_length=1, max_length=120)
    buyer_budget: float = Field(gt=0)
    seller_minimum: float = Field(gt=0)
    buyer_offer: float = Field(gt=0)
    seller_offer: float = Field(gt=0)
    delivery_days: int = Field(default=5, ge=1, le=365)
    max_delivery_days: int = Field(default=7, ge=1, le=365)
    max_rounds: int = Field(default=6, ge=1, le=20)


@app.post("/api/negotiate")
def start_negotiation(request: NegotiationRequest):
    """
    Original fixed-formula negotiation endpoint.
    Kept as a simple baseline alongside the marketplace.
    """

    if request.seller_minimum > request.seller_offer:
        raise HTTPException(
            422,
            "Seller opening offer cannot be below seller minimum."
        )

    if request.buyer_offer > request.buyer_budget:
        raise HTTPException(
            422,
            "Buyer opening offer cannot exceed buyer budget."
        )

    result = negotiate(Deal(**request.model_dump()))

    return {
        "product": result.product,
        "status": result.status,
        "agreed_price": result.agreed_price,
        "rounds": result.round_number,
        "history": result.history,
    }


# --------------------------------------------------
# React production build (optional)
# --------------------------------------------------

DIST = Path("frontend/dist")

if DIST.exists():

    app.mount(
        "/assets",
        StaticFiles(directory=DIST / "assets"),
        name="assets",
    )

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):

        # Do not let unknown API routes return index.html.
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")

        file_path = (DIST / path).resolve()

        if (
            path
            and file_path.is_file()
            and file_path.is_relative_to(DIST.resolve())
        ):
            return FileResponse(file_path)

        return FileResponse(DIST / "index.html")
