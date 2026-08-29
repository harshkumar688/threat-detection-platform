"""
Risk Scorer

Computes a risk prioritization score from observable detection evidence.
All logic is transparent and configurable — no hidden rules.

This is an engineering tool for prioritizing operator attention,
NOT a prediction of criminal intent.
"""

from ..logger import get_logger
from .config import ScoringConfig
from .models import RiskLevel, ScoreComponent, ScoringResult

logger = get_logger(__name__)


class RiskScorer:
    """
    Configurable risk scoring engine.

    Usage:
        config = ScoringConfig()
        scorer = RiskScorer(config)

        result = scorer.score(
            weapon_class="handgun",
            avg_confidence=0.82,
            frames_confirmed=10,
            weapon_count=1,
            location_id="lobby",
        )
    """

    def __init__(self, config: ScoringConfig = None):
        """
        Initialize scorer with configuration.

        Args:
            config: Scoring configuration. Uses defaults if None.
        """
        self.config = config or ScoringConfig()

    def score(
        self,
        weapon_class: str,
        avg_confidence: float,
        frames_confirmed: int,
        weapon_count: int = 1,
        location_id: str = "",
    ) -> ScoringResult:
        """
        Compute risk score from detection evidence.

        Args:
            weapon_class: Detected weapon class name (e.g., "handgun", "rifle").
            avg_confidence: Average detection confidence (0.0–1.0).
            frames_confirmed: Number of frames the weapon has been confirmed.
            weapon_count: Number of distinct weapons currently detected.
            location_id: Camera/location identifier for multiplier lookup.

        Returns:
            ScoringResult with score, level, and full explanation.
        """
        components = []

        # ─── Factor 1: Weapon Severity ───────────────────────────────────────
        severity_raw = self._get_weapon_severity(weapon_class)
        severity_component = ScoreComponent(
            factor_name="Weapon Severity",
            raw_value=severity_raw,
            normalized_value=severity_raw,  # Already 0–100
            weight=self.config.weight_weapon_severity,
            weighted_score=severity_raw * self.config.weight_weapon_severity,
            description=f"{weapon_class} → {severity_raw:.0f}/100",
        )
        components.append(severity_component)

        # ─── Factor 2: Detection Confidence ──────────────────────────────────
        confidence_normalized = _clamp(avg_confidence * 100.0, 0.0, 100.0)
        confidence_component = ScoreComponent(
            factor_name="Detection Confidence",
            raw_value=avg_confidence,
            normalized_value=confidence_normalized,
            weight=self.config.weight_confidence,
            weighted_score=confidence_normalized * self.config.weight_confidence,
            description=f"avg_confidence={avg_confidence:.3f} → {confidence_normalized:.1f}/100",
        )
        components.append(confidence_component)

        # ─── Factor 3: Persistence ───────────────────────────────────────────
        persistence_ratio = min(frames_confirmed / self.config.persistence_max_frames, 1.0)
        persistence_normalized = persistence_ratio * 100.0
        persistence_component = ScoreComponent(
            factor_name="Persistence",
            raw_value=float(frames_confirmed),
            normalized_value=persistence_normalized,
            weight=self.config.weight_persistence,
            weighted_score=persistence_normalized * self.config.weight_persistence,
            description=(
                f"{frames_confirmed} frames / {self.config.persistence_max_frames} max "
                f"→ {persistence_normalized:.1f}/100"
            ),
        )
        components.append(persistence_component)

        # ─── Factor 4: Weapon Count ──────────────────────────────────────────
        count_ratio = min(weapon_count / self.config.weapon_count_max, 1.0)
        count_normalized = count_ratio * 100.0
        count_component = ScoreComponent(
            factor_name="Weapon Count",
            raw_value=float(weapon_count),
            normalized_value=count_normalized,
            weight=self.config.weight_weapon_count,
            weighted_score=count_normalized * self.config.weight_weapon_count,
            description=(
                f"{weapon_count} weapon(s) / {self.config.weapon_count_max} max "
                f"→ {count_normalized:.1f}/100"
            ),
        )
        components.append(count_component)

        # ─── Factor 5: Location Base Score ───────────────────────────────────
        # Location contributes a base 100 (full marks) multiplied by its weight.
        # The actual location multiplier is applied post-sum.
        location_base = 100.0  # Locations always contribute full base
        location_component = ScoreComponent(
            factor_name="Location Base",
            raw_value=1.0,
            normalized_value=location_base,
            weight=self.config.weight_location,
            weighted_score=location_base * self.config.weight_location,
            description="Base contribution (multiplier applied post-sum)",
        )
        components.append(location_component)

        # ─── Sum weighted components ─────────────────────────────────────────
        pre_multiplier_score = sum(c.weighted_score for c in components)

        # ─── Apply location multiplier ───────────────────────────────────────
        location_mult = self._get_location_multiplier(location_id)
        final_score = _clamp(pre_multiplier_score * location_mult, 0.0, 100.0)

        # ─── Classify risk level ─────────────────────────────────────────────
        risk_level = self._classify_level(final_score)

        result = ScoringResult(
            risk_score=final_score,
            risk_level=risk_level,
            components=components,
            location_multiplier=location_mult,
            pre_multiplier_score=pre_multiplier_score,
            weapon_class=weapon_class,
            avg_confidence=avg_confidence,
            frames_confirmed=frames_confirmed,
            weapon_count=weapon_count,
            location_id=location_id,
        )

        logger.debug(
            "risk_scored",
            weapon=weapon_class,
            score=round(final_score, 1),
            level=risk_level.value,
            confidence=round(avg_confidence, 3),
            frames=frames_confirmed,
            weapons=weapon_count,
            location=location_id or "default",
        )

        return result

    def _get_weapon_severity(self, weapon_class: str) -> float:
        """Look up weapon severity from config, with fallback to default."""
        return self.config.weapon_severity_scores.get(
            weapon_class.lower(),
            self.config.default_weapon_severity,
        )

    def _get_location_multiplier(self, location_id: str) -> float:
        """Look up location multiplier from config, with fallback to default."""
        if not location_id:
            return self.config.default_location_multiplier
        return self.config.location_multipliers.get(
            location_id,
            self.config.default_location_multiplier,
        )

    def _classify_level(self, score: float) -> RiskLevel:
        """Map a numeric score to a risk level using configured thresholds."""
        if score <= self.config.threshold_low_max:
            return RiskLevel.LOW
        elif score <= self.config.threshold_medium_max:
            return RiskLevel.MEDIUM
        elif score <= self.config.threshold_high_max:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def get_info(self) -> dict:
        """Get scorer configuration summary."""
        return {
            "weights": {
                "weapon_severity": self.config.weight_weapon_severity,
                "confidence": self.config.weight_confidence,
                "persistence": self.config.weight_persistence,
                "weapon_count": self.config.weight_weapon_count,
                "location": self.config.weight_location,
            },
            "thresholds": {
                "LOW": f"0–{self.config.threshold_low_max}",
                "MEDIUM": f"{self.config.threshold_low_max}–{self.config.threshold_medium_max}",
                "HIGH": f"{self.config.threshold_medium_max}–{self.config.threshold_high_max}",
                "CRITICAL": f"{self.config.threshold_high_max}–100",
            },
            "weapon_severities": self.config.weapon_severity_scores,
            "location_multipliers": self.config.location_multipliers,
            "persistence_max_frames": self.config.persistence_max_frames,
            "weapon_count_max": self.config.weapon_count_max,
        }


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to [min_val, max_val]."""
    return max(min_val, min(value, max_val))
