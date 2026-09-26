"""Номинальный охват score: backend владеет весами, UI только отображает результат."""

from decimal import ROUND_HALF_UP, Decimal

from .mvp import WEIGHTS, MVPPolicy

SUPPORTED_POLICIES = {"mvp-score-v1", "mvp-score-v1.1", MVPPolicy.version}


def score_coverage(policy_version, categories):
    """Не угадывать веса неизвестной policy; partial score не означает полный сбор данных."""
    if policy_version not in SUPPORTED_POLICIES:
        return None
    scored = [name for name in WEIGHTS if categories.get(name, {}).get("score") is not None]
    return {"nominal_weight_percent": sum(WEIGHTS[name] for name in scored),
            "scored_categories": len(scored),
            "unscored_categories": [name for name in WEIGHTS if name not in scored],
            "partial_categories": [name for name in scored if categories[name].get("availability") == "partial"]}


def score_preview(policy_version, categories):
    """Return a derived preview without weakening or replacing the official score gate."""
    if policy_version not in SUPPORTED_POLICIES:
        return None
    scored = {name: categories.get(name, {}).get("score") for name in WEIGHTS
              if categories.get(name, {}).get("score") is not None}
    if not scored:
        return None
    nominal_weight = sum(WEIGHTS[name] for name in scored)
    numeric = len(scored) >= 2 and nominal_weight >= 30
    weighted = sum(Decimal(str(score)) * WEIGHTS[name] for name, score in scored.items())
    value = (float((weighted / nominal_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
             if numeric else None)
    return {"score": value, "nominal_weight_percent": nominal_weight,
            "scored_categories": len(scored), "numeric": numeric}
