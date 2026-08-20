import os

from aiohttp import web

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)


# =========================
# ENV
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
BASE_URL = os.environ["BASE_URL"].rstrip("/")
TALLY_URL = os.environ["TALLY_URL"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"


# =========================
# BOT
# =========================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()
router = Router()

dp.include_router(router)


# =========================
# /start
# =========================

@router.message(CommandStart())
async def start_handler(message: Message):

    photo = FSInputFile("images/welcome.jpg")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✈️ Пройти міні-чекап",
                    url=TALLY_URL
                )
            ]
        ]
    )

    text = """
<b>Політ нормальний?</b>

Пропоную перевірити, хто сьогодні тримає кермо вашого життя і бізнесу.

Я підготувала короткий <b>міні-чекап якості польоту</b>.

✈️ 10 запитань
⏱ близько 3 хвилин

Після проходження ви побачите свою провідну зону та отримаєте точку для рефлексії.

Тут немає правильних відповідей.
Важлива лише чесність із собою.
"""

    await message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=keyboard
    )


# =========================
# HEALTH CHECK
# =========================

async def health_check(request):
    return web.Response(text="Bot is running")


# =========================
# WEBHOOK
# =========================

async def on_startup(bot: Bot):
    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=dp.resolve_used_update_types()
    )

    print(f"Webhook set: {WEBHOOK_URL}")


dp.startup.register(on_startup)


# =========================
# SERVER
# =========================

def main():

    app = web.Application()

    app.router.add_get("/", health_check)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET
    ).register(
        app,
        path=WEBHOOK_PATH
    )

    setup_application(
        app,
        dp,
        bot=bot
    )

    port = int(os.environ.get("PORT", 10000))

    web.run_app(
        app,
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":
    main()