"""Confidence scoring utilities for mappings and classifications."""


def combine_confidences(scores: list[float], method: str = "average") -> float:
    """
    Combine multiple confidence scores.

    Args:
        scores: List of confidence scores (0–1)
        method: Combination method ('average', 'min', 'max')

    Returns:
        Combined confidence score (0–1)
    """
    if not scores:
        return 0.0

    if method == "average":
        return sum(scores) / len(scores)
    elif method == "min":
        return min(scores)
    elif method == "max":
        return max(scores)
    else:
        raise ValueError(f"Unknown confidence combination method: {method}")


def boost_confidence(base_score: float, boost_amount: float) -> float:
    """
    Boost a confidence score (e.g., due to user feedback).

    Args:
        base_score: Original confidence (0–1)
        boost_amount: Amount to boost (0–1)

    Returns:
        Boosted confidence (clamped to 0–1)
    """
    return min(1.0, base_score + boost_amount)
