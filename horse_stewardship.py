from __future__ import annotations

from current_truth_loader import load_current_truth


def get_horse_stewardship_status() -> dict:
    truth = load_current_truth()
    return truth.get("horse_stewardship") or {"status": "unknown", "principle": "Horses are central mission assets, not a side story."}


class HorseStewardship:
    def get_status(self) -> dict:
        return get_horse_stewardship_status()
