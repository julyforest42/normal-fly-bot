import os
import asyncio
import logging

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

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


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]

# Наприклад:
# https://tally.so/r/XXXXXXXX
TALLY_URL = os.environ["TALLY_URL"]

# Куди веде кнопка:
# "✈️ Хочу на подарунковий розбір"
#
# Це може бути Calendly / Tally / Google Form /
# інша сторінка запису.
GIFT_REVIEW_URL = os.environ["GIFT_REVIEW_URL"]

# Render URL:
# https://normal-fly-bot.onrender.com
BASE_URL = os.environ.get(
    "BASE_URL",
    "https://normal-fly-bot.onrender.com"
).rstrip("/")

# Необов'язково.
# Якщо задасте цей secret у Render,
# такий самий треба передати з Tally
# в header X-Tally-Secret.
TALLY_WEBHOOK_SECRET = os.environ.get(
    "TALLY_WEBHOOK_SECRET",
    ""
)

# Затримка другого повідомлення
FOLLOWUP_DELAY_SECONDS = int(
    os.environ.get("FOLLOWUP_DELAY_SECONDS", "5")
)


# ============================================================
# FILES
# ============================================================

WELCOME_IMAGE = "images/welcome.jpg"
FOLLOWUP_IMAGE = "images/express_review.jpg"


# ============================================================
# BOT
# ============================================================

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

router = Router()

dp.include_router(router)


# ============================================================
# TEXTS
# ============================================================

WELCOME_TEXT = """
<b>Політ нормальний?</b>

Пропоную перевірити, хто сьогодні тримає кермо вашого життя і бізнесу.

✈️ 10 запитань
⏱ близько 3 хвилин

Тут немає правильних відповідей.
Важлива лише чесність із собою.
""".strip()


FOLLOWUP_TEXT = """
Ви щойно зробили те, на що ми часто не знаходимо часу в щоденному русі — подивилися на свій політ трохи зверху.

Я — <b>Оксана Ткачук</b>, бізнес-архітекторка, стратегічна радниця, наставниця та коуч ICF. Понад 24 роки працюю з бізнесами, командами й людьми в періоди росту, змін і складних переходів.

Міні-чекап показав, де зараз може бути ваша зона турбулентності, і запропонував маневр на найближчі 72 години.

Якщо результат відгукнувся і ви впізнали в ньому те, що вже давно забирає енергію, ясність чи відчуття керма у власних руках — запрошую вас на наступний крок.

За 30 хвилин ми знайдемо, що саме сьогодні створює вашу турбулентність, чого вона вже вам коштує, на що ви можете спертися і який один точний крок здатен змінити вашу траєкторію.

Ви вийдете з розмови не просто з усвідомленням проблеми, а з ясністю: <b>що відбувається, що з цим робити і з чого почати саме зараз.</b>

<i>«Не кожна турбулентність означає, що треба змінювати літак. Іноді потрібно лише повернути собі кермо».</i>

🎁 <b>Подарунковий «Експрес-розбір польоту» — 30 хвилин зі мною.</b>
""".strip()


# ============================================================
# HELPERS
# ============================================================

def create_personal_tally_url(chat_id: int) -> str:
    """
    Додає tg_id до URL Tally.

    Наприклад:
    https://tally.so/r/ABC123?tg_id=123456789
    """

    url_parts = urlsplit(TALLY_URL)

    query = dict(
        parse_qsl(
            url_parts.query,
            keep_blank_values=True
        )
    )

    query["tg_id"] = str(chat_id)

    new_query = urlencode(query)

    return urlunsplit(
        (
            url_parts.scheme,
            url_parts.netloc,
            url_parts.path,
            new_query,
            url_parts.fragment,
        )
    )


def extract_tg_id(fields) -> str | None:
    """
    Шукає hidden field tg_id
    серед fields, які приходять від Tally.
    """

    if not isinstance(fields, list):
        return None

    for field in fields:

        if not isinstance(field, dict):
            continue

        label = field.get("label")
        key = field.get("key")

        if label == "tg_id" or key == "tg_id":

            value = field.get("value")

            if value is None:
                return None

            # На випадок, якщо Tally поверне масив.
            if isinstance(value, list):
                if not value:
                    return None

                value = value[0]

            return str(value)

    return None


# ============================================================
# /START
# ============================================================

@router.message(CommandStart())
async def start_handler(message: Message):

    if message.chat is None:
        return

    chat_id = message.chat.id

    # Для кожної людини генерується її
    # персональне посилання на Tally.
    personal_tally_url = create_personal_tally_url(
        chat_id
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✈️ Пройти міні-чекап",
                    url=personal_tally_url
                )
            ]
        ]
    )

    photo = FSInputFile(
        WELCOME_IMAGE
    )

    await message.answer_photo(
        photo=photo,
        caption=WELCOME_TEXT,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    logger.info(
        "User %s started bot. Tally URL: %s",
        chat_id,
        personal_tally_url
    )


# ============================================================
# FOLLOW-UP AFTER TALLY
# ============================================================

async def send_followup(chat_id: int):
    """
    Надсилає другий банер + текст + кнопку.
    """

    try:

        # Чекаємо 5 секунд.
        await asyncio.sleep(
            FOLLOWUP_DELAY_SECONDS
        )

        logger.info(
            "Sending follow-up to user %s",
            chat_id
        )

        # ----------------------------------------------------
        # 1. Банер окремим повідомленням
        # ----------------------------------------------------

        photo = FSInputFile(
            FOLLOWUP_IMAGE
        )

        await bot.send_photo(
            chat_id=chat_id,
            photo=photo
        )

        # ----------------------------------------------------
        # 2. Текст + CTA-кнопка
        # ----------------------------------------------------

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✈️ Хочу на подарунковий розбір",
                        url=GIFT_REVIEW_URL
                    )
                ]
            ]
        )

        await bot.send_message(
            chat_id=chat_id,
            text=FOLLOWUP_TEXT,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        logger.info(
            "Follow-up successfully sent to %s",
            chat_id
        )

    except Exception:
        logger.exception(
            "Failed to send follow-up to %s",
            chat_id
        )


# ============================================================
# TALLY WEBHOOK
# ============================================================

# Захист від повторних webhook Tally.
#
# Якщо Tally повторно надішле той самий submission,
# другий банер двічі не прилетить.
#
# Для поточного заходу цього достатньо.
processed_submissions = set()


async def tally_webhook(request: web.Request):

    # --------------------------------------------------------
    # OPTIONAL SECURITY CHECK
    # --------------------------------------------------------

    if TALLY_WEBHOOK_SECRET:

        received_secret = request.headers.get(
            "X-Tally-Secret"
        )

        if received_secret != TALLY_WEBHOOK_SECRET:

            logger.warning(
                "Invalid Tally webhook secret"
            )

            return web.json_response(
                {
                    "ok": False,
                    "error": "unauthorized"
                },
                status=401
            )

    # --------------------------------------------------------
    # READ JSON
    # --------------------------------------------------------

    try:

        payload = await request.json()

    except Exception:

        logger.exception(
            "Invalid JSON from Tally"
        )

        return web.json_response(
            {
                "ok": False,
                "error": "invalid_json"
            },
            status=400
        )

    logger.info(
        "Tally webhook received: %s",
        payload
    )

    # --------------------------------------------------------
    # EVENT TYPE
    # --------------------------------------------------------

    event_type = payload.get(
        "eventType"
    )

    # Нас цікавить тільки завершена форма.
    if event_type and event_type != "FORM_RESPONSE":

        return web.json_response(
            {
                "ok": True,
                "ignored": True
            }
        )

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    data = payload.get(
        "data",
        {}
    )

    if not isinstance(data, dict):

        return web.json_response(
            {
                "ok": False,
                "error": "missing_data"
            },
            status=400
        )

    submission_id = data.get(
        "submissionId"
    )

    # --------------------------------------------------------
    # DUPLICATE PROTECTION
    # --------------------------------------------------------

    if submission_id:

        if submission_id in processed_submissions:

            logger.info(
                "Duplicate submission ignored: %s",
                submission_id
            )

            return web.json_response(
                {
                    "ok": True,
                    "duplicate": True
                }
            )

        processed_submissions.add(
            submission_id
        )

    # --------------------------------------------------------
    # GET tg_id
    # --------------------------------------------------------

    fields = data.get(
        "fields",
        []
    )

    tg_id = extract_tg_id(
        fields
    )

    if not tg_id:

        logger.warning(
            "Tally submission has no tg_id. Submission: %s",
            submission_id
        )

        return web.json_response(
            {
                "ok": False,
                "error": "tg_id_not_found"
            },
            status=400
        )

    # --------------------------------------------------------
    # VALIDATE tg_id
    # --------------------------------------------------------

    try:

        chat_id = int(
            tg_id
        )

    except (TypeError, ValueError):

        logger.warning(
            "Invalid tg_id: %s",
            tg_id
        )

        return web.json_response(
            {
                "ok": False,
                "error": "invalid_tg_id"
            },
            status=400
        )

    logger.info(
        "Tally submission %s belongs to Telegram user %s",
        submission_id,
        chat_id
    )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # НЕ await send_followup().
    #
    # Tally повинен отримати HTTP 200 одразу.
    # Повідомлення відправляємо окремою background task.
    # --------------------------------------------------------

    asyncio.create_task(
        send_followup(
            chat_id
        )
    )

    return web.json_response(
        {
            "ok": True
        },
        status=200
    )


# ============================================================
# HEALTH CHECK
# ============================================================

async def health(request: web.Request):

    return web.json_response(
        {
            "status": "ok",
            "message": "Bot is running"
        }
    )


# ============================================================
# STARTUP
# ============================================================

async def on_startup(bot: Bot):

    webhook_url = (
        f"{BASE_URL}/webhook"
    )

    logger.info(
        "Setting Telegram webhook: %s",
        webhook_url
    )

    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=[
            "message"
        ],
        drop_pending_updates=False
    )

    logger.info(
        "Telegram webhook set successfully"
    )


dp.startup.register(
    on_startup
)


# ============================================================
# MAIN
# ============================================================

def main():

    app = web.Application()

    # --------------------------------------------------------
    # Render health check
    # --------------------------------------------------------

    app.router.add_get(
        "/",
        health
    )

    # --------------------------------------------------------
    # Tally webhook
    # --------------------------------------------------------

    app.router.add_post(
        "/tally-webhook",
        tally_webhook
    )

    # --------------------------------------------------------
    # Telegram webhook
    # --------------------------------------------------------

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

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    logger.info(
        "Starting server on 0.0.0.0:%s",
        port
    )

    web.run_app(
        app,
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":
    main()