import phonenumbers


def parse_phone(raw: str, country_hint: str | None = None) -> str | None:
    try:
        parsed = phonenumbers.parse(raw, country_hint)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
