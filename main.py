import asyncio
import os
import logging
import re 
from datetime import datetime, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, BaseFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from cachetools import TTLCache

from price_scraper import PriceScraperService

# ==========================================
# 1. ЗАВАНТАЖЕННЯ НАЛАШТУВАНЬ
# ==========================================
load_dotenv() 

TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS_STR = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [int(uid.strip()) for uid in ALLOWED_USERS_STR.split(",") if uid.strip()]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ANALOGS_CACHE = TTLCache(maxsize=1000, ttl=3600)

class IsAllowedUser(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id in ALLOWED_USERS

# ==========================================
# 2. ІНІЦІАЛІЗАЦІЯ БОТА ТА ФОНОВИХ ЗАВДАНЬ
# ==========================================
bot = Bot(token=TOKEN)
dp = Dispatcher()
dp.message.filter(IsAllowedUser())

scraper_service = None
active_requests = 0

async def scheduled_restart():
    """Фонове завдання: перезавантажує браузер раз на 2 дні о 03:00 ночі для очищення пам'яті."""
    while True:
        now = datetime.now()
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"⏳ Наступна перевірка для рестарту Chrome через {wait_seconds / 3600:.1f} годин")
        await asyncio.sleep(wait_seconds)
         
        logger.info("🔄 Планове перезавантаження браузера (очищення пам'яті)...")
        if scraper_service:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(scraper_service.executor, scraper_service.restart_browser)
        logger.info("✅ Браузер успішно перезавантажено!")
        
        await asyncio.sleep(24 * 3600)

def format_dict_results(data_dict):
    """Форматує словник з пропозиціями у єдиний текст без дублювання назв."""
    lines = []
    for brand_art, offers in data_dict.items():
        lines.append(brand_art)
        lines.extend(offers)
        lines.append("") 
    return "\n".join(lines).strip()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("✅ Привіт! Бот для пошуку цін готовий.\nПросто відправ мені артикул (або кілька через кому/пробіл).")

@dp.message(F.text)
async def handle_article_search(message: types.Message):
    global active_requests 
    
    if message.text.startswith('/'): return
    
    cyrillic = "АВЕКМНОРСТХІУуавекмнорстхі"
    latin    = "ABEKMHOPCTXIYyabekmhopctxi"
    layout_map = str.maketrans(cyrillic, latin)
    
    fixed_text = message.text.translate(layout_map).upper()
    
    raw_articles = re.split(r'[,\n/.;|]', fixed_text)
    articles = [art.strip() for art in raw_articles if art.strip()]
    
    if not articles:
        return await message.answer("❌ Я не знайшов дійсних артикулів у вашому повідомленні.")
        
    if len(articles) > 10:
        return await message.answer("⚠️ Будь ласка, надсилайте не більше 10 артикулів за один раз.")
        
    if len(articles) > 1:
        await message.answer(f"📥 Отримано {len(articles)} артикулів. Починаю обробку по черзі...")

    for article in articles:
        queue_position = active_requests + 1
        
        if active_requests > 0:
            wait_time = active_requests * 15
            queue_msg = f"\n\n🚦 **Ви {queue_position}-й у черзі.**\nОрієнтовний час очікування: ~{wait_time} сек."
        else:
            queue_msg = ""
            
        msg = await message.answer(f"💰 Шукаю ціни для `{article}`...\n⏳ Зачекайте кілька секунд.{queue_msg}", parse_mode="Markdown")
        
        active_requests += 1
        
        try:
            fps_task = asyncio.create_task(scraper_service.search_fps(article))
            fourcars_task = asyncio.create_task(scraper_service.search_fourcars(article))
            inside_task = asyncio.create_task(scraper_service.search_inside(article))
            autonova_task = asyncio.create_task(scraper_service.search_autonova(article))
            
            fps_res, fourcars_res, inside_res, autonova_res = await asyncio.gather(fps_task, fourcars_task, inside_task, autonova_task)
            
            # --- ФОРМУВАННЯ ПОВІДОМЛЕННЯ ---
            reply = f"🔎 **Запит:** `{article}`\n\n➖➖➖➖➖➖➖➖➖➖\n\n"
            
            # Autonova-D
            reply += f"🛒 AUTONOVAD\u200B.\u200BUA\n\n"
            if autonova_res["exact"]:
                reply += format_dict_results(autonova_res["exact"])
            else:
                reply += "❌ Деталь не знайдена."
            if autonova_res["analogs"]:
                reply += "\n\n♻️ *Є АНАЛОГИ*"
            
            reply += "\n\n➖➖➖➖➖➖➖➖➖➖\n\n"
            
            # Forma Parts
            reply += f"🛒 B2B\u200B.\u200BFORMA-PARTS\u200B.\u200BUA\n\n"
            if fps_res["exact"]:
                reply += format_dict_results(fps_res["exact"])
            else:
                reply += "❌ Деталь не знайдена."
            if fps_res["analogs"]:
                reply += "\n\n♻️ *Є АНАЛОГИ*"
            
            reply += "\n\n➖➖➖➖➖➖➖➖➖➖\n\n"
            
            # 4cars
            reply += f"🛒 4CARS\u200B.\u200BCOM\u200B.\u200BUA\n\n"
            if fourcars_res["exact"]:
                reply += format_dict_results(fourcars_res["exact"])
            else:
                reply += "❌ Деталь не знайдена."
            if fourcars_res["analogs"]:
                reply += "\n\n♻️ *Є АНАЛОГИ*"
            
            reply += "\n\n➖➖➖➖➖➖➖➖➖➖\n\n"
            
            # Inside-Auto
            reply += f"🛒 INSIDE-AUTO\u200B.\u200BCOM\n\n"
            if inside_res["exact"]:
                reply += format_dict_results(inside_res["exact"])
            else:
                reply += "❌ Деталь не знайдена."
            if inside_res["analogs"]:
                reply += "\n\n♻️ *Є АНАЛОГИ*"
                
            # Блок зі списком аналогів для кнопки
            analogs_parts = []
            if autonova_res["analogs"]:
                analogs_parts.append(f"🛒 AUTONOVAD\u200B.\u200BUA\n\n" + format_dict_results(autonova_res["analogs"]))
            if fps_res["analogs"]:
                analogs_parts.append(f"🛒 B2B\u200B.\u200BFORMA-PARTS\u200B.\u200BUA\n\n" + format_dict_results(fps_res["analogs"]))
            if fourcars_res["analogs"]:
                analogs_parts.append(f"🛒 4CARS\u200B.\u200BCOM\u200B.\u200BUA\n\n" + format_dict_results(fourcars_res["analogs"]))
            if inside_res["analogs"]:
                analogs_parts.append(f"🛒 INSIDE-AUTO\u200B.\u200BCOM\n\n" + format_dict_results(inside_res["analogs"]))
                
            markup = None
            if analogs_parts:
                ANALOGS_CACHE[article] = "\n\n➖➖➖➖➖➖➖➖➖➖\n\n".join(analogs_parts)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Показати аналоги ♻️", callback_data=f"analogs:{article}")]
                ])
                
            await msg.edit_text(reply, reply_markup=markup, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Помилка цін для {article}: {e}")
            await msg.edit_text(f"❌ Помилка при зборі цін для `{article}`. Спробуйте ще раз.", parse_mode="Markdown")
        finally:
            active_requests -= 1
            
        if len(articles) > 1:
            await asyncio.sleep(1.5)

@dp.callback_query(F.data.startswith("analogs:"))
async def show_analogs(callback: CallbackQuery):
    await callback.answer() 
    article = callback.data.split(":")[1]
    analogs_text = ANALOGS_CACHE.get(article)
    
    if analogs_text:
        header = f"➖➖➖➖➖➖➖➖➖➖\n♻️ *АНАЛОГИ ДЛЯ {article}*\n➖➖➖➖➖➖➖➖➖➖\n\n"
        full_reply = header + analogs_text
        
        await callback.message.answer(full_reply, parse_mode="Markdown")
        
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e: 
            logger.warning(f"Не вдалося прибрати кнопку: {e}")
            
    else:
        await callback.answer("⏳ Дані аналогів видалені з пам'яті (пройшла 1 година). Зробіть пошук заново.", show_alert=True)

# ==========================================
# 3. ТОЧКА ВХОДУ (ЗАПУСК)
# ==========================================
async def main():
    global scraper_service
    logger.info("Бот запускається... Відкриваю броньований Chrome 🛡️")
    
    scraper_service = await asyncio.to_thread(PriceScraperService)
    asyncio.create_task(scheduled_restart())
    
    logger.info("✅ Chrome готовий! Бот слухає повідомлення.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())