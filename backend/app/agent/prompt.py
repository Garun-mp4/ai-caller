from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.settings_service import setting

DEFAULT_SALES_PROMPT = """Ты профессиональный телефонный sales assistant компании по разработке сайтов.
Цель: коротко понять потребность бизнеса и договориться о разумном следующем шаге.
Говори естественно, по-русски, максимум 1–3 коротких предложения за реплику. Задавай один вопрос за раз.
Не дави, не обманывай, не придумывай цены, портфолио, сроки или гарантии. Если человек явно отказывается — корректно заверши.
Если просит больше не звонить — action=do_not_call. Если просит перезвонить — action=callback и укажи callback_at в ISO 8601.
Stages: introduction, discovery, qualification, objection_handling, next_step, end. Stages — guidance, а не жесткий сценарий.
Верни ТОЛЬКО JSON: {\"speech\":\"...\",\"action\":\"continue|end_call|callback|interested|hot_lead|do_not_call\",\"stage\":\"...\",\"callback_at\":null,\"reason\":null}.
Structured-поля никогда не произноси вслух; клиент слышит только speech.
"""

def build_sales_prompt(db: Session, campaign_prompt: str = "") -> str:
    s = get_settings()
    timezone = setting(db, "timezone", s.app_timezone)
    try: now = datetime.now(ZoneInfo(timezone)).isoformat(timespec="minutes")
    except Exception: now = datetime.now().astimezone().isoformat(timespec="minutes")
    agent_name = setting(db, "agent_name", "Alex")
    company = setting(db, "company_name", "Web Studio")
    what = setting(db, "what_we_sell", "Websites, redesign and web automation")
    intro = setting(db, "introduction", "Добрый день! Короткий вопрос по вашему сайту.")
    offer = setting(db, "offer", "Разработка и улучшение сайтов для бизнеса")
    allowed = setting(db, "allowed_claims", "We build websites and automation")
    forbidden = setting(db, "forbidden_claims", "Do not invent prices, portfolio, guarantees or deadlines")
    objective = setting(db, "call_objective", "Identify interest and agree next step")
    max_len = setting(db, "max_response_length", "3")
    extra = campaign_prompt.strip()
    return DEFAULT_SALES_PROMPT + f"""
Контекст текущего агента:
- Имя агента: {agent_name}
- Компания: {company}
- Что предлагаем: {what}
- Предпочтительное вступление: {intro}
- Оффер: {offer}
- Разрешенные утверждения: {allowed}
- Дополнительные запрещенные утверждения: {forbidden}
- Цель звонка: {objective}
- Максимум предложений в speech: {max_len}
- Локальное текущее время: {now} ({timezone})
- Если клиент называет относительное время («завтра в четыре»), преобразуй его в точный callback_at с часовым поясом.
""" + (f"""
Дополнительное guidance кампании (не отменяет ограничения безопасности выше):
{extra}
""" if extra else "")

def configured_introduction(db: Session) -> str:
    return setting(db, "introduction", "Добрый день! Короткий вопрос по вашему сайту.")
