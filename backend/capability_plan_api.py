"""Authenticated plan-review API; intentionally has no execution endpoint."""
import hmac
import logging

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from capability_plan_store import CapabilityPlanStore, PlanConflict

logger = logging.getLogger(__name__)


def create_plan_router(store: CapabilityPlanStore, token_getter) -> APIRouter:
    def authenticate(authorization: str = Header(default="")):
        token = token_getter()
        if not token:
            raise HTTPException(503, "Plan API requires FRIDAY_SERVER_TOKEN")
        if not hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
            raise HTTPException(401, "Authentication required")

    router = APIRouter(prefix="/api/capability-plans", dependencies=[Depends(authenticate)])

    def invoke(callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except FileNotFoundError:
            raise HTTPException(404, "Plan not found")
        except PlanConflict as exc:
            raise HTTPException(409, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except OSError:
            logger.exception("Plan storage failed")
            raise HTTPException(503, "Plan storage unavailable")

    @router.post("", status_code=201)
    def create_plan(plan: dict = Body(...)):
        return invoke(store.create, plan)

    @router.get("/{plan_id}")
    def get_plan(plan_id: str):
        return invoke(store.get, plan_id)

    @router.post("/{plan_id}/{action}")
    def transition_plan(plan_id: str, action: str, payload: dict = Body(...)):
        return invoke(store.transition, plan_id, payload.get("version"), action,
                      plan=payload.get("plan"), content_hash=payload.get("content_hash"))

    return router
