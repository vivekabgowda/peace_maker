"""Multiple-testing corrections (Sprint 14).

When N strategies / parameter sets are evaluated, the best raw p-value is
optimistic. Bonferroni (family-wise error) and Benjamini-Hochberg (false
discovery rate) correct for that so a "significant" winner isn't just the
luckiest of many draws.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TestResult:
    label: str
    p_value: float
    adjusted: float  # adjusted p-value / threshold comparison basis
    reject: bool  # reject the null (i.e. significant) after correction


def bonferroni(items: Sequence[tuple[str, float]], *, alpha: float = 0.05) -> list[TestResult]:
    """Family-wise error control: reject when p <= alpha / n."""
    n = len(items)
    if n == 0:
        return []
    threshold = alpha / n
    return [
        TestResult(label=label, p_value=p, adjusted=min(1.0, p * n), reject=p <= threshold)
        for label, p in items
    ]


def benjamini_hochberg(
    items: Sequence[tuple[str, float]], *, alpha: float = 0.05
) -> list[TestResult]:
    """FDR control (BH step-up). Returns results in the input order."""
    n = len(items)
    if n == 0:
        return []
    ordered = sorted(enumerate(items), key=lambda kv: kv[1][1])  # by p-value asc
    # Largest rank k with p_(k) <= (k/n) * alpha ⇒ reject all with rank <= k.
    max_reject_rank = 0
    for rank, (_orig_idx, (_label, p)) in enumerate(ordered, start=1):
        if p <= (rank / n) * alpha:
            max_reject_rank = rank
    # Monotone-adjusted q-values.
    adjusted_by_orig: dict[int, float] = {}
    prev = 1.0
    for rank in range(n, 0, -1):
        orig_idx, (_label, p) = ordered[rank - 1]
        q = min(prev, p * n / rank)
        adjusted_by_orig[orig_idx] = q
        prev = q

    results: list[TestResult] = []
    reject_orig = {ordered[r - 1][0] for r in range(1, max_reject_rank + 1)}
    for i, (label, p) in enumerate(items):
        results.append(
            TestResult(
                label=label,
                p_value=p,
                adjusted=round(adjusted_by_orig.get(i, 1.0), 6),
                reject=i in reject_orig,
            )
        )
    return results
