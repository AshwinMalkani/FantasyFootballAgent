"""Turn a projected stat line into fantasy points."""

# Sleeper league scoring_settings keys match the projection stat keys 1:1,
# so exact scoring is a dot product.
def score_stat_line(stats: dict[str, float], scoring: dict[str, float]) -> float:
    total = 0.0
    for key, weight in scoring.items():
        val = stats.get(key)
        if val:
            total += weight * val
    return round(total, 2)


def approx_points(stats: dict[str, float], rec_value: float) -> float:
    """Pick the closest of Sleeper's precomputed PPR / half / standard totals."""
    if rec_value >= 0.75:
        return round(float(stats.get("pts_ppr", 0.0) or 0.0), 2)
    if rec_value >= 0.25:
        return round(float(stats.get("pts_half_ppr", 0.0) or 0.0), 2)
    return round(float(stats.get("pts_std", 0.0) or 0.0), 2)


def scoring_label(rec_value: float | None) -> str:
    if rec_value is None:
        return "Unknown"
    if rec_value >= 0.75:
        return "PPR"
    if rec_value >= 0.25:
        return "Half PPR"
    return "Standard"
