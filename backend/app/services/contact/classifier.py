import re


class TitleClassifier:
    WHITE_LIST_PATTERNS = [
        (1, re.compile(r"\b(CEO|Chief Executive(?: Officer)?|Founder|Co[-\s]?Founder|Owner|Co-Owner|President|Chairman|Chairperson)\b", re.I)),
        (2, re.compile(r"\b(Managing Director|MD|Director General|General Director|Executive Director|Geschaeftsfuehrer|Gesch.+f.+hrer|Director Ejecutivo|Directeur General|Consejero Delegado)\b", re.I)),
        (3, re.compile(r"\b(General Manager|GM|COO|Chief Operating Officer|VP(?: of)? (?:Operations|Business|Commercial)|Vice President(?: of)? (?:Operations|Business|Commercial)|Head of (?:Operations|Business)|Betriebsleiter|Gerente General)\b", re.I)),
        (4, re.compile(r"\b(Procurement|Purchasing|Sourcing|Supply Chain|CPO|Chief Procurement Officer|Head of (?:Procurement|Purchasing|Sourcing)|Director of (?:Procurement|Purchasing|Sourcing)|VP(?: of)? (?:Procurement|Purchasing|Sourcing)|Einkauf|Einkaufsleiter)\b", re.I)),
    ]
    BLACK_LIST_PATTERNS = [
        re.compile(r"\bSales\b(?!\s+(?:Director|General)\b)", re.I),
        re.compile(r"\b(Marketing|Brand|Customer Service|Support|Receptionist|Administrat|HR|Human Resources|Accountant|Bookkeeper|Intern|Trainee)\b", re.I),
        re.compile(r"\bFinance\b(?!\s+Director)", re.I),
        re.compile(r"\bAssistant\b(?!\s+(?:General\s+Manager|Managing))", re.I),
        re.compile(r"^Director(?:\s*,)?$", re.I),
    ]

    def classify(self, title: str) -> tuple[bool, int]:
        for pattern in self.BLACK_LIST_PATTERNS:
            if pattern.search(title):
                return False, -1
        for priority, pattern in self.WHITE_LIST_PATTERNS:
            if pattern.search(title):
                return True, priority
        return False, -1
