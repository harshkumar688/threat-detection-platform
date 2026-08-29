"""
Scoring Data Models

Defines risk levels and scoring result structures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class RiskLevel(str, Enum):
    """Risk classification levels."""

    LOW = "LOW"
    """Score 0–30: Detection exists but minimal concern."""

    MEDIUM = "MEDIUM"
    """Score 31–55: Warrants operator attention."""

    HIGH = "HIGH"
    """Score 56–80: Likely real threat, prioritize response."""

    CRITICAL = "CRITICAL"
    """Score 81–100: Maximum urgency, immediate response needed."""


@dataclass
class ScoreComponent:
    """A single component of the risk score breakdown."""

    factor_name: str       # Human-readable factor name
    raw_value: float       # Raw input value (e.g., confidence=0.82)
    normalized_value: float  # Normalized to 0–100 scale
    weight: float          # Weight applied (0.0–1.0)
    weighted_score: float  # normalized_value * weight (contribution to total)
    description: str = ""  # Explanation of this component

    def to_dict(self) -> dict:
        return {
            "factor": self.factor_name,
            "raw_value": round(self.raw_value, 4),
            "normalized": round(self.normalized_value, 2),
            "weight": round(self.weight, 3),
            "contribution": round(self.weighted_score, 2),
            "description": self.description,
        }


@dataclass
class ScoringResult:
    """
    Complete scoring output with explanation.

    This is the public interface consumed by incident management.
    """

    risk_score: float            # Final score (0–100)
    risk_level: RiskLevel        # Classified level
    components: List[ScoreComponent]  # Breakdown of how score was computed
    location_multiplier: float = 1.0  # Applied multiplier
    pre_multiplier_score: float = 0.0  # Score before location multiplier

    # Input context (for audit/logging)
    weapon_class: str = ""
    avg_confidence: float = 0.0
    frames_confirmed: int = 0
    weapon_count: int = 0
    location_id: str = ""

    @property
    def explanation(self) -> str:
        """Human-readable explanation of the score."""
        lines = [
            f"Risk Score: {self.risk_score:.1f}/100 ({self.risk_level.value})",
            f"",
            f"Breakdown:",
        ]
        for comp in self.components:
            lines.append(
                f"  {comp.factor_name}: "
                f"{comp.normalized_value:.1f}/100 × {comp.weight:.2f} = "
                f"{comp.weighted_score:.1f} points"
                f"  ({comp.description})"
            )

        if self.location_multiplier != 1.0:
            lines.append(f"")
            lines.append(
                f"  Location multiplier: ×{self.location_multiplier:.2f} "
                f"(pre-multiplier: {self.pre_multiplier_score:.1f})"
            )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "risk_score": round(self.risk_score, 2),
            "risk_level": self.risk_level.value,
            "components": [c.to_dict() for c in self.components],
            "location_multiplier": round(self.location_multiplier, 2),
            "pre_multiplier_score": round(self.pre_multiplier_score, 2),
            "inputs": {
                "weapon_class": self.weapon_class,
                "avg_confidence": round(self.avg_confidence, 4),
                "frames_confirmed": self.frames_confirmed,
                "weapon_count": self.weapon_count,
                "location_id": self.location_id,
            },
        }
