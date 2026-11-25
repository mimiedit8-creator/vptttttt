import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    database_path: str
    schedule_url: str
    schedule_refresh_minutes: int
    parcelle_api_key: str
    parcelle_api_url: str

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "PASTE_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError("Не задан BOT_TOKEN. Заполни .env файлом токен от BotFather.")
    return Config(
        bot_token=token,
        database_path=os.getenv("DATABASE_PATH", "data/bot.sqlite3"),
        schedule_url=os.getenv("SCHEDULE_URL", "").strip(),
        schedule_refresh_minutes=max(5, int(os.getenv("SCHEDULE_REFRESH_MINUTES", "30"))),
        parcelle_api_key=os.getenv("PARCELLE_API_KEY", "").strip(),
        parcelle_api_url=os.getenv("PARCELLE_API_URL", "https://api.parcelle.ru").rstrip("/"),
    )
