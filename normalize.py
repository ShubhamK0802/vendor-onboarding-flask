from config import SUFFIX_WORDS

EMPTY_WORDS = {"", "n/a", "none", "null", "-"}

def clean_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in EMPTY_WORDS:
        return None
    return text

def normalize_id(value):
    text = clean_value(value)
    if text is None:
        return None
    return "".join(text.split()).replace("-", "").upper()

def normalize_name(value):
    text = clean_value(value)
    if text is None:
        return None
    text = text.lower().replace("&", " and ")
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(text.split())


def core_name(value):
    full = normalize_name(value)
    if full is None:
        return None
    words = [word for word in full.split() if word not in SUFFIX_WORDS]
    return " ".join(words)