from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

# Brazilian-specific recognizers
_cpf_recognizer = PatternRecognizer(
    supported_entity="BR_CPF",
    patterns=[Pattern("cpf", r"\d{3}\.\d{3}\.\d{3}-\d{2}", score=0.95)],
)
_cnpj_recognizer = PatternRecognizer(
    supported_entity="BR_CNPJ",
    patterns=[Pattern("cnpj", r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", score=0.95)],
)
_phone_br_recognizer = PatternRecognizer(
    supported_entity="BR_PHONE",
    patterns=[Pattern("phone_br", r"\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}", score=0.75)],
)

_analyzer = AnalyzerEngine()
_analyzer.registry.add_recognizer(_cpf_recognizer)
_analyzer.registry.add_recognizer(_cnpj_recognizer)
_analyzer.registry.add_recognizer(_phone_br_recognizer)
_anonymizer = AnonymizerEngine()

MIN_SCORE = 0.6


def detect_and_anonymize(text: str) -> dict:
    raw = _analyzer.analyze(text=text, language="en")
    hits = [r for r in raw if r.score >= MIN_SCORE]

    entities = [
        {
            "type": r.entity_type,
            "score": r.score,
            "value": text[r.start : r.end],
        }
        for r in hits
    ]

    sanitized = _anonymizer.anonymize(text=text, analyzer_results=hits).text if hits else text

    return {
        "entities": entities,
        "found": bool(entities),
        "sanitized": sanitized,
    }
