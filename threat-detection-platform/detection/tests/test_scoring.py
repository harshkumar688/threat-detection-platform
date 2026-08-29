"""
Unit tests for the threat-risk scoring engine.

Tests:
- Score computation correctness
- Risk level classification
- Boundary conditions
- Configuration impact
- Explainability
- Edge cases
"""

import pytest

from src.scoring import RiskScorer, ScoringConfig, RiskLevel, ScoringResult


# =============================================================================
# Basic Scoring Tests
# =============================================================================

class TestBasicScoring:
    """Tests for basic score computation."""

    def test_default_config_handgun_high_confidence(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score(
            weapon_class="handgun",
            avg_confidence=0.82,
            frames_confirmed=10,
            weapon_count=1,
        )
        assert 0 <= result.risk_score <= 100
        assert result.risk_level in RiskLevel

    def test_score_increases_with_confidence(self):
        scorer = RiskScorer(ScoringConfig())
        low_conf = scorer.score("handgun", avg_confidence=0.3, frames_confirmed=5, weapon_count=1)
        high_conf = scorer.score("handgun", avg_confidence=0.9, frames_confirmed=5, weapon_count=1)
        assert high_conf.risk_score > low_conf.risk_score

    def test_score_increases_with_persistence(self):
        scorer = RiskScorer(ScoringConfig())
        short = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=2, weapon_count=1)
        long = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=15, weapon_count=1)
        assert long.risk_score > short.risk_score

    def test_score_increases_with_weapon_count(self):
        scorer = RiskScorer(ScoringConfig())
        single = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=10, weapon_count=1)
        multiple = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=10, weapon_count=3)
        assert multiple.risk_score > single.risk_score

    def test_rifle_scores_higher_than_knife(self):
        scorer = RiskScorer(ScoringConfig())
        rifle = scorer.score("rifle", avg_confidence=0.8, frames_confirmed=10, weapon_count=1)
        knife = scorer.score("knife", avg_confidence=0.8, frames_confirmed=10, weapon_count=1)
        assert rifle.risk_score > knife.risk_score

    def test_score_is_deterministic(self):
        """Same inputs → same output every time."""
        scorer = RiskScorer(ScoringConfig())
        r1 = scorer.score("handgun", 0.75, 8, 1)
        r2 = scorer.score("handgun", 0.75, 8, 1)
        assert r1.risk_score == r2.risk_score
        assert r1.risk_level == r2.risk_level


# =============================================================================
# Risk Level Classification Tests
# =============================================================================

class TestRiskLevels:
    """Tests for risk level thresholds."""

    def test_low_level(self):
        """Very low inputs should produce LOW level."""
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("knife", avg_confidence=0.2, frames_confirmed=1, weapon_count=1,
                              location_id="")
        # With knife(50)*0.3 + conf(20)*0.25 + pers(6.7)*0.2 + count(33.3)*0.15 + base(100)*0.1
        # = 15 + 5 + 1.3 + 5 + 10 = 36.3 → still MEDIUM. Need even lower:
        # Use 0 frames and 0 weapon_count to get truly LOW
        result = scorer.score("knife", avg_confidence=0.1, frames_confirmed=0, weapon_count=0)
        assert result.risk_level == RiskLevel.LOW

    def test_critical_level(self):
        """Maximum inputs should produce CRITICAL level."""
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("rifle", avg_confidence=0.99, frames_confirmed=30, weapon_count=3)
        assert result.risk_level == RiskLevel.CRITICAL

    def test_custom_thresholds(self):
        """Custom thresholds change level boundaries."""
        config = ScoringConfig(
            threshold_low_max=10.0,
            threshold_medium_max=20.0,
            threshold_high_max=30.0,
        )
        scorer = RiskScorer(config)
        # A score that would normally be MEDIUM should now be CRITICAL
        result = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=10, weapon_count=1)
        # With default weights, this should be well above 30 → CRITICAL
        assert result.risk_level == RiskLevel.CRITICAL

    def test_level_at_exact_boundary_low(self):
        """Score exactly at threshold_low_max → LOW (inclusive)."""
        config = ScoringConfig(threshold_low_max=50.0, threshold_medium_max=70.0, threshold_high_max=90.0)
        scorer = RiskScorer(config)
        # We need to engineer a score of exactly 50
        # With all factors at 50/100: 0.30*50 + 0.25*50 + 0.20*50 + 0.15*50 + 0.10*100 = 55
        # Not exactly 50, so test the classification logic directly
        level = scorer._classify_level(50.0)
        assert level == RiskLevel.LOW

    def test_level_just_above_low(self):
        config = ScoringConfig(threshold_low_max=30.0)
        scorer = RiskScorer(config)
        level = scorer._classify_level(30.1)
        assert level == RiskLevel.MEDIUM


# =============================================================================
# Boundary Tests
# =============================================================================

class TestBoundaryConditions:
    """Tests for edge cases and boundary values."""

    def test_zero_confidence(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", avg_confidence=0.0, frames_confirmed=10, weapon_count=1)
        assert result.risk_score >= 0
        assert result.risk_score <= 100

    def test_max_confidence(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", avg_confidence=1.0, frames_confirmed=10, weapon_count=1)
        assert result.risk_score >= 0
        assert result.risk_score <= 100

    def test_zero_frames(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=0, weapon_count=1)
        assert result.risk_score >= 0

    def test_very_high_frames(self):
        """Frames beyond max should cap at 100 normalized."""
        scorer = RiskScorer(ScoringConfig(persistence_max_frames=10))
        result = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=1000, weapon_count=1)
        # Persistence should be capped at 100
        persistence_comp = [c for c in result.components if c.factor_name == "Persistence"][0]
        assert persistence_comp.normalized_value == 100.0

    def test_zero_weapon_count(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=5, weapon_count=0)
        count_comp = [c for c in result.components if c.factor_name == "Weapon Count"][0]
        assert count_comp.normalized_value == 0.0

    def test_very_high_weapon_count(self):
        scorer = RiskScorer(ScoringConfig(weapon_count_max=3))
        result = scorer.score("handgun", avg_confidence=0.8, frames_confirmed=5, weapon_count=100)
        count_comp = [c for c in result.components if c.factor_name == "Weapon Count"][0]
        assert count_comp.normalized_value == 100.0  # Capped

    def test_score_never_exceeds_100(self):
        """Even with maximum inputs and high multiplier, score is clamped."""
        config = ScoringConfig(
            location_multipliers={"danger_zone": 3.0},
        )
        scorer = RiskScorer(config)
        result = scorer.score(
            "rifle", avg_confidence=1.0, frames_confirmed=100,
            weapon_count=10, location_id="danger_zone"
        )
        assert result.risk_score <= 100.0

    def test_score_never_below_zero(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("knife", avg_confidence=0.0, frames_confirmed=0, weapon_count=0)
        assert result.risk_score >= 0.0

    def test_unknown_weapon_class_uses_default(self):
        config = ScoringConfig(default_weapon_severity=42.0)
        scorer = RiskScorer(config)
        result = scorer.score("unknown_weapon_xyz", avg_confidence=0.8, frames_confirmed=5, weapon_count=1)
        severity_comp = [c for c in result.components if c.factor_name == "Weapon Severity"][0]
        assert severity_comp.normalized_value == 42.0


# =============================================================================
# Location Multiplier Tests
# =============================================================================

class TestLocationMultiplier:
    """Tests for location-based score adjustment."""

    def test_high_security_location_increases_score(self):
        config = ScoringConfig(location_multipliers={"server_room": 1.5, "default": 1.0})
        scorer = RiskScorer(config)

        normal = scorer.score("handgun", 0.8, 10, 1, location_id="lobby")
        secure = scorer.score("handgun", 0.8, 10, 1, location_id="server_room")

        assert secure.risk_score > normal.risk_score
        assert secure.location_multiplier == 1.5

    def test_low_priority_location_decreases_score(self):
        config = ScoringConfig(location_multipliers={"parking": 0.7})
        scorer = RiskScorer(config)

        result = scorer.score("knife", 0.6, 5, 1, location_id="parking")
        assert result.location_multiplier == 0.7

    def test_unknown_location_uses_default(self):
        config = ScoringConfig(default_location_multiplier=1.0)
        scorer = RiskScorer(config)
        result = scorer.score("handgun", 0.8, 10, 1, location_id="some_random_place")
        assert result.location_multiplier == 1.0

    def test_empty_location_uses_default(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", 0.8, 10, 1, location_id="")
        assert result.location_multiplier == 1.0


# =============================================================================
# Configuration Tests
# =============================================================================

class TestConfigurationImpact:
    """Tests that configuration changes affect scoring."""

    def test_custom_weights_shift_importance(self):
        """If confidence weight is 1.0 and others 0.0, only confidence matters."""
        config = ScoringConfig(
            weight_weapon_severity=0.0,
            weight_confidence=1.0,
            weight_persistence=0.0,
            weight_weapon_count=0.0,
            weight_location=0.0,
        )
        scorer = RiskScorer(config)

        # Different weapons but same confidence → same score
        r1 = scorer.score("rifle", avg_confidence=0.7, frames_confirmed=1, weapon_count=1)
        r2 = scorer.score("knife", avg_confidence=0.7, frames_confirmed=100, weapon_count=5)
        assert abs(r1.risk_score - r2.risk_score) < 0.01

    def test_custom_weapon_severity(self):
        config = ScoringConfig(weapon_severity_scores={"bomb": 100.0, "stick": 10.0})
        scorer = RiskScorer(config)

        bomb = scorer.score("bomb", 0.8, 10, 1)
        stick = scorer.score("stick", 0.8, 10, 1)
        assert bomb.risk_score > stick.risk_score

    def test_persistence_max_frames_affects_normalization(self):
        """Lower max_frames → persistence reaches 100 faster."""
        fast_config = ScoringConfig(persistence_max_frames=5)
        slow_config = ScoringConfig(persistence_max_frames=50)

        fast_scorer = RiskScorer(fast_config)
        slow_scorer = RiskScorer(slow_config)

        fast_result = fast_scorer.score("handgun", 0.8, 5, 1)
        slow_result = slow_scorer.score("handgun", 0.8, 5, 1)

        # Same frames=5: fast config gives 100%, slow gives 10%
        fast_pers = [c for c in fast_result.components if c.factor_name == "Persistence"][0]
        slow_pers = [c for c in slow_result.components if c.factor_name == "Persistence"][0]
        assert fast_pers.normalized_value == 100.0
        assert slow_pers.normalized_value == 10.0


# =============================================================================
# Explainability Tests
# =============================================================================

class TestExplainability:
    """Tests that scoring output is fully explainable."""

    def test_result_has_all_components(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", 0.8, 10, 1)
        assert len(result.components) == 5

        factor_names = {c.factor_name for c in result.components}
        assert "Weapon Severity" in factor_names
        assert "Detection Confidence" in factor_names
        assert "Persistence" in factor_names
        assert "Weapon Count" in factor_names
        assert "Location Base" in factor_names

    def test_components_sum_to_pre_multiplier_score(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", 0.8, 10, 1)
        component_sum = sum(c.weighted_score for c in result.components)
        assert abs(component_sum - result.pre_multiplier_score) < 0.01

    def test_explanation_is_readable(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("handgun", 0.82, 10, 1)
        explanation = result.explanation
        assert "Risk Score:" in explanation
        assert "handgun" in explanation
        assert "Weapon Severity" in explanation

    def test_to_dict_is_complete(self):
        scorer = RiskScorer(ScoringConfig())
        result = scorer.score("rifle", 0.9, 15, 2, location_id="lobby")
        d = result.to_dict()

        assert "risk_score" in d
        assert "risk_level" in d
        assert "components" in d
        assert "inputs" in d
        assert d["inputs"]["weapon_class"] == "rifle"
        assert d["inputs"]["weapon_count"] == 2
        assert len(d["components"]) == 5

    def test_get_info_shows_config(self):
        config = ScoringConfig(persistence_max_frames=20)
        scorer = RiskScorer(config)
        info = scorer.get_info()

        assert info["weights"]["weapon_severity"] == 0.30
        assert info["persistence_max_frames"] == 20
        assert "LOW" in info["thresholds"]
        assert "CRITICAL" in info["thresholds"]
