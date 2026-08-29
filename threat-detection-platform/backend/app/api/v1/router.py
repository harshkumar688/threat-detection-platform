"""
API v1 Router Aggregation

Combines all domain routers under the /api/v1 prefix.
"""

from fastapi import APIRouter

from . import alerts, analytics, auth, cameras, detections, evidence, incidents, locations, users

api_router = APIRouter(prefix="/api/v1")

# Register all domain routers
# NOTE: locations must be imported before cameras is used at request time
# (cameras.py lazily reads app.api.v1.locations._location_repo), but Python
# module import order here doesn't matter for that — the reference is
# resolved lazily inside _build_camera_service(). Registration order below
# only affects route matching, not construction order.
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(locations.router)
api_router.include_router(cameras.router)
api_router.include_router(incidents.router)
api_router.include_router(detections.router)
api_router.include_router(evidence.router)
api_router.include_router(alerts.router)
api_router.include_router(analytics.router)
