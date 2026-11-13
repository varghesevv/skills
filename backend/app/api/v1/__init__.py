from fastapi import APIRouter

from app.api.v1 import (
    admin,
    app_info,
    auth,
    churches,
    freelancers,
    group_invitations,
    labels,
    me,
    organisations,
    ratings,
    reports,
    search,
    verifier,
    vouching,
    workhosts,
)

api_v1_router = APIRouter(prefix="/api/v1")
ROUTERS = (
    app_info,
    auth,
    churches,
    group_invitations,
    me,
    admin,
    freelancers,
    workhosts,
    organisations,
    labels,
    ratings,
    search,
    reports,
    verifier,
    vouching,
)
for module in ROUTERS:
    api_v1_router.include_router(module.router)
