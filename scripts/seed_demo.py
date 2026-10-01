from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.db.session import SessionLocal
from app.db.base import Base
from app.db.session import engine
from app.crm.importer import import_txt
Base.metadata.create_all(engine)
db=SessionLocal(); print(import_txt(db,"ООО Альфа,+79991111111\nООО Бета,+79992222222\nООО Гамма,+79993333333\nООО Дельта,+79994444444")); db.close()
