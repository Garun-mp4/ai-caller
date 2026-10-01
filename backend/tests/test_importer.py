from app.crm.importer import normalize_phone, import_txt
from app.models import Lead
from sqlalchemy import select

def test_phone_validation():
    assert normalize_phone("+7 (999) 111-22-33") == "+79991112233"
    assert normalize_phone("abc") is None

def test_import_and_duplicates(db):
    r=import_txt(db,"ООО Альфа,+79991111111\n+79992222222\n+79991111111\nbad")
    assert r=={"imported":2,"duplicates":1,"invalid":1}
    assert len(db.scalars(select(Lead)).all())==2
