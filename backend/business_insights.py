import os
from dotenv import load_dotenv
from google import genai
from fastapi import APIRouter
from pydantic import BaseModel

load_dotenv()

insights_router = APIRouter(prefix="/api/insights", tags=["5. Business Insights"])

try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    MODEL_ID = "models/gemini-2.5-flash"
except Exception as e:
    client = None
    print(f"Помилка ініціалізації клієнта Gemini: {e}")


class RFMRequest(BaseModel):
    business_type: str
    cluster_name: str
    recency: float
    frequency: float
    monetary: float


class FPGrowthRequest(BaseModel):
    business_type: str
    item_a: str
    item_b: str
    confidence: float


def rule_based_rfm_fallback(cluster_name: str, business_type: str) -> str:
    if "Champions" in cluster_name or "1" in cluster_name:
        return "Запропонуйте преміальний статус та ексклюзивні умови обслуговування. Надішліть персональне привітання від керівника компанії."
    elif "Risk" in cluster_name or "3" in cluster_name:
        return "Надішліть знижку двадцять відсотків на категорію товарів, яку клієнт купував раніше. Запропонуйте телефонний дзвінок для з'ясування причин відсутності активності."
    else:
        return "Надішліть добірку найпопулярніших товарів вашої ніші. Запропонуйте безкоштовну доставку при наступному замовленні."


def rule_based_fp_fallback(item_a: str, item_b: str, confidence: float) -> str:
    return f"Створіть акційний набір із товарів «{item_a}» та «{item_b}» зі знижкою десять відсотків. Розмістіть банер про спільну покупку цих товарів на головній сторінці сайту."


@insights_router.post("/rfm")
async def generate_rfm_insight(req: RFMRequest):
    prompt = f"""
    Ти — провідний стратег з електронної комерції. Ніша бізнесу: "{req.business_type}".
    Ти аналізуєш результати кластеризації.

    Дані сегмента клієнтів:
    - Назва кластера: {req.cluster_name}
    - Давність покупки: {req.recency} днів
    - Частота замовлень: {req.frequency}
    - Середній чек: {req.monetary} грн.

    Завдання:
    Напиши маркетингові поради для цього сегмента.

    Суворі правила оформлення відповіді (порушення критичне):
    1. Текст має складатися рівно з двох речень. Одне речення описує одну пораду. 
    2. Не використовуй жодних списків, маркерів, цифр чи абзаців. Текст повинен йти суцільним рядком із двох речень.
    3. Повністю заборонено використовувати будь-які англійські слова чи абревіатури.
    4. Категорично заборонено використовувати жирний шрифт або символи зірочок. Текст має бути звичайним.
    """

    if client:
        try:
            response = client.models.generate_content(model=MODEL_ID, contents=prompt)
            insight_text = response.text.strip() if response.text else ""
            insight_text = insight_text.replace("**", "").replace("*", "").replace("•", "").replace("\n", " ").strip()

            return {"insight": insight_text, "is_fallback": False}
        except Exception as e:
            print(f"Gemini API Error: {e}")

    return {"insight": rule_based_rfm_fallback(req.cluster_name, req.business_type), "is_fallback": True}


@insights_router.post("/fpgrowth")
async def generate_fpgrowth_insight(req: FPGrowthRequest):
    prompt = f"""
    Ти — провідний експерт із мерчандайзингу. Ніша бізнесу: "{req.business_type}".
    Ти аналізуєш асоціативні правила.

    Дані аналізу: 
    Користувачі, які купують товар "{req.item_a}", також купують товар "{req.item_b}" із впевненістю {req.confidence}%.

    Завдання:
    Напиши бізнес-стратегії монетизації цього зв'язку.

    Суворі правила оформлення відповіді (порушення критичне):
    1. Текст має складатися рівно з двох речень. Одне речення описує одну стратегію.
    2. Не використовуй жодних списків, маркерів, цифр чи абзаців. Текст повинен йти суцільним рядком із двох речень.
    3. Повністю заборонено використовувати англійські слова чи професійний жаргон.
    4. Категорично заборонено використовувати жирний шрифт або символи зірочок. Текст має бути звичайним.
    """

    if client:
        try:
            response = client.models.generate_content(model=MODEL_ID, contents=prompt)
            insight_text = response.text.strip() if response.text else ""
            insight_text = insight_text.replace("**", "").replace("*", "").replace("•", "").replace("\n", " ").strip()

            return {"insight": insight_text, "is_fallback": False}
        except Exception as e:
            print(f"Gemini API Error: {e}")

    return {"insight": rule_based_fp_fallback(req.item_a, req.item_b, req.confidence), "is_fallback": True}