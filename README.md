# Nuè Wellness Telegram Bots

One secure Python application that runs both Nuè Wellness Telegram bots:

- `@Wellnsscouch_bot`
- `@Nueyounue_bot`

The bots share the same menu and safe automatic replies while using separate Telegram tokens. Tokens are read only from environment variables and must never be committed to GitHub. Telegram webhooks let the app run as a free Render web service.

## Features

- `/start`, `/menu`, and `/help`
- Programs and pricing
- Order and reorder
- FAQ and guides
- Support and contact routing
- Nuè Wellness community link: https://t.me/NueMeNuewellness
- Website routing
- Safe keyword replies
- Medical safety guardrails that do not diagnose, prescribe, or suggest dosages

## 1. Get both tokens safely

While signed in to Telegram as **4Ø4 | ɴøᴛ ꜰøᴜɴᴅ (`@nevrthere`)**:

1. Open the verified `@BotFather` account.
2. Use `/mybots` and select `@Wellnsscouch_bot`.
3. Open **API Token** and copy its token somewhere private.
4. Repeat for `@Nueyounue_bot`.
5. Never send tokens in Telegram groups, screenshots, support chats, or GitHub files.

If either bot belongs to another Telegram account, transfer or recreate it under the intended account before deployment. The application cannot verify bot ownership from a token-free code checkout.

## 2. Deploy on Render

This project uses a free Render web service. Render may pause a free service after 15 minutes without incoming traffic. A new Telegram message sends an incoming webhook request that wakes it again, so the first reply after a quiet period can be delayed while the service starts.

1. Sign in to [Render](https://render.com/) and connect this GitHub repository.
2. Choose **New**, then **Blueprint**, and select `raphaagm-ux/Bot_bot`.
3. Render will read `render.yaml` and create a free web service. No paid worker or payment card is required for this configuration.
4. In the worker's **Environment** settings, add these secret values:
   - `WELLNSSCOUCH_BOT_TOKEN`: token for `@Wellnsscouch_bot`
   - `NUEYOUNUE_BOT_TOKEN`: token for `@Nueyounue_bot`
5. Add only the optional values you have verified:
   - `WEBSITE_URL`
   - `ORDER_URL`
   - `GUIDES_URL`
   - `SUPPORT_USERNAME` (without `@`)
   - `PROGRAMS_PRICING_TEXT`
   - `FAQ_TEXT`
6. Deploy the web service and check its logs for `Started Wellnsscouch bot webhook`, `Started Nueyounue bot webhook`, and `Web service is ready`.
7. Open each bot in Telegram and send `/start`.

Do not put secrets into `render.yaml`. Marking token values as `sync: false` makes Render request them securely during setup. Render automatically supplies the public `RENDER_EXTERNAL_URL` used to register both Telegram webhooks.

## Run locally for testing

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally with both tokens. PowerShell does not load `.env` automatically, so set each secret in the current terminal before starting:

```powershell
$env:WELLNSSCOUCH_BOT_TOKEN="your-private-token"
$env:NUEYOUNUE_BOT_TOKEN="your-private-token"
python bot.py
```

For local webhook testing, also set `WEBHOOK_BASE_URL` to a public HTTPS tunnel URL. Press `Ctrl+C` to stop both bots.

## BotFather command menu

For each bot, use `@BotFather` → `/setcommands`, select the bot, and paste:

```text
start - Open the welcome menu
menu - Show all options
help - Get help using the bot
```

## Safe configuration behavior

Unknown website, guide, order, and support links are deliberately not guessed. If an optional value is missing, the bot gives a safe fallback and routes the user toward support. Program prices are also left unlisted until confirmed through `PROGRAMS_PRICING_TEXT`.

