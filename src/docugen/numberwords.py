"""Convert numeric symbols in narration text to natural English words.

Run this on narration text BEFORE passing to TTS. Handles:
- Integers: 64,659 → "sixty-four thousand six hundred fifty-nine"
- Decimals: 0.1 → "zero point one"
- Percentages: 15% → "fifteen percent", +15.1% → "plus fifteen point one percent"
- Dollar amounts: $420 billion → "four hundred twenty billion dollars"
- Years: 2017 → "twenty seventeen" (contextual)
- Ordinals in context: not converted (keep "Layer 1" as-is for clarity)
"""

import re

ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
]
SCALES = [
    (1_000_000_000_000, "trillion"),
    (1_000_000_000, "billion"),
    (1_000_000, "million"),
    (1_000, "thousand"),
]


def _int_to_words(n: int) -> str:
    """Convert a non-negative integer to English words."""
    if n == 0:
        return "zero"

    if n < 0:
        return "negative " + _int_to_words(-n)

    parts = []

    for threshold, name in SCALES:
        if n >= threshold:
            parts.append(_int_to_words(n // threshold))
            parts.append(name)
            n %= threshold

    if n >= 100:
        parts.append(ONES[n // 100])
        parts.append("hundred")
        n %= 100

    if n >= 20:
        tens_word = TENS[n // 10]
        ones_word = ONES[n % 10]
        if ones_word:
            parts.append(f"{tens_word}-{ones_word}")
        else:
            parts.append(tens_word)
    elif n > 0:
        parts.append(ONES[n])

    return " ".join(parts)


def _year_to_words(year: int) -> str:
    """Convert a 4-digit year to natural speech form.

    2017 → "twenty seventeen"
    2000 → "two thousand"
    1999 → "nineteen ninety-nine"
    2030 → "twenty thirty"
    """
    if year < 100 or year > 9999:
        return _int_to_words(year)

    if year % 1000 == 0:
        return _int_to_words(year // 1000) + " thousand"

    if year % 100 == 0:
        return _int_to_words(year // 100) + " hundred"

    # Years like 2001-2009
    if 2000 <= year <= 2009:
        return "two thousand " + ONES[year - 2000]

    high = year // 100
    low = year % 100
    return _int_to_words(high) + " " + _int_to_words(low)


def _decimal_to_words(integer_part: int, decimal_str: str) -> str:
    """Convert a decimal number. 15.1 → 'fifteen point one'."""
    int_words = _int_to_words(integer_part)
    digit_words = " ".join(ONES[int(d)] if d != "0" else "zero" for d in decimal_str)
    return f"{int_words} point {digit_words}"


# Year pattern: 4-digit number that looks like a year (1800-2099)
_YEAR_RE = re.compile(
    r'''(?x)
    (?:(?<=in\s)|(?<=since\s)|(?<=by\s)|(?<=of\s)|(?<=circa\s)|(?<=year\s))
    (1[89]\d{2}|20\d{2})
    (?=[\s.,;:!?\-)]|$)
    '''
)

# Standalone 4-digit year at sentence boundaries or after common prepositions
_YEAR_STANDALONE_RE = re.compile(
    r'\b(1[89]\d{2}|20[0-9]{2})\b'
)

# Dollar amounts: $420 billion, $200
_MONEY_RE = re.compile(
    r'\$\s*([\d,]+(?:\.\d+)?)\s*(trillion|billion|million|thousand)?',
    re.IGNORECASE,
)

# "N dollars" pattern
_N_DOLLARS_RE = re.compile(
    r'\b([\d,]+(?:\.\d+)?)\s+dollars?\b',
    re.IGNORECASE,
)

# Percentage: +15.1%, 76%, 0.1 percent — capture preceding space to preserve it
_PCT_RE = re.compile(
    r'(?<!\w)([+-])?\s*([\d,]+(?:\.\d+)?)\s*(?:%|percent)',
    re.IGNORECASE,
)

# Plain numbers with commas: 64,659
_COMMA_NUM_RE = re.compile(r'\b(\d{1,3}(?:,\d{3})+)\b')

# Plain decimals: 0.1, 10.3
_DECIMAL_RE = re.compile(r'\b(\d+)\.(\d+)\b')

# Plain integers (standalone, not part of something else)
_INT_RE = re.compile(r'\b(\d+)\b')

# Compound names with numbers: PI-103, Rb1, K-2SO, dGTP, etc.
# Number immediately preceded by a letter or hyphen-letter
_COMPOUND_NUM_RE = re.compile(r'[A-Za-z]-?\d+|\d+-?[A-Za-z]')

# Contexts where a number is likely a label, not a quantity (Layer 1, Phase 2, etc.)
_LABEL_CONTEXT_RE = re.compile(
    r'(?:layer|phase|step|round|stage|figure|fig|analysis|chapter|ch|version|v)\s*\d',
    re.IGNORECASE,
)


def _is_year_context(text: str, match_start: int, number: str) -> bool:
    """Check if a 4-digit number is used as a year based on surrounding context."""
    n = int(number)
    if not (1800 <= n <= 2099):
        return False

    # Check preceding words
    before = text[max(0, match_start - 15):match_start].lower().strip()
    year_prepositions = ("in", "since", "by", "of", "circa", "year", "published")
    if any(before.endswith(p) for p in year_prepositions):
        return True

    # Check following context
    after = text[match_start + len(number):match_start + len(number) + 10].lower().strip()
    if after.startswith((",") ) and "paper" in text[match_start:match_start+50].lower():
        return True

    # Names that include years (e.g., "Sarnoski et al. 2017")
    if re.search(r'et\s+al\.?\s*$', before):
        return True

    return False


def _is_label_context(text: str, match_start: int) -> bool:
    """Check if a number is a label (Layer 1, Phase 2, etc.)."""
    before = text[max(0, match_start - 12):match_start].lower()
    return bool(_LABEL_CONTEXT_RE.search(before + text[match_start:match_start + 5]))


def _is_compound_number(text: str, match_start: int, match_end: int) -> bool:
    """Check if a number is part of a compound name (PI-103, Rb1, K-2SO)."""
    # Character immediately before the number
    if match_start > 0:
        before_char = text[match_start - 1]
        if before_char.isalpha() or (before_char == '-' and match_start > 1 and text[match_start - 2].isalpha()):
            return True
    # Character immediately after the number
    if match_end < len(text):
        after_char = text[match_end]
        if after_char.isalpha() or (after_char == '-' and match_end + 1 < len(text) and text[match_end + 1].isalpha()):
            return True
    return False


def numbers_to_words(text: str) -> str:
    """Convert all numeric symbols in text to natural English words.

    Handles dollars, percentages, comma-separated numbers, decimals,
    years, and plain integers. Preserves label-style numbers (Layer 1, Phase 2).
    """
    # Pass 1: Dollar amounts ($420 billion)
    def _replace_money(m):
        num_str = m.group(1).replace(",", "")
        scale = m.group(2) or ""
        if "." in num_str:
            int_part, dec_part = num_str.split(".", 1)
            words = _decimal_to_words(int(int_part), dec_part)
        else:
            words = _int_to_words(int(num_str))
        if scale:
            words += " " + scale.lower()
        words += " dollars"
        return words

    text = _MONEY_RE.sub(_replace_money, text)

    # Pass 2: "N dollars" pattern
    def _replace_n_dollars(m):
        num_str = m.group(1).replace(",", "")
        if "." in num_str:
            int_part, dec_part = num_str.split(".", 1)
            words = _decimal_to_words(int(int_part), dec_part)
        else:
            words = _int_to_words(int(num_str))
        return words + " dollars"

    text = _N_DOLLARS_RE.sub(_replace_n_dollars, text)

    # Pass 3: Percentages (+15.1%, 76 percent)
    def _replace_pct(m):
        sign = m.group(1) or ""
        num_str = m.group(2).replace(",", "")
        prefix = ""
        if sign == "+":
            prefix = "plus "
        elif sign == "-":
            prefix = "minus "

        if "." in num_str:
            int_part, dec_part = num_str.split(".", 1)
            words = _decimal_to_words(int(int_part), dec_part)
        else:
            words = _int_to_words(int(num_str))
        return prefix + words + " percent"

    text = _PCT_RE.sub(_replace_pct, text)

    # Pass 4: Comma-separated numbers (64,659)
    def _replace_comma_num(m):
        if _is_label_context(text, m.start()) or _is_compound_number(text, m.start(), m.end()):
            return m.group(0)
        num = int(m.group(1).replace(",", ""))
        return _int_to_words(num)

    text = _COMMA_NUM_RE.sub(_replace_comma_num, text)

    # Pass 5: Decimals (0.1, 10.3) — but not inside words already converted
    def _replace_decimal(m):
        if _is_label_context(text, m.start()) or _is_compound_number(text, m.start(), m.end()):
            return m.group(0)
        return _decimal_to_words(int(m.group(1)), m.group(2))

    text = _DECIMAL_RE.sub(_replace_decimal, text)

    # Pass 6: Remaining standalone integers
    def _replace_int(m):
        num_str = m.group(1)
        n = int(num_str)

        if _is_label_context(text, m.start()) or _is_compound_number(text, m.start(), m.end()):
            return num_str

        # Year detection
        if len(num_str) == 4 and _is_year_context(text, m.start(), num_str):
            return _year_to_words(n)

        # Small numbers (0-9) — keep as digits if they look like labels
        if n <= 9:
            return _int_to_words(n)

        return _int_to_words(n)

    text = _INT_RE.sub(_replace_int, text)

    # Clean up double spaces
    text = re.sub(r'  +', ' ', text)

    return text
