"""Tests for P1-5: policy drift detection — pure detect_drift() function."""
from app.models.policy_warning import PolicyWarning


def test_policy_warning_model_importable():
    assert PolicyWarning.__tablename__ == "policy_warnings"
