"""
Threat-Risk Scoring Engine

Computes an engineering prioritization score (0–100) based on
observable detection evidence. This is NOT a prediction of intent
or criminal behavior — it is a prioritization tool that helps
human operators focus attention on the most urgent situations.

Scoring factors:
- Weapon class severity (rifle > handgun > knife)
- Detection confidence (higher = more certain)
- Persistence across frames (longer = more real)
- Number of weapons detected
- Location/camera sensitivity multiplier

All parameters are fully configurable. The output includes an
explainable breakdown showing exactly how the score was computed.

Usage:
    from detection.src.scoring import RiskScorer, ScoringConfig

    config = ScoringConfig()
    scorer = RiskScorer(config)

    result = scorer.score(
        weapon_class="handgun",
        avg_confidence=0.82,
        frames_confirmed=10,
        weapon_count=1,
        location_id="lobby_entrance",
    )
    print(f"Score: {result.risk_score}, Level: {result.risk_level}")
    print(result.explanation)
"""

from .config import ScoringConfig
from .models import RiskLevel, ScoringResult
from .scorer import RiskScorer

__all__ = [
    "RiskScorer",
    "ScoringConfig",
    "RiskLevel",
    "ScoringResult",
]
