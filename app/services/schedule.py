import logging
from html import escape
from datetime import date, timedelta
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

LOG = logging.getLogger(__name__)
STUDENT_PAGE = "https://volpt.ru/студентам"

async def discover_schedule_url(session, configured_url=""):
    if configured_url:
        return configured_url
    try:
        async with session.get(STUDENT_PAGE, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            label = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
            if "распис" in label:
                return urljoin(STUDENT_PAGE, a["href"])
    except Exception:
        LOG.exception("Не удалось найти ссылку на расписание")
    return ""

async def fetch_schedule_html(session, url):
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as response:
        response.raise_for_status()
        return await response.text()

def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    found = []
    for table in tables:
        text = table.get_text("\n", strip=True)
        if "РКЛ-3" in text.upper():
            found.append(text)
    if not found:
        raise ValueError("На странице не найдена HTML-таблица с группой РКЛ-3")
    return "\n\n".join(found)[:12000]

async def refresh_schedule(db, configured_url):
    async with aiohttp.ClientSession(headers={"User-Agent": "VPT-RKL3-Bot/1.0"}) as session:
        url = await discover_schedule_url(session, configured_url)
        if not url:
            raise RuntimeError("Не удалось автоматически найти ссылку. Укажи SCHEDULE_URL в .env")
        html = await fetch_schedule_html(session, url)
    body = parse_schedule(html)
    today = date.today()
    # Храним один подтверждённый блок источника; не размножаем его по дням.
    await db.set_schedule("raw", body)
    await db.set_schedule("source", url)
    return body

async def get_cached_schedule(db):
    row = await db.get_schedule("raw")
    if not row:
        return "Расписание пока не загружено. Нажми «🔄 Обновить» позже."
    return escape(f"Расписание РКЛ-3 (данные из официального источника):\n\n{row['body']}\n\nОбновлено: {row['updated_at']}")
