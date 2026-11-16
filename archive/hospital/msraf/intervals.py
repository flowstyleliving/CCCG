"""Exact half-open interval arithmetic, shared by the environment and scorers."""


def merged(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def covered_minutes(start, end, intervals):
    # Union before summing: overlapping providers must never earn double coverage.
    return sum(b - a for a, b in merged(
        (max(start, a), min(end, b)) for a, b in intervals))


def covers(start, end, intervals):
    return covered_minutes(start, end, intervals) == end - start


def commitment_intervals(commitments, patient="A", person="son"):
    # A withdrawal truncates authorization at its effective time. Later answers
    # cannot retroactively authorize labor before the answer was recorded.
    return [(max(c["start"], c["recorded_at"]),
             min(c["end"], c.get("revoked_at", c["end"])))
            for c in commitments
            if c["patient"] == patient and c["person"] == person
            and c["kind"] == "availability"]
