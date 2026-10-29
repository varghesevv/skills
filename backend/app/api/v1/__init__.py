from fastapi import APIRouter

from app.api.v1 import (
    admin,
    app_info,
    auth,
    freelancers,
    labels,
    me,
    organisations,
    ratings,
    reports,
    search,
    workhosts,
)

api_v1_router = APIRouter(prefix="/api/v1")
ROUTERS = (
    app_info,
    auth,
    me,
    admin,
    freelancers,
    workhosts,
    organisations,
    labels,
    ratings,
    search,
    reports,
)
for module in ROUTERS:
    api_v1_router.include_router(module.router)
