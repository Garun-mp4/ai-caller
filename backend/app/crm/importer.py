import re
try:
    import phonenumbers
except ImportError:
    phonenumbers = None
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import Lead

PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{6,}\d")

def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw.strip())
    if raw.strip().startswith("00") and len(digits) >= 8:
        pass
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not (8 <= len(digits) <= 15) or digits.startswith("0"):
        return None
    candidate = "+" + digits
    if phonenumbers is not None:
        try:
            parsed = phonenumbers.parse(candidate, None)
            if not phonenumbers.is_possible_number(parsed):
                return None
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            return None
    return candidate

def parse_line(line: str):
    line = line.strip()
    if not line:
        return None, None
    match = PHONE_RE.search(line)
    if not match:
        return None, None
    phone = normalize_phone(match.group(0))
    if not phone:
        return None, None
    before = line[:match.start()].strip(" ,|;:-\t")
    after = line[match.end():].strip(" ,|;:-\t")
    company = before or after or None
    return company, phone

def import_txt(db: Session, content: str) -> dict:
    imported = duplicates = invalid = 0
    seen_batch: set[str] = set()
    for line in content.splitlines():
        if not line.strip():
            continue
        company, phone = parse_line(line)
        if not phone:
            invalid += 1
            continue
        if phone in seen_batch or db.scalar(select(Lead.id).where(Lead.phone == phone)):
            duplicates += 1
            seen_batch.add(phone)
            continue
        db.add(Lead(phone=phone, company=company))
        seen_batch.add(phone)
        imported += 1
    db.commit()
    return {"imported": imported, "duplicates": duplicates, "invalid": invalid}
