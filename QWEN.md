# Vitrina Parser - Project Context

## Project Overview

**Vitrina Parser** is an automated web scraper for the Russian investment projects portal [vitrina.gge.ru](https://vitrina.gge.ru). It monitors new investment projects daily and sends notifications to Telegram.

### Core Features
- **Web Scraping** - Extracts new projects from vitrina.gge.ru using Playwright (browser automation)
- **Filtering** - Filters projects by categories, regions, and publication date
- **Telegram Notifications** - Sends formatted HTML notifications about new projects
- **Scheduling** - Runs on a configurable cron schedule using APScheduler
- **SQLite Database** - Stores project data and run logs
- **Statistics** - Tracks project counts and errors

### Technology Stack

| Component | Package | Purpose |
|-----------|---------|---------|
| Browser Automation | `playwright` | Chromium-based web scraping |
| Telegram Bot | `python-telegram-bot` | Bot API for notifications |
| Scheduler | `apscheduler` | Cron-based job scheduling |
| Configuration | `pydantic-settings`, `python-dotenv` | Environment-based config |
| Logging | `loguru` | Structured logging with rotation |
| HTTP Client | `httpx` | Async HTTP requests |
| Database | `sqlite3` (built-in) | Local data persistence |

**Python Version:** 3.11+

---

## Project Structure

```
vitrina-parser/
├── src/
│   ├── main.py              # Entry point, Telegram bot setup
│   ├── config.py            # Pydantic settings from .env
│   │
│   ├── browser/
│   │   ├── session.py       # Playwright browser session manager (singleton)
│   │   └── scraper.py       # DOM parsing helpers
│   │
│   ├── services/
│   │   ├── projects.py      # Project fetching (API + DOM fallback)
│   │   ├── telegram.py      # Telegram bot message sending
│   │   └── scheduler.py     # APScheduler integration, parsing pipeline
│   │
│   ├── db/
│   │   ├── database.py      # SQLite connection & schema management
│   │   └── repository.py    # Data access layer (Project, RunLog models)
│   │
│   └── utils/
│       ├── logger.py        # Loguru configuration
│       └── formatters.py    # Telegram message formatting (HTML)
│
├── data/                    # SQLite database storage
├── logs/                    # Rotating log files (daily)
├── venv/                    # Python virtual environment
│
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── install_browser_deps.sh  # System deps installer for Playwright
├── BROWSER_SETUP.md         # Browser troubleshooting guide
└── README.md                # Main documentation
```

---

## Building and Running

### Prerequisites

```bash
# Python 3.11+
python3.11 --version

# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright Chromium
playwright install chromium

# Install system dependencies (Linux only)
chmod +x install_browser_deps.sh
sudo bash install_browser_deps.sh
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

**Required `.env` variables:**

```env
# Vitrina portal credentials
VITRINA_LOGIN=your_email@example.com
VITRINA_PASSWORD=your_password

# Telegram bot (create via @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:AAExampleToken
TELEGRAM_CHAT_ID=-1001234567890

# Filters (JSON arrays)
FILTER_CATEGORIES=["Жилые здания","Административные здания"]
FILTER_REGIONS=["Москва","Московская область"]
FILTER_DAYS_BACK=1

# Schedule (cron format, UTC)
CRON_SCHEDULE=0 6 * * *

# Optional
RUN_ON_START=false
HEADLESS=true
LOG_LEVEL=INFO
```

### Running the Application

```bash
# Standard run (bot waits for commands)
python -m src.main

# Run immediately on start (for testing)
RUN_ON_START=true python -m src.main

# Debug mode with visible browser
HEADLESS=false RUN_ON_START=true python -m src.main
```

### Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and command list |
| `/status` | Last parser run status |
| `/run_now` | Trigger parser immediately |
| `/stats` | Project statistics |
| `/help` | Help information |

---

## Database Schema

### `projects` Table
```sql
CREATE TABLE projects (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  vitrina_id      TEXT UNIQUE NOT NULL,
  expertise_num   TEXT,
  object_name     TEXT,
  expert_org      TEXT,
  developer       TEXT,
  tech_customer   TEXT,
  region          TEXT,
  category        TEXT,
  characteristics TEXT,              -- JSON
  published_at    TEXT,
  updated_at      TEXT,
  url             TEXT,
  notified_at     TEXT,
  created_at      TEXT DEFAULT (datetime('now'))
);
```

### `run_logs` Table
```sql
CREATE TABLE run_logs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  status      TEXT,              -- 'running' | 'success' | 'error'
  new_count   INTEGER DEFAULT 0,
  error_msg   TEXT
);
```

---

## Architecture Details

### Browser Session (`src/browser/session.py`)
- **Singleton pattern** - Single browser instance shared across services
- **Auto-login** - Handles authentication on vitrina.gge.ru
- **API token capture** - Intercepts Bearer tokens from API responses
- **Graceful fallback** - Alternative selectors if primary login fails

### Projects Service (`src/services/projects.py`)
- **Dual-mode fetching**:
  1. **API mode** - Uses captured Bearer token for direct API calls
  2. **DOM mode** - Falls back to browser-based scraping if API unavailable
- **Date filtering** - Filters projects by `published_at` date
- **Detail fetching** - Extracts additional data from project pages

### Scheduler Service (`src/services/scheduler.py`)
- **Pipeline**:
  1. Ensure logged in
  2. Fetch project list
  3. Filter by date
  4. For each new project:
     - Fetch details
     - Save to database
     - Send Telegram notification
     - Mark as notified
  5. Send summary
- **Error handling** - Logs errors and sends alerts to Telegram

### Repository Pattern (`src/db/repository.py`)
- **Dataclass models** - `Project`, `RunLog`
- **CRUD operations** - Type-safe database access
- **Query helpers** - Stats, recent errors, unnotified projects

---

## Development Conventions

### Code Style
- **Type hints** - Used throughout the codebase
- **Async/await** - All I/O operations are async
- **Logging** - Uses `loguru` logger via `get_logger()`
- **Error handling** - Exceptions logged with `exc_info=True`

### Logging
```python
from src.utils.logger import get_logger

logger = get_logger()
logger.info("Message")
logger.error("Error", exc_info=True)
logger.debug("Debug info")
```

### Configuration Access
```python
from src.config import get_config

config = get_config()
print(config.vitrina_url)
print(config.filter_categories)
```

### Database Usage
```python
from src.db.repository import Repository, Project

# Save project
repo.save_project(project)

# Check if known
if repo.is_known(vitrina_id):
    ...

# Get stats
stats = repo.get_stats()
```

---

## Common Issues & Solutions

### Browser Dependencies Error
**Symptom:** `libnspr4.so: cannot open shared object file`

**Solution:**
```bash
sudo bash install_browser_deps.sh
# Or manually:
sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0
```

### Login Failed
**Symptom:** `Login failed - still on login page`

**Solution:**
1. Verify credentials in `.env`
2. Run with `HEADLESS=false` to debug
3. Check/update selectors in `src/browser/session.py` (lines 88-94)

### Database Errors
**Symptom:** `No such table: projects`

**Solution:**
```bash
rm data/vitrina.db  # Will be recreated on next run
```

### Telegram Not Receiving Messages
**Solution:**
1. Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
2. Ensure bot is added to the chat (if group)
3. Check logs: `grep "Error sending" logs/parser-*.log`

---

## Useful Commands

```bash
# View logs in real-time
tail -f logs/parser-$(date +%Y-%m-%d).log

# Check project count
sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"

# View project categories
sqlite3 data/vitrina.db "SELECT category, COUNT(*) FROM projects GROUP BY category;"

# Clear database (warning: destructive!)
sqlite3 data/vitrina.db "DELETE FROM projects; DELETE FROM run_logs;"

# Test authorization
HEADLESS=false python -c "
import asyncio
from src.browser.session import SessionManager
async def test():
    session = SessionManager()
    await session.initialize()
    await session.login()
    print('✅ Login successful!')
    await session.close()
asyncio.run(test())
"
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/main.py` | Entry point, Telegram bot command handlers |
| `src/config.py` | Pydantic settings, JSON parsing for filters |
| `src/browser/session.py` | Playwright singleton, login, token capture |
| `src/services/projects.py` | Project fetching logic (API + DOM) |
| `src/services/scheduler.py` | Cron scheduling, parsing pipeline |
| `src/db/repository.py` | Data models and database operations |
| `src/utils/formatters.py` | Telegram HTML message formatting |
| `.env.example` | Environment variable template |
| `BROWSER_SETUP.md` | Browser dependency troubleshooting |

---

## Notes for AI Assistants

1. **DOM Selectors May Need Updates** - If vitrina.gge.ru changes its HTML structure, update selectors in `session.py` and `projects.py`

2. **Singleton Pattern** - `SessionManager` is a singleton; don't create multiple instances

3. **Async Context** - All browser and HTTP operations require async context

4. **Graceful Shutdown** - The app handles SIGINT/SIGTERM for clean shutdown

5. **Testing** - Use `RUN_ON_START=true HEADLESS=false` for interactive debugging

6. **API Token** - The Bearer token is captured from API responses; if this fails, DOM parsing is used as fallback
