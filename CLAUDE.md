# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**vitrina-parser** — automated web scraper for monitoring investment projects on [vitrina.gge.ru](https://vitrina.gge.ru) with Telegram notifications. It parses project details daily, applies user-defined filters (categories, regions, expertise years), and sends notifications to a Telegram chat.

**Key Technologies:**
- **Scraping:** Playwright (headless Chromium browser)
- **Async:** asyncio + python-telegram-bot
- **Scheduling:** APScheduler (cron-based)
- **Database:** SQLite with custom Repository pattern
- **Logging:** loguru with daily rotation

## Development Commands

### Setup & Installation
```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure environment
cp .env.example .env
nano .env  # Set VITRINA_LOGIN, VITRINA_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### Running the Application
```bash
# Start the bot (listens for Telegram commands, runs scheduler)
python -m src.main

# Run parser immediately (via /run_now Telegram command or programmatically)
# Parser runs inside the scheduler service

# Run parser STANDALONE (without bot)
python run_parser_standalone.py

# Run parser standalone with DEBUG logging
LOG_LEVEL=DEBUG python run_parser_standalone.py

# Debug: visible browser + run on start
HEADLESS=false RUN_ON_START=true python -m src.main

# Debug: standalone mode with visible browser
HEADLESS=false python run_parser_standalone.py
```

### Database & Debugging
```bash
# Check database state
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./data/vitrina.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM projects")
print(f"Projects: {cursor.fetchone()[0]}")
conn.close()
EOF

# View logs
tail -f logs/parser-$(date +%Y-%m-%d).log

# Clear parsing results (projects table only)
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./data/vitrina.db')
conn.execute("DELETE FROM projects")
conn.execute("DELETE FROM run_logs")
conn.commit()
conn.close()
EOF
```

## Architecture & Data Flow

### High-Level Flow
1. **Telegram Bot** (`main.py`) — listens for `/start`, `/run_now`, `/status`, `/stats`, `/admin` commands
2. **Scheduler** (`services/scheduler.py`) — runs parser on cron schedule (default 6 AM UTC)
3. **Projects Service** (`services/projects.py`) — fetches list + intelligent detail parsing
4. **Database** (`db/database.py`, `db/repository.py`) — SQLite with schema + CRUD operations
5. **Telegram Service** (`services/telegram.py`) — formats and sends notifications

### Core Components

#### **SessionManager** (`browser/session.py`)
- Manages Playwright browser session (Chromium)
- Handles login to vitrina.gge.ru (email + password)
- Provides `goto()`, `page.evaluate()` for DOM scraping
- Auto-retries on 401 (re-authenticates)
- **Key methods:**
  - `ensure_logged_in()` — login with credentials caching
  - `goto(url)` — navigate with `wait_until="networkidle"`
  - `page.evaluate(js_code)` — run arbitrary JS in browser context

#### **ProjectsService** (`services/projects.py`)
- `fetch_list()` — get projects from `/projects/search` API (returns id, name only)
- `fetch_details(url)` — parse project page via `page.evaluate(JS_EXTRACT_PAIRS)`
  - Extracts label-value pairs from multiple HTML structures (tables, dl/dd, divs)
  - Maps Russian labels to Project dataclass fields via `LABEL_MAPPING` dict
  - Collects unmapped fields in `characteristics` dict
- `filter_by_last_run()` — keep only projects published after last successful run
- `filter_by_expertise_year()` — filter by expertise year range (extracted from expertise_num)

**Key Data:** Returns `List[Project]` dataclass with fields:
- `vitrina_id`, `expertise_num`, `object_name`, `expert_org`, `developer`, `tech_customer`, `region`, `category`, `characteristics`, `url`, `published_at`, `updated_at`

#### **SchedulerService** (`services/scheduler.py`)
- APScheduler with cron trigger (configurable from settings)
- `run_parser()` — main pipeline:
  1. Fetch project list
  2. Filter by last run date + expertise year
  3. For each new project:
     - Fetch details via `ProjectsService.fetch_details()`
     - **Merge details into project object** (apply extracted fields + characteristics)
     - Save to database
     - Send Telegram notification
     - Mark as notified
- `run_immediately()` — run outside schedule (called by /run_now)

#### **Repository** (`db/repository.py`)
- SQLite CRUD for projects, run_logs, parser_settings, admins
- **Key methods:**
  - `save_project(project)` — INSERT OR IGNORE (vitrina_id is unique)
  - `is_known(vitrina_id)` — check if project already in DB
  - `get_stats()` — count total, notified, today's projects
  - `get_all_settings()` — deserialize settings from DB (JSON arrays, ints)
  - Settings: filter_categories, filter_regions, expertise_year_from/to, last_successful_run, cron_schedule, run_on_start

#### **TelegramService** (`services/telegram.py`)
- Sends notifications to TELEGRAM_CHAT_ID
- `send_notification(message)` — formatted project summary
- `send_alert(error_msg)` — error notifications

#### **AdminPanelService** (`services/admin_panel.py`)
- Inline keyboard menu for /admin command
- Allows admins to modify filters, schedule, manage admins
- Returns telegram.ext handlers for integration with main app

### Database Schema

**projects** — stores parsed project data
- `id` (PK), `vitrina_id` (UNIQUE), `expertise_num`, `object_name`, `expert_org`, `developer`, `tech_customer`, `region`, `category`, `characteristics` (JSON), `published_at`, `updated_at`, `url`, `notified_at`, `created_at`

**run_logs** — tracks each parser execution
- `id` (PK), `started_at`, `finished_at`, `status` ('success'|'error'), `new_count`, `error_msg`

**parser_settings** — key-value store for filters and schedule
- `id` (PK), `key` (UNIQUE), `value`, `description`, `updated_at`
- Example keys: `filter_categories`, `filter_regions`, `expertise_year_from`, `expertise_year_to`, `last_successful_run`, `cron_schedule`, `run_on_start`

**admins** — Telegram user IDs with admin access
- `id` (PK), `telegram_id` (UNIQUE), `username`, `created_at`

## Common Development Tasks

### Adding a New Filter Type
1. Add setting to `ParserSettings` dataclass in `db/repository.py`
2. Update `get_all_settings()` and `save_settings()` to deserialize/serialize
3. Add to admin panel in `services/admin_panel.py` (menu + callback)
4. Apply filter in `services/scheduler.py` `run_parser()` method

### Fixing DOM Parsing Issues
If vitrina.gge.ru changes HTML structure:
1. **Login selectors** → update `src/browser/session.py` (login form, email/password inputs, submit button)
2. **Project list parsing** → update `src/services/projects.py` `_fetch_via_dom()` (table rows, links)
3. **Project detail parsing** → update `JS_EXTRACT_PAIRS` constant in `src/services/projects.py`
   - Add new CSS selectors for additional HTML structures
   - Update `LABEL_MAPPING` to include new Russian label variants
   - Test with `page.evaluate(JS_EXTRACT_PAIRS)` in browser DevTools

### Testing Detail Parsing Locally
```python
# In Python REPL
from src.browser.session import SessionManager
from src.services.projects import ProjectsService

session = SessionManager()
session.initialize()  # async, run with asyncio
projects_service = ProjectsService(session)

# Fetch and parse a specific project URL
details = await projects_service.fetch_details("https://vitrina.gge.ru/projects/12345")
print(details)  # Should show expertise_num, developer, characteristics, etc.
```

### Monitoring in Production
- **Telegram bot commands:** /status (last run), /stats (counts + recent errors), /run_now (manual trigger)
- **Log file:** `logs/parser-YYYY-MM-DD.log` (daily rotation, configurable via LOG_LEVEL env var)
- **Database queries:** Check `run_logs` for failures, `projects` for counts, `parser_settings` for current config

## Key Implementation Details

### Smart Detail Parsing (`fetch_details`)
- Uses `page.evaluate(JS_EXTRACT_PAIRS)` — runs JavaScript in browser to extract all label-value pairs
- Supports 3 HTML structures: `<tr><td>Label</td><td>Value</td></tr>`, `<dl><dt>Label</dt><dd>Value</dd></dl>`, div-pairs
- Maps Russian labels → Project fields via configurable `LABEL_MAPPING` dictionary
- Unmapped pairs go to `characteristics` dict (JSON-serialized in DB)
- Falls back gracefully if no pairs found (logs warning, continues)

### Async Architecture
- All I/O (browser, HTTP, DB, Telegram) is async
- Scheduler runs on APScheduler's AsyncIOScheduler
- Parser blocks until completion (sync within async context)
- Consider: for high volume, could parallelize detail fetching with asyncio.gather()

### Database Constraints
- `vitrina_id` is UNIQUE → INSERT OR IGNORE prevents re-parsing same project
- Foreign keys enabled (`PRAGMA foreign_keys = ON`)
- Settings are deserialized on read (JSON arrays → list, strings → int)

### Parser Logging & Observability
Comprehensive logging added for full pipeline visibility:

**Startup Parameters** (INFO level):
- Filter counts and values (categories, regions, expertise years)
- Chat IDs for notifications
- Last successful run timestamp

**Filtering Funnel** (INFO level):
- `[1/4] ПОЛУЧЕНО с сайта` — total projects fetched
- `[2/4] ПОСЛЕ фильтра по дате` — filtered count + dropped count
- `[3/4] НОВЫХ объектов для обработки` — new projects

**Project Cards** (INFO level):
- `[ОБЪЕКТ]` section with vitrina_id, name, category, region, developer, expertise, date, URL, TEPs
- `[4/4] УВЕДОМЛЕНИЕ отправлено` — notification confirmation per chat

**Parsing Details** (DEBUG level):
- Found/missing fields from sidebar cards
- Two-phase parsing results (ID-based + label-pairs)
- Characteristics count
- Date filter reasons (ОСТАВЛЕН/ОТСЕЯН)

**Run with logging:**
```bash
# INFO level (full pipeline overview)
python run_parser_standalone.py

# DEBUG level (detailed field-by-field analysis)
LOG_LEVEL=DEBUG python run_parser_standalone.py
```

## Pitfalls & Edge Cases

1. **Flood Control** — Telegram rate limiting. Bot retries 3 times with 60s delay on "Flood control" error.
2. **Browser Crashes** — Playwright may fail on system with missing dependencies. Run `BROWSER_SETUP.md` for fixes.
3. **Stale Credentials** — If portal login changes, update VITRINA_LOGIN/PASSWORD in .env and restart.
4. **Timezone Sensitivity** — Cron schedule in .env is UTC. `last_successful_run` is ISO format (no timezone hint, treated as UTC).
5. **Characteristics JSON** — Unmapped label-value pairs are stored as JSON string in DB. `Repository.save_project()` handles serialization.

## Useful References

- **README.md** — user-facing documentation, setup, Telegram commands
- **ADMIN_PANEL.md** — detailed guide for admin menu features
- **BROWSER_SETUP.md** — fixes for Playwright/Chromium system dependencies
- **IMPLEMENTATION_SUMMARY.md** — historical notes on implementation decisions
- **.env.example** — template for configuration variables

Проект русскоязычный. Отвечай по русски на запросы пользователя.