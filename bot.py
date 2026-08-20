import os

from aiohttp import web

from aiogram import Bot, Dispatcher, Router
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


BOT_TOKEN = os.environ["BOT_TOKEN"]
TALLY_URL = os.environ["TALLY_URL"]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

dp.include_router(router)


@router.message(CommandStart())
async def start_handler(message: Message):

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

    photo = FSInputFile("images/welcome.jpg")

    text = """
<b>Політ нормальний?</b>

Пропоную перевірити, хто сьогодні тримає кермо вашого життя і бізнесу.

✈️ 10 запитань
⏱ близько 3 хвилин

Тут немає правильних відповідей.
Важлива лише чесність із собою.
"""

    await message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def health(request):
    return web.Response(
        text="Bot is running",
        status=200
    )


def main():

    app = web.Application()

    # Перевірка Render
    app.router.add_get("/", health)

    # Telegram webhook
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    ).register(
        app,
        path="/webhook"
    )

    setup_application(
        app,
        dp,
        bot=bot
    )

    port = int(os.environ.get("PORT", "10000"))

    print(f"Starting server on 0.0.0.0:{port}")

    web.run_app(
        app,
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":
    main()
