from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")

# Routers for auth, freelancers, work hosts, organisations, labels, search,
# ratings and reports are added in later phases (see docs/specification/08-delivery-plan.md).
