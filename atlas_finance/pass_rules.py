#!/usr/bin/env python3
"""Evaluate versioned ATLAS pass rules from grading evidence."""

from collections import Counter
import math
from operator import ge, gt

RULES = {
    "v1.0": {"operator": ">=", "threshold": 3},
    "v1.1": {"operator": ">", "threshold": 5},
}


def critical(weight, atlas_version):
    rule = RULES[atlas_version]
    compare = ge if rule["operator"] == ">=" else gt
    return compare(weight, rule["threshold"])


def rule_metadata(atlas_version, *, min_weight=None):
    if min_weight is not None:
        if not math.isfinite(min_weight) or min_weight <= 0:
            raise ValueError("custom min_weight must be finite and positive")
        atlas_version, rule = "custom", {"operator": ">=", "threshold": min_weight}
    else:
        rule = RULES[atlas_version]
    return {
        "atlas_version": atlas_version,
        "rule": f"all criteria with weight {rule['operator']} {rule['threshold']:g} met; no negative-weight criterion met",
        "critical_weight_operator": rule["operator"],
        "critical_weight_threshold": rule["threshold"],
    }


def rubric_items(rubric):
    if isinstance(rubric, list):
        return rubric
    items = list(rubric.get("criteria", []))
    for section in rubric.get("sections", []):
        items.extend(dict(item, section=section["name"]) for item in section["criteria"])
    return items


def identity(item):
    weight = item["weight"]
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
        raise ValueError("criterion weight must be a finite number")
    criterion = item["criterion"]
    section = item.get("section")
    if not isinstance(criterion, str) or not criterion.strip():
        raise ValueError("criterion text must be nonempty")
    return (section.strip() if section else None, criterion, weight)


def evaluate(info, rubric, atlas_version, *, min_weight=None, errored_policy="fail"):
    """Evaluate criteria and verify completeness against the supplied rubric."""
    metadata = rule_metadata(atlas_version, min_weight=min_weight)
    if errored_policy not in ("fail", "ignore"):
        raise ValueError("errored_policy must be fail or ignore")
    compare = ge if metadata["critical_weight_operator"] == ">=" else gt
    threshold = metadata["critical_weight_threshold"]
    results = info.get("criterion_results")
    if not isinstance(results, list) or not results:
        raise ValueError("nonempty rubric and criterion_results are required")
    identities = Counter(map(identity, results))
    if rubric is None:
        raise ValueError("complete rubric is required")
    if Counter(map(identity, rubric_items(rubric))) != identities:
        raise ValueError("criterion results do not match the complete rubric (text, section, weight)")
    unknown = []
    failed = []
    penalties = []
    critical_count = penalty_count = 0
    for index, result in enumerate(results):
        required = compare(result["weight"], threshold)
        penalty = result["weight"] < 0
        critical_count += required
        penalty_count += penalty
        if not (required or penalty):
            continue
        met = result.get("met")
        if type(met) is not bool or result.get("skipped", False):
            unknown.append(index)
        elif required and not met:
            failed.append(index)
        elif penalty and met:
            penalties.append(index)
    # A known critical miss or penalty proves failure even if other verdicts
    # are unavailable. Certifying success requires every relevant verdict.
    valid = bool(failed or penalties) or not unknown or errored_policy == "ignore"
    return {
        "schema_version": 2,
        **metadata,
        "valid": valid,
        "passed": not (failed or penalties) if valid else None,
        "criterion_count": len(results),
        "critical_criterion_count": critical_count,
        "penalty_criterion_count": penalty_count,
        "failed_critical_indices": failed,
        "triggered_penalty_indices": penalties,
        "unknown_indices": unknown,
        "errored_policy": errored_policy,
    }


def judge_pass(info, *, rubric=None, min_weight=None, errored_policy="fail", atlas_version="v1.0"):
    """Return passed (None for incomplete evidence) and failure reasons."""
    try:
        result = evaluate(info, rubric, atlas_version, min_weight=min_weight,
                          errored_policy=errored_policy)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return None, [f"invalid grading evidence: {exc}"]
    reasons = []
    for field, label in (("failed_critical_indices", "required criterion not met"),
                         ("triggered_penalty_indices", "penalty triggered"),
                         ("unknown_indices", "unevaluated criterion")):
        if field == "unknown_indices" and errored_policy == "ignore":
            continue
        for index in result[field]:
            criterion = info["criterion_results"][index]
            reasons.append(f"{label} (w={criterion['weight']:g}): {criterion['criterion'][:90]}")
    return result["passed"], reasons
