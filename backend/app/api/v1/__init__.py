from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_invitations,
    app_info,
    auth,
    churches,
    freelancers,
    group_invitations,
    group_requests,
    home_groups,
    labels,
    me,
    organisations,
    owner,
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
    admin_invitations,
    auth,
    churches,
    group_invitations,
    group_requests,
    home_groups,
    me,
    owner,
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
