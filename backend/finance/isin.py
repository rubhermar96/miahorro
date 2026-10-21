"""ISIN codes (ISO 6166): two letters for the country, nine characters and a check digit
computed with the Luhn algorithm over the letters turned into numbers (A = 10 … Z = 35)."""

import re

_PATTERN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def normalize_isin(code: str) -> str:
    return "".join(code.split()).upper()


def is_valid_isin(code: str) -> bool:
    if not _PATTERN.fullmatch(code):
        return False
    digits = "".join(str(int(char, 36)) for char in code[:-1])
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 0:  # every other digit from the right, the check digit aside
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (total + int(code[-1])) % 10 == 0
