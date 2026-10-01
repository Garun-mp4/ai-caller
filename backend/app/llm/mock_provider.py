from datetime import datetime, timedelta, timezone
import json
from .base import LLMProvider

class MockLLMProvider(LLMProvider):
    async def generate(self, system_prompt, history, user_text):
        t = user_text.lower()
        if any(x in t for x in ["не звон", "удалите номер", "больше не надо"]):
            d={"speech":"Понял, больше звонить не будем. Всего доброго.","action":"do_not_call","stage":"end","callback_at":None,"reason":"Попросил больше не звонить"}
        elif any(x in t for x in ["перезвон", "завтра", "позже"]):
            when=(datetime.now(timezone.utc)+timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0).isoformat()
            d={"speech":"Хорошо, договорились. Перезвоним позже.","action":"callback","stage":"next_step","callback_at":when,"reason":"Попросил перезвонить"}
        elif any(x in t for x in ["интерес", "нужен сайт", "хотим сайт", "редизайн"]):
            d={"speech":"Отлично. Какой результат от сайта для вас сейчас самый важный?","action":"interested","stage":"qualification","callback_at":None,"reason":None}
        elif any(x in t for x in ["нет", "не интересно", "не нужно"]):
            d={"speech":"Понял, спасибо за время. Хорошего дня.","action":"end_call","stage":"end","callback_at":None,"reason":"Нет интереса"}
        else:
            d={"speech":"Добрый день. Мы помогаем бизнесу с сайтами и автоматизацией. Подскажите, актуально ли для вас улучшение сайта?","action":"continue","stage":"discovery","callback_at":None,"reason":None}
        return json.dumps(d, ensure_ascii=False)
