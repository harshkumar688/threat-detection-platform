"""
Analytics Module

Computes metrics from real incident/detection data.
All numbers are derived from actual repository queries — nothing is fabricated.
"""

from .service import AnalyticsService

__all__ = ["AnalyticsService"]
