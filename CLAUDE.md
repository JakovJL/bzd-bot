# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

BZD Bot is a Telegram bot (Russian/Belarusian UI) for buying Belarusian Railway (БЖД) train tickets. It is a demo/diploma project: railway data is mocked and payment is simulated. Built on **aiogram 3.x** (async) with **SQLite** storage.

## Commands

All commands run from the project root with the venv active (`.\venv\Scripts\Activate.ps1`).

```powershell
# Run the bot
python -m bot.main          # or: .\run.bat

# Run all tests
python -m unittest discover tests/

# Run a single test module / case
python -m unittest tests.test_booking
python -m unittest tests.test_booking.TestBooking.test_search_routes

# First-time setup (creates venv, installs deps, scaffolds .env)
.\setup.ps1
```

Requires `.env` with `BOT_TOKEN` (from @BotFather) and `ADMIN_IDS` (comma-separated Telegram IDs). `Config.validate()` aborts startup if `BOT_TOKEN` is missing.

## Architecture

**Entry point** ([bot/main.py](bot/main.py)): validates config → sets up logging (file + stdout) → creates `Bot` + `Dispatcher` with `MemoryStorage` → registers `LoggingMiddleware` → includes all routers → starts `NotificationScheduler` → begins long-polling.

**Router aggregation**: every handler module exposes a module-level `router = Router()`. [bot/handlers/__init__.py](bot/handlers/__init__.py) collects them via `get_all_routers()`. **When adding a new handler module, you must register its router in that list** or it will never receive updates. Router order matters — earlier routers match first.

**Multi-step flows use aiogram FSM.** State groups live in [bot/states/booking.py](bot/states/booking.py): `BookingState` (the ~8-step purchase flow: origin → destination → date → train → wagon → seat → passenger data → confirm), `WaitlistState`, `ReviewState`. Handlers transition state with `state.set_state(...)` and stash data in `state.update_data(...)`.

**Data layer is raw SQL, no ORM.** A single global `db` instance ([bot/database.py](bot/database.py)) creates all tables on import and hands out connections via `with db.get_connection() as conn:` (rows come back as `sqlite3.Row`). There is **no repository abstraction** — handlers and the scheduler write SQL inline. Tables: `users`, `routes`, `orders`, `tickets`, `waitlist`, `reviews`. Order lifecycle: `status` goes `pending` → `paid`; tickets have `is_active` toggled on refund.

**Mock railway "API"** ([bot/services/bzd_mock.py](bot/services/bzd_mock.py)): `BZDMockService` is the source of truth for routes/seats — 5 hardcoded `ROUTES` and a `STATIONS` list. **Seat occupancy is randomized on every `search_routes()` call** (`random.sample`), so availability is not stable between calls. There is no real persistence of which seats are taken.

**Background jobs** ([bot/services/scheduler.py](bot/services/scheduler.py)): `NotificationScheduler` (APScheduler `AsyncIOScheduler`) runs two interval jobs — trip reminders (every 10 min) and waitlist auto-purchase (every 5 min). It is constructed with a `bot_send_message` callback rather than holding the `Bot` directly. The waitlist checker creates `pending` orders and DMs the user when a seat opens.

**Other services**: `pdf_generator.py` (reportlab ticket PDFs into `tickets/`), `qr_service.py` (qrcode), wired together at payment confirmation.

**Models** ([bot/models/](bot/models/)) are plain dataclasses (`Route`, `Wagon`, `User`, `Order`, `Ticket`) used for in-memory shaping, distinct from the SQLite schema.

## Conventions

- All user-facing strings are Russian/Belarusian and use Telegram **HTML** parse mode (`<b>`, `<i>`). The bot is constructed with `ParseMode.HTML` globally.
- Keyboards are split: [bot/keyboards/reply.py](bot/keyboards/reply.py) (reply keyboards) and [bot/keyboards/inline.py](bot/keyboards/inline.py) (inline buttons + callback data).
- Tests use stdlib `unittest` and exercise services directly (e.g. `BZDMockService`), not the Telegram layer.

## Known caveats (per README)

- Demo only: 5 mock routes, simulated payment.
- `MemoryStorage` is used for FSM — all in-flight flow state is lost on restart (README notes Redis for production).
