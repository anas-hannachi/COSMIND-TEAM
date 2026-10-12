"""Decision-level comparisons for host and firmware logs."""


def compare_decisions(reference: list[dict], candidate: list[dict]) -> dict:
    mismatches = []
    for index, (left, right) in enumerate(zip(reference, candidate)):
        if (left.get("action"), left.get("task_id")) != (right.get("action"), right.get("task_id")):
            mismatches.append({"index": index, "reference": left, "candidate": right})
    if len(reference) != len(candidate):
        mismatches.append({"index": min(len(reference), len(candidate)), "reason": "length_mismatch"})
    return {"reference_count": len(reference), "candidate_count": len(candidate),
            "mismatch_count": len(mismatches), "mismatches": mismatches}
