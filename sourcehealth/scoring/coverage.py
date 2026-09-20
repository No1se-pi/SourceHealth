"""Номинальный охват score: backend владеет весами, UI только отображает результат."""

from .mvp import WEIGHTS, MVPPolicy


def score_coverage(policy_version, categories):
    """Не угадывать веса неизвестной policy; partial score не означает полный сбор данных."""
    if policy_version not in {"mvp-score-v1", "mvp-score-v1.1", MVPPolicy.version}:
        return None
    scored = [name for name in WEIGHTS if categories.get(name, {}).get("score") is not None]
    return {"nominal_weight_percent": sum(WEIGHTS[name] for name in scored),
            "scored_categories": len(scored),
            "unscored_categories": [name for name in WEIGHTS if name not in scored],
            "partial_categories": [name for name in scored if categories[name].get("availability") == "partial"]}
