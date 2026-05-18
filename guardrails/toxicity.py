from detoxify import Detoxify

_model = None
THRESHOLD = 0.7


def _get_model() -> Detoxify:
    global _model
    if _model is None:
        _model = Detoxify("original")
    return _model


def check_toxicity(text: str) -> dict:
    scores = {k: float(v) for k, v in _get_model().predict(text).items()}
    max_score = max(scores.values())
    return {
        "score": max_score,
        "scores": scores,
        "is_toxic": max_score >= THRESHOLD,
    }
