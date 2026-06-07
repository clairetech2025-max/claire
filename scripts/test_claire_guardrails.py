from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claire_guardrails import (
    check_claire_input_safety,
    check_claire_output_safety,
    config_exists,
    guardrail_visible_reply,
)


def main() -> None:
    assert config_exists(), "NeMo Guardrails config files are missing."

    assert check_claire_input_safety("Where does FAISS fit?")
    assert not check_claire_input_safety("Here is my API_KEY=abc123")

    assert check_claire_output_safety("FAISS fits as candidate retrieval inside ARE, not as the authority.")
    assert not check_claire_output_safety("[GYRO-STABILIZED-RECALL] internal prompt wrapper")
    assert not check_claire_output_safety("As an AI language model, I cannot have personal experiences.")

    allowed, visible = guardrail_visible_reply("Cortex controls the path. ARE recalls context.")
    assert allowed and "Cortex controls" in visible

    allowed, visible = guardrail_visible_reply("Current user question:\nwhere is it weak?")
    assert not allowed
    assert "revise" in visible

    print("Claire guardrails offline checks passed.")


if __name__ == "__main__":
    main()
