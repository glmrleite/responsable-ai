from .pii import detect_and_anonymize
from .toxicity import check_toxicity


class GuardrailPipeline:
    """Sequentially applies guardrails: toxicity check → PII masking."""

    def analyze(self, text: str) -> dict:
        result = {
            "original": text,
            "sanitized_message": text,
            "blocked": False,
            "block_reason": None,
            "toxicity": {},
            "pii": {"entities": [], "found": False, "sanitized": text},
        }

        toxicity = check_toxicity(text)
        result["toxicity"] = toxicity

        if toxicity["is_toxic"]:
            result["blocked"] = True
            result["block_reason"] = (
                f"Conteúdo tóxico detectado (score: {toxicity['score']:.2f}). "
                "Mensagem não enviada ao modelo."
            )
            return result

        pii = detect_and_anonymize(text)
        result["pii"] = pii
        result["sanitized_message"] = pii["sanitized"]

        return result
