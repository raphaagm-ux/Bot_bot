import asyncio
import logging
import os
import re
import signal
import hashlib
import hmac
from collections.abc import Iterable

from aiohttp import web
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("nue-wellness-bots")

COMMUNITY_URL = "https://t.me/NueMeNuewellness"
MENU = ReplyKeyboardMarkup(
    [
        ["Programs & Pricing", "Order / Reorder"],
        ["FAQ", "Guides"],
        ["Support / Contact", "Community"],
        ["Website"],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Choose an option or type a question",
)


def setting(name: str) -> str:
    return os.getenv(name, "").strip()


def configured_link(label: str, env_name: str, fallback: str) -> str:
    value = setting(env_name)
    if value.startswith(("https://", "http://", "tg://")):
        return f"{label}: {value}"
    return fallback


def support_text() -> str:
    username = setting("SUPPORT_USERNAME").lstrip("@")
    if username and re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        return f"Need help from a person? Message our support team: https://t.me/{username}"
    return "Need help from a person? Please reply with your name, order reference (if any), and what you need help with. A team member can follow up when support contact details are configured."


WELCOME = (
    "Welcome to Nuè Wellness. I can help you explore programs, view pricing, "
    "order or reorder, find guides, and reach support.\n\n"
    "Choose an option below to get started."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME, reply_markup=MENU)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("What would you like help with?", reply_markup=MENU)


def response_for(text: str) -> str:
    normalized = " ".join(text.lower().split())

    urgent_terms = ("can't breathe", "cannot breathe", "chest pain", "overdose", "suicidal", "emergency")
    if any(term in normalized for term in urgent_terms):
        return (
            "This may need urgent help. Please contact your local emergency services now. "
            "If you may harm yourself, contact a local crisis service or a trusted person who can stay with you. "
            "This bot cannot provide emergency care."
        )

    routes: list[tuple[Iterable[str], str]] = [
        (("program", "programs", "pricing", "price", "cost"),
         setting("PROGRAMS_PRICING_TEXT") or
         "Program options and prices may vary. Current details have not been added to this bot yet. Please choose Support / Contact for confirmed options and pricing."),
        (("order", "buy", "purchase", "reorder", "refill"),
         configured_link("Order or reorder here", "ORDER_URL",
                         "The order link has not been added yet. Please choose Support / Contact and the team will help you order or reorder.")),
        (("faq", "question", "questions"),
         setting("FAQ_TEXT") or
         "Common topics include choosing a program, ordering, delivery, account help, and using your guide. For personal health or treatment questions, please contact a qualified healthcare professional."),
        (("guide", "guides", "instructions", "how to"),
         configured_link("View the Nuè Wellness guides", "GUIDES_URL",
                         "The guides link has not been added yet. Please choose Support / Contact to request the right guide.")),
        (("support", "contact", "help", "human", "agent"), support_text()),
        (("community", "group", "telegram group"), f"Join the Nuè Wellness community: {COMMUNITY_URL}"),
        (("website", "site", "web page"),
         configured_link("Visit the Nuè Wellness website", "WEBSITE_URL",
                         "The official website link has not been added yet. Please use Support / Contact for verified information.")),
    ]
    for keywords, response in routes:
        if any(keyword in normalized for keyword in keywords):
            return response

    wellness_terms = (
        "symptom", "diagnose", "diagnosis", "dose", "dosage", "medicine", "medication",
        "treatment", "side effect", "pain", "pregnant", "allergy", "weight loss",
    )
    if any(term in normalized for term in wellness_terms):
        return (
            "I can share general Nuè Wellness information, but I cannot diagnose conditions, "
            "recommend treatment, or tell you what medication or dosage to use. Please contact a qualified "
            "healthcare professional for personal medical advice. If this feels urgent, contact local emergency services."
        )

    greetings = ("hi", "hello", "hey", "good morning", "good afternoon", "good evening")
    if normalized in greetings:
        return WELCOME

    return (
        "I’m not sure which option you need. Choose a menu button below, or type programs, order, "
        "FAQ, guides, support, community, or website."
    )


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.text:
        return
    await update.effective_message.reply_text(response_for(update.effective_message.text), reply_markup=MENU)


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("help", menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    return application


async def run() -> None:
    bot_tokens = {
        "Wellnsscouch": setting("WELLNSSCOUCH_BOT_TOKEN"),
        "Nueyounue": setting("NUEYOUNUE_BOT_TOKEN"),
    }
    missing = [name for name, token in bot_tokens.items() if not token]
    if missing:
        raise RuntimeError(f"Missing bot token environment variables for: {', '.join(missing)}")
    if len(set(bot_tokens.values())) != len(bot_tokens):
        raise RuntimeError("Each Telegram bot must use a different token")

    external_url = setting("RENDER_EXTERNAL_URL") or setting("WEBHOOK_BASE_URL")
    if not external_url.startswith("https://"):
        raise RuntimeError("RENDER_EXTERNAL_URL or WEBHOOK_BASE_URL must be a public HTTPS URL")

    applications = {
        name: {
            "application": build_application(token),
            "secret": hashlib.sha256(f"nue-webhook:{token}".encode()).hexdigest(),
            "path": name.lower(),
        }
        for name, token in bot_tokens.items()
    }
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    async def receive_update(request: web.Request) -> web.Response:
        name = request.match_info["bot_name"]
        config = applications.get(name)
        if config is None:
            raise web.HTTPNotFound()
        supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(supplied_secret, config["secret"]):
            raise web.HTTPForbidden()
        try:
            payload = await request.json()
            update = Update.de_json(payload, config["application"].bot)
        except Exception:
            logger.warning("Rejected malformed Telegram update for %s", name)
            raise web.HTTPBadRequest()
        await config["application"].update_queue.put(update)
        return web.Response(text="ok")

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bots": len(applications)})

    server = web.Application(client_max_size=1024 * 1024)
    server.router.add_get("/", health)
    server.router.add_get("/health", health)
    server.router.add_post("/telegram/{bot_name}", receive_update)
    runner = web.AppRunner(server)

    try:
        for name, config in applications.items():
            application = config["application"]
            await application.initialize()
            await application.start()
            webhook_url = f"{external_url.rstrip('/')}/telegram/{config['path']}"
            await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES,
                secret_token=config["secret"],
            )
            logger.info("Started %s bot webhook", name)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(setting("PORT") or "10000"))
        await site.start()
        logger.info("Web service is ready")
        await stop_event.wait()
    finally:
        await runner.cleanup()
        for name, config in reversed(list(applications.items())):
            application = config["application"]
            if application.running:
                await application.stop()
            await application.shutdown()
            logger.info("Stopped %s bot", name)


if __name__ == "__main__":
    asyncio.run(run())

