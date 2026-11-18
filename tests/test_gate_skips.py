"""Confirmed gate skips are excluded from the binary pass decision."""
import pytest

from atlas_finance.pass_rules import evaluate, judge_pass


def gate_case(weight, *, gated_out=True, gates_met=False):
    rubric = [{"criterion": "control", "section": "A", "weight": 6},
              {"criterion": "gated", "section": "B", "weight": weight}]
    info = {"criterion_results": [dict(rubric[0], met=True),
                                 dict(rubric[1], met=None, skipped=True, score_contribution=0)],
            "section_results": [{"section": "B", "gated_out": gated_out,
                                 "section_gates_met": gates_met}]}
    return info, rubric


@pytest.mark.parametrize("version", ["v1.0", "v1.1"])
@pytest.mark.parametrize("weight", [2, 3, 5, 6, -1])
def test_failed_gate_skips_do_not_fail_an_otherwise_passing_trial(version, weight):
    info, rubric = gate_case(weight)
    result = evaluate(info, rubric, version)
    assert result["valid"] is True and result["passed"] is True
    assert result["failed_critical_indices"] == []
    assert result["unknown_indices"] == []
    assert result["triggered_penalty_indices"] == []
    assert judge_pass(info, rubric=rubric, atlas_version=version) == (True, [])


def test_failed_gate_skips_are_also_excluded_with_a_custom_threshold():
    info, rubric = gate_case(6)
    assert judge_pass(info, rubric=rubric, min_weight=3) == (True, [])


@pytest.mark.parametrize("version", ["v1.0", "v1.1"])
@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("weight,field", [
    (6, "failed_critical_indices"), (-1, "triggered_penalty_indices"),
])
def test_failed_gate_does_not_hide_actual_critical_misses_or_penalties(version, index, weight, field):
    info, rubric = gate_case(6)
    rubric[index]["weight"] = weight
    info["criterion_results"][index].update(weight=weight, skipped=False, met=weight < 0)
    result = evaluate(info, rubric, version)
    assert result["valid"] is True and result["passed"] is False
    assert result[field] == [index]


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
