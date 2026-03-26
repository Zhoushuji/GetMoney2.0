from app.services.contact.classifier import TitleClassifier


def test_title_classifier_cases() -> None:
    classifier = TitleClassifier()
    assert classifier.classify("CEO") == (True, 1)
    assert classifier.classify("Managing Director") == (True, 2)
    assert classifier.classify("CEO at Global Geosystems") == (True, 1)
    assert classifier.classify("Founder / CEO") == (True, 1)
    assert classifier.classify("Co-Founder & CEO") == (True, 1)
    assert classifier.classify("Directeur General") == (True, 2)
    assert classifier.classify("Sales Director") == (False, -1)
