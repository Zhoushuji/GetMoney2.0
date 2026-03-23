import re


class TitleClassifier:
    WHITE_LIST_PATTERNS = [
        (1, re.compile(r"\b(CEO|Chief Executive Officer|Founder|Co-Founder|Owner|Co-Owner)\b", re.I)),
        (2, re.compile(r"\bManaging Director\b", re.I)),
        (3, re.compile(r"\b(General Manager|GM)\b", re.I)),
        (4, re.compile(r"\b(Procurement|Purchasing|Sourcing)\b", re.I)),
    ]
    BLACK_LIST_PATTERNS = [
        re.compile(r"\b(?<!Managing )Director\b", re.I),
        re.compile(r"\b(Sales|Marketing|Support|Customer Service|HR|Human Resources|Accountant|Intern)\b", re.I),
    ]

    def classify(self, title: str) -> tuple[bool, int]:
        for pattern in self.BLACK_LIST_PATTERNS:
            if pattern.search(title):
                return False, -1
        for priority, pattern in self.WHITE_LIST_PATTERNS:
            if pattern.search(title):
                return True, priority
        return False, -1
