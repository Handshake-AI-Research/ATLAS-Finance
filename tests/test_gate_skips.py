"""Gate-skipped criteria have a known zero contribution, not a judge error."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.pass_rules import evaluate


def gate_case(weight, *, gated_out=True, gates_met=False):
    rubric = [{"criterion": "control", "section": "A", "weight": 6},
              {"criterion": "gated", "section": "B", "weight": weight}]
    info = {"criterion_results": [dict(rubric[0], met=True),
                                 dict(rubric[1], met=None, skipped=True, score_contribution=0)],
            "section_results": [{"section": "B", "gated_out": gated_out,
                                 "section_gates_met": gates_met}]}
    return info, rubric


@pytest.mark.parametrize("version,weight,passed", [
    ("v1.0", 2, True), ("v1.0", 3, False), ("v1.0", 6, False), ("v1.0", -1, True),
    ("v1.1", 3, True), ("v1.1", 5, True), ("v1.1", 6, False), ("v1.1", -1, True),
])
def test_failed_gate_has_the_versioned_effective_score(version, weight, passed):
    info, rubric = gate_case(weight)
    result = evaluate(info, rubric, version)
    assert result["valid"] is True and result["passed"] is passed
    assert result["unknown_indices"] == []
    assert result["triggered_penalty_indices"] == []


@pytest.mark.parametrize("state", ["gate_error", "gate_passed", "not_gated", "no_section_evidence"])
def test_a_skipped_verdict_without_a_known_failed_gate_stays_unknown(state):
    info, rubric = gate_case(6)
    if state == "gate_error":
        info["section_results"][0]["section_gates_met"] = None
    elif state == "gate_passed":
        info["section_results"][0]["section_gates_met"] = True
    elif state == "not_gated":
        info["section_results"][0]["gated_out"] = False
    else:
        info.pop("section_results")
    result = evaluate(info, rubric, "v1.1")
    assert result["valid"] is False and result["passed"] is None


def test_failed_gate_does_not_hide_an_unskipped_judge_error():
    info, rubric = gate_case(6)
    info["criterion_results"][1]["skipped"] = False
    result = evaluate(info, rubric, "v1.1")
    assert result["valid"] is False and result["passed"] is None
