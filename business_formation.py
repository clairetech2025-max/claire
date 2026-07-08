from __future__ import annotations

from current_truth_loader import load_current_truth


def get_business_formation_status() -> dict:
    truth = load_current_truth()
    return {
        "company_profile": truth.get("company_profile"),
        "founding_team": truth.get("founding_team"),
        "mission_statement": truth.get("mission_statement"),
    }


class BusinessFormation:
    def get_status(self) -> dict:
        return get_business_formation_status()
