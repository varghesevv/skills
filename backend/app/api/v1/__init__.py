from fastapi import APIRouter

from app.api.v1 import admin, auth, freelancers, labels, me, organisations, ratings, workhosts

api_v1_router = APIRouter(prefix="/api/v1")
for module in (auth, me, admin, freelancers, workhosts, organisations, labels, ratings):
    api_v1_router.include_router(module.router)

# Search and reports are added in later phases (see docs/specification/08-delivery-plan.md).
