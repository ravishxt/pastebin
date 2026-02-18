from __future__ import annotations

import uuid
from http import HTTPStatus

from flask import Blueprint, current_app, request

from app.api.schemas import HealthResponse, PasteCreateRequest
from app.services.paste_service import (
    InvalidPasteParameters,
    PasteNotFoundError,
    PasteUnavailableError,
)

from app.db import SessionLocal
from app.services.paste_service import PasteService

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health() -> tuple[dict, int]:
    """Simple health check endpoint."""

    body = HealthResponse().model_dump()
    return body, HTTPStatus.OK


@api_bp.route("/pastes", methods=["POST"])
def create_paste() -> tuple[dict, int]:
    """
    Create a new paste.

    Validation is handled by Pydantic; business rules by the service layer.
    """
    try:
        payload = PasteCreateRequest.model_validate(request.get_json() or {})
    except Exception as exc:  # Pydantic validation error
        return {"error": "Invalid request body", "details": str(exc)}, HTTPStatus.BAD_REQUEST

    paste_service = PasteService(session_factory=SessionLocal)
    try:
        dto = paste_service.create_paste(
            content=payload.content,
            max_views=payload.max_views,
            expires_at=payload.expires_at,
            password_hash=payload.password_hash,
        )
    except InvalidPasteParameters as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST

    return dto, HTTPStatus.CREATED


@api_bp.route("/pastes/<paste_id>", methods=["GET"])
def get_paste(paste_id: str) -> tuple[dict, int]:
    """
    Retrieve (view) a paste by id.

    All view/expiry rules are contained in the service layer.
    """
    try:
        uid = uuid.UUID(paste_id)
    except ValueError:
        return {"error": "Invalid paste id"}, HTTPStatus.BAD_REQUEST

    paste_service = PasteService(session_factory=SessionLocal)
    try:
        dto = paste_service.retrieve_paste_for_view(
            paste_id=uid,
            ip_address=request.remote_addr,
        )
    except PasteNotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND
    except PasteUnavailableError as exc:
        # 410 Gone indicates the resource used to exist but is no longer available.
        return {"error": str(exc)}, HTTPStatus.GONE

    return dto, HTTPStatus.OK


@api_bp.route("/pastes/<paste_id>", methods=["DELETE"])
def delete_paste(paste_id: str) -> tuple[dict, int]:
    """
    Logically delete a paste by transitioning it to the DELETED state.

    The actual transition rules are enforced by the domain state machine,
    invoked indirectly through the service layer.
    """
    try:
        uid = uuid.UUID(paste_id)
    except ValueError:
        return {"error": "Invalid paste id"}, HTTPStatus.BAD_REQUEST

    paste_service = PasteService(session_factory=SessionLocal)
    try:
        dto = paste_service.delete_paste(uid)
    except PasteNotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND
    except PasteUnavailableError as exc:
        return {"error": str(exc)}, HTTPStatus.CONFLICT

    return dto, HTTPStatus.OK

