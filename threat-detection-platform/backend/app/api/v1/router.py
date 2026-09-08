"""
API v1 Router Aggregation

Combines all domain routers under the /api/v1 prefix.
"""

from fastapi import APIRouter

from . import alerts, analytics, auth, cameras, detections, evidence, incidents, locations, streams, users

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(locations.router)
api_router.include_router(cameras.router)
api_router.include_router(incidents.router)
api_router.include_router(detections.router)
api_router.include_router(evidence.router)
api_router.include_router(alerts.router)
api_router.include_router(analytics.router)
api_router.include_router(streams.router)
