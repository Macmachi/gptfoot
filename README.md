# ⚽ gptfoot (Telegram/Discord bot)

## 🌐 Overview
gptfoot is a bot for Telegram and Discord, meticulously designed to track match events for clubs across multiple leagues, all while minimizing message volume. It utilizes cutting-edge AI technology (OpenRouter API with MiniMax-M3, GPT-4o, Claude, Gemini and more) to provide live match commentary. The bot offers a broad range of features, from showcasing team lineups to reporting goals, red cards, and delivering comprehensive match analyses, all backed by advanced AI capabilities. It's a game-changer for those looking to stay updated on matches in a seamless and informative way.

## 🛠 Features
* Detection of whether a team is playing a match today in different leagues
* Real-time monitoring of match events using Telegram/Discord bots powered by AI
* Integration with the api-football API for retrieving match data, predictions, and team statistics
* AI-driven match analysis with contextual awareness:
  * History of last 5 matches (richer insights)
  * **NEW v2.6.0** — Current-season statistics for the followed team in the league of the match (single API call per match, cached and reused for both pre-match and post-match LLM prompts)
* **NEW v2.6.0** — Compact season-stats summary appended after the post-match analysis (Markdown legacy compatible with Telegram & Discord)
* **NEW v2.6.0** — League type configurable via `[LEAGUE_TYPES]` (no more hard-coded league IDs in the source)
* **NEW v2.6.0** — `config.ini.example` template + `.gitignore` for safe public deployment
* Can be used with a Telegram bot, a Discord bot, or both (configurable in `config.ini`)
* Can be used with either the free or paid API from api-football (configurable in `config.ini`)
* Professional logging system with automatic rotation (max 10MB, keeps 5 backups)
* API cost tracking and reporting (transparent monitoring of AI API usage)
* Match history storage (last 5 matches) for contextual AI analysis
* Intelligent message splitting for long AI responses (respects platform limits)
* API key validation at startup with helpful error messages
* Retry mechanism with exponential backoff for improved reliability
* Enhanced error handling for network issues and API failures
* The frequency of messages is limited to ensure a pleasant experience for users
* Works with the free version of api-football (up to 100 calls per day)
* Support for dozens of languages
* Configurable AI models (OpenRouter API)

## 🆕 What's New in v2.8.2
* ✅ **Fix — Goals published in two steps are no longer missed**: api-football sometimes publishes a goal in two stages — first with the score already incremented but no scorer name, then a few minutes later with the player name. Since the score no longer changed on the second pass, the goal was silently dropped and never announced. `process_goal_event` now rescues it: if the goal's `event_key` was never sent, it is announced (deduplication via `sent_events` still guarantees uniqueness). The `score_updated` flag in `check_events` now accumulates with `or`, so a rescued goal (no score change) processed after a real goal can no longer reset the flag and block the score update. **No additional API call.**

## 🆕 What's New in v2.8.1
* ✅ **Fix — Missing venue no longer leaks `None`**: when api-football returns a null stadium and/or city for a fixture (common on some leagues), the "match today" prompt used to literally send `Stade : None, Genève` to the LLM, which then wrote "stadium not provided". The location line is now built only from the fields that actually exist (venue + city, city only, venue only, or omitted), and the model is instructed never to say the venue is missing. **No additional API call.**
* ✅ **Fix — Graceful handling of empty lineups**: on the free api-football tier, the `startXI` arrays are sometimes still empty at kickoff. Instead of dumping empty lineups into the prompt (which made the model ramble about "no lineup provided"), the bot now detects the absence of a starting XI and switches to a shorter pre-match preview (recent form + prediction only), without inventing players and without apologizing for the missing data. **No additional API call, no extra LLM call.**

## 🆕 What's New in v2.8.0
* ✅ **Fix — Infinite loop after penalty shootouts (free API)**: the shootout handler was waiting for the `PEN` status to change, but `PEN` is a **final** status (match finished after penalties) and never changes. On the free API tier this drained the daily quota and the end-of-match summary was never sent. The handler now monitors `P` (shootout in progress) and lets `PEN` be handled as a normal end of match.
* ✅ **Fix — Bot permanently dead after an API quota error**: `RateLimitExceededError` escaping from the live-event loop used to kill the daily 09:00 check task silently — the script kept running but never checked matches again until a manual restart. The daily loop now catches all exceptions and resumes the next day. A related bug was also fixed: `get_check_match_status` was swallowing `RateLimitExceededError` in its generic `except`, preventing a clean stop of the match tracking.
* ✅ **Fix — Graceful shutdown**: Ctrl+C (`SIGINT`), `kill` (`SIGTERM`) and `SIGQUIT` now log and stop the script cleanly (previously only `SIGKILL` could terminate it). `SIGHUP` is still ignored so the bot survives terminal closure under `nohup`.
* ✅ **Fix — Background tasks garbage collection**: references to all `asyncio` background tasks are now kept (the event loop only holds weak references), tasks are named, and their unhandled exceptions are logged.
* ✅ **Fix — Lost Telegram messages on invalid Markdown**: LLM-generated text with unbalanced Markdown made Telegram reject the message (it was only logged, never delivered). Messages are now retried in plain text, and Discord-style `**bold**` is converted to Telegram legacy `*bold*`.
* ✅ **Fix — Timezone-aware scheduling**: all wait computations (daily 09:00 check, kickoff countdown, "is the match today?") now use the `TIMEZONE` from `config.ini` instead of the OS clock.
* ✅ **Robustness — Terminal match statuses**: abandoned / cancelled / postponed / forfeited matches (`ABD`, `CANC`, `PST`, `AWD`, `WO`) now cleanly stop the live tracking loop, and suspended matches (`SUSP`) are handled like interruptions.
* ✅ **Robustness — AI failure fallbacks**: when the OpenRouter API is definitively unavailable, users now receive a factual fallback (match announcement, "But de X !", raw match events) instead of an error string; failed analyses are no longer stored in the match history (they used to pollute the context of future prompts). Empty LLM responses (reasoning models exhausting `max_tokens`) are retried. Failed translations now fall back to the original message.
* ✅ **Robustness — Atomic JSON writes**: `telegram_chat_ids.json`, `discord_channels.json` and `match_analyses.json` are written via a temp-file + atomic rename, so a crash mid-write can no longer corrupt them; corrupted files are also handled gracefully on read.
* ✅ **Robustness — Startup validation extended**: `LEAGUE_IDS` and `SEASON_ID` are now validated at startup (previously an invalid `SEASON_ID` only crashed on match day). Oversized single lines in messages are now hard-split to respect Telegram/Discord limits.
* ✅ **Performance — Shared HTTP clients**: one reusable `aiohttp` session (api-football) and one `httpx` client (OpenRouter) instead of a new session per request; both are closed cleanly on shutdown.
* ✅ **Dependencies updated**: aiogram 3.30.0, aiohttp 3.14.3, discord.py 2.7.1, pytz 2026.2 (httpx unchanged). Removed the useless `asyncio` and `configparser` backports from `requirements.txt`. **Note: aiogram 3.30 requires Python ≥ 3.10 (and < 3.15).** Code compatibility with these versions has been verified.

## 🆕 What's New in v2.7.0
* ✅ **Migrated from Poe to OpenRouter**: The bot now calls the OpenRouter API (`https://openrouter.ai/api/v1/chat/completions`) instead of Poe. The endpoint is OpenAI-compatible, so response parsing and cost tracking are unchanged. Required `HTTP-Referer` and `X-Title` headers are now sent. The config key is `OPENROUTER_API_KEY` (the old `POE_API_KEY` still works as a fallback for backward compatibility).
* ✅ **Default Model — MiniMax-M3**: The example config ships with `minimax/minimax-m3` as the default `MAIN_MODEL` and `TRANSLATION_MODEL` ($0.30 in / $1.20 out per 1M tokens). Any OpenRouter model slug works (`openai/gpt-4o`, `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash-001`, etc.).

## 🆕 What's New in v2.6.1
* ✅ **Fix — End-of-season false positive**: `is_match_today()` no longer broadcasts a misleading "API football is unavailable" message when the API returns `200 OK` with an empty `response` array (typical case during the off-season, when no upcoming match is scheduled). The function now distinguishes a real API failure (5xx, timeout, network error) from a successful API call with no match planned, and only notifies users in the former case. During the off-season, the bot stays silent (logs only).

## 🆕 What's New in v2.6.0
* ✅ **Season Stats in AI Context**: The current-season record of the followed team (in the league of the day's match) is now injected — in a compact one-liner — into both the pre-match (compomatch) and post-match (endmatch) LLM prompts. The LLM finally knows the team's W/D/L, goals for/against, clean sheets, and 5-match form within that specific competition.
* ✅ **Single API Call per Match for Season Stats**: The `/teams/statistics` endpoint is called once before the kickoff and the response is cached in memory for the rest of the match (pre-match prompt + post-match prompt + post-match display block). Total cost: **+1 api-football request per match**.
* ✅ **Optimized Live Polling Budget**: Live polling target lowered from 90 to 85 polls per match, freeing room for the new season-stats call while staying well under the 100 req/day free quota.
* ✅ **Visible Season Stats Block in Telegram & Discord**: After the AI end-of-match analysis, a compact stats panel is appended to the message (record, goals, clean sheets, recent form with 🟢⚪🔴 emojis). Fully compatible with Telegram (`parse_mode=Markdown`) and Discord.
* ✅ **Removed Hard-Coded League IDs**: The previous `if current_league_id == X / Y / Z` chain in the live-polling loop has been replaced by a configurable `[LEAGUE_TYPES]` section in `config.ini`. Any league ID listed in `LEAGUES_WITH_EXTRA_TIME` is treated as potentially going to extra time (+30 min budget). Leagues not listed are treated as regular championships. **The source code is now fully agnostic to country / league / team.**
* ✅ **Public-Repo Hygiene**: Added `.gitignore` (excludes `config.ini`, generated JSON, logs, virtualenv, OS files) and a `config.ini.example` template with neutral placeholders, so the repository can be published without leaking API keys or local data.
* ✅ **Default Model Updated**: The example config previously shipped with `Gemini-3-Flash` as the default `MAIN_MODEL` and `TRANSLATION_MODEL`. As of v2.7.0 the default is the OpenRouter slug `minimax/minimax-m3`.

## 🆕 What's New in v2.5.0
* ✅ **Professional Logging**: Rotating log files with automatic cleanup
* ✅ **Cost Tracking**: Real-time monitoring of AI API costs with detailed summaries
* ✅ **Match History**: Stores last 5 matches for contextual AI analysis
* ✅ **Smart Message Splitting**: Automatically splits long messages for Telegram (4096 chars) and Discord (2000 chars)
* ✅ **API Validation**: Validates all API keys at startup with clear error messages
* ✅ **Improved Reliability**: Retry mechanism with exponential backoff for API calls
* ✅ **Better Error Handling**: Enhanced error messages and graceful degradation
* ✅ **Poe API Support**: Now supports Poe API with configurable models (Grok-4-Fast-Reasoning, etc.)
* ✅ **Enhanced AI Prompts**: Richer context with match history for better analysis
* ✅ **Missed Penalty Detection**: Smart detection that doesn't notify during penalty shootouts

## 🛠 Demo & press articles
* Video link (fr) : https://www.youtube.com/shorts/XLvecHDjJGk?feature=share
* Blog api-football.com (en) : https://www.api-football.com/news/post/gptfoot-the-ultimate-telegram-and-discord-bot-for-football-fanatics-powered-by-ai

## 🌟 Potential future updates
* ✅ [DONE] Change of OpenAI's model to use GPT-4o
* ✅ [DONE] Handle the cancellation of goals by VAR
* ✅ [DONE] Professional logging system with rotation
* ✅ [DONE] API cost tracking and monitoring
* ✅ [DONE] Match history for contextual AI analysis
* ✅ [DONE — v2.6.0] Inject current-season team statistics into pre-match and post-match AI prompts (per-league, one API call per match, cached)
* ✅ [DONE — v2.6.0] Make the codebase fully agnostic (no hard-coded league IDs)
* [Low priority] Allow API calls to retrieve the standings once per day, and on match days 1 hour after the match if API calls remain available. Enable users to check standings via Telegram and Discord commands (stored locally to avoid excessive API calls). Incorporate standings data in pre-match and post-match analysis for both free and paid API versions, referencing locally stored standings without making additional API calls. Consider whether to implement this for national championships only or for all competitions.
* [Low priority] Make the bot more flexible by adding more events such as yellow cards and player changes, with the option of enabling or disabling events in `config.ini`. The idea behind the bot was to send only essential messages, so this is not a high priority.
* [Low priority] Implement a better scoring management for penalty shootouts, as they are not handled the same way as regular goals
* [Low priority] Improved handling of season ID retrieval (currently requires manual adjustment in `config.ini` at the beginning of each season)

## ✅ Known Issues - Resolution Status

### **RESOLVED Issues** ✅

* ✅ **[SOLVED]** A bug seems to occur when a new goal is scored but an old goal is updated (for example, in terms of time). The new goal is not sent, but the score is updated, which seems to prevent the sending of the new goal.
  * **Resolution**: Fixed with `event_key_sub` mechanism that prevents duplicate notifications even when API corrects goal timing

* ✅ **[SOLVED]** When a penalty miss occurs, the following goals during a match are not sent under certain conditions
  * **Resolution**: Enhanced penalty miss detection with proper event tracking and continuation logic

* ✅ **[SOLVED]** When a goal is disallowed under certain conditions, no alert is sent to indicate that the goal has been cancelled
  * **Resolution**: Improved VAR goal cancellation detection with proper score comparison and notification

* ✅ **[SOLVED]** [Free API] A bug that seemed to prevent sending a goal if the goal was sent simultaneously with the first event (mainly free API)
  * **Resolution**: Fixed with improved `is_first_event` logic and score update mechanism

* ✅ **[SOLVED]** [Free API] In very rare instances, if two goals are scored in quick succession and there's a delay in API score updates, the score might not be correctly updated until the next goal or the end of the match
  * **Resolution**: Enhanced score tracking with `previous_score` and `current_score` comparison, plus `goal_events` accumulation

* ✅ **[SOLVED — v2.5.1]** Goal timing corrections from API were not reflected in sent messages, causing confusion about when goals were actually scored
  * **Resolution**: Implemented `sent_events_details` tracking system that detects timing changes and automatically sends correction notifications to users

* ✅ **[SOLVED — v2.5.1]** Automatic correction messages now sent when timing changes are detected

* ✅ **[SOLVED — v2.6.0]** League IDs were hard-coded in `check_events()`, making the bot non-portable across countries
  * **Resolution**: Removed all hard-coded IDs. Behavior driven by the optional `[LEAGUE_TYPES]` section in `config.ini` (`LEAGUES_WITH_EXTRA_TIME`).

* ✅ **[SOLVED — v2.6.0]** AI pre-match and post-match analyses had no awareness of the team's current-season form within the specific competition being played
  * **Resolution**: One `/teams/statistics` call is made before kickoff and cached in memory, then reused in `call_chatgpt_api_compomatch` (start-of-match prompt) and `call_chatgpt_api_endmatch` (end-of-match prompt). Compact one-liner format keeps token usage minimal.

* ✅ **[SOLVED — v2.6.1]** During the off-season, the bot was sending a daily false-positive message claiming "API football is unavailable" because `is_match_today()` treated a valid `200 OK` response with an empty `response` array (no upcoming match) the same way as a real API failure
  * **Resolution**: Added an `api_call_succeeded` flag to differentiate "API OK but no fixture scheduled" (silent log only — expected during off-season) from "API actually unreachable" (still broadcast to users). No more daily spam between seasons.

* ✅ **[SOLVED — v2.8.0]** [Free API] After a penalty shootout, the tracking loop never terminated (waiting for the final `PEN` status to change), draining the daily API quota and skipping the end-of-match summary
  * **Resolution**: The shootout handler now monitors `P` (shootout in progress); `PEN` is correctly treated as a final status by the end-of-match block.

* ✅ **[SOLVED — v2.8.0]** A `RateLimitExceededError` raised during live tracking killed the daily check task silently — the bot never checked matches again until a manual restart
  * **Resolution**: The daily loop catches and logs all exceptions, then resumes the next day. The generic `except` in `get_check_match_status` no longer swallows the rate-limit exception.

* ✅ **[SOLVED — v2.8.0]** The script could not be stopped with Ctrl+C or `kill` (only `SIGKILL` worked), and Telegram messages with invalid LLM-generated Markdown were silently lost
  * **Resolution**: Proper signal handlers (log + clean exit) and a plain-text retry fallback for Telegram.

### **Circumvented Issues** 🕹️

* **[🕹️ CIRCUMVENTED — v2.5.1]** [Free API] In very rare instances, a disallowed goal could go undetected if two scored goals were identified — including one that was later disallowed — within the same interval between two checks.
  * **Status**: Mitigated by a dual-layer safety net in the live-event loop: (1) explicit handling of `Var` events with `"Goal Disallowed"` detail (`gptfoot.py:1359-1375`), and (2) a backup score-decrease detector that fires `send_goal_cancelled_message` whenever `current_score < previous_score` (`gptfoot.py:1461-1465`). Residual probability **< 1%**, and even in that residual case the displayed score remains accurate.

* **[🕹️ CIRCUMVENTED]** [Free API] Some events occurring in the very last seconds of a period may not be detected
  * **Status**: Inherent limitation of the free api-football tier — the live-polling interval (~80-100 s) is constrained by the 100 req/day quota and cannot be shortened without exceeding it. The bot is calibrated to maximize coverage (85 polls/match target) while leaving margin for season-stats and lineup calls. **Recommendation**: subscribe to a paid api-football plan and set `IS_PAID_API = true` for full 15 s polling.

* **[🕹️ CIRCUMVENTED]** [Paid API] The script does not update the score with penalty shots as this is handled differently (AI end-of-match analysis partially incorrect on shootouts)
  * **Status**: By design — penalty shootout goals are tracked separately and included in the final match analysis

* **[🕹️ CIRCUMVENTED]** [Paid API] Goals invalidated during a penalty shootout session are not considered
  * **Status**: By design — only successful penalty shootout goals are reported to avoid confusion

## 📋 Good to know
* The bot cannot provide ongoing match information if launched on a server during the match; only upcoming matches are considered
* Log files are automatically rotated when they reach 10 MB, keeping the last 5 backups
* API costs are tracked and summarized at the end of each match (when enabled in `config.ini`)
* Match analyses are stored locally in `match_analyses.json` for contextual AI insights
* Season stats are NOT persisted on disk — they are fetched once per match and cached only in memory for the duration of that match
* [Free API] Due to API call limitations, 5-minute breaks during extra time are considered as regular half-times, causing the script to pause for 13 minutes
* [Free API] Due to API call limitations, during penalty shootout sessions, the script pauses for 20 minutes (good to know but penalty goals are managed differently than goals during a match)
* [Free API] Live-polling interval is computed dynamically based on whether the league is listed in `LEAGUES_WITH_EXTRA_TIME` (longer total budget when extra time is possible). Target = 85 polls per match, leaving margin for `is_match_today`, lineups, and `/teams/statistics` calls under the 100 req/day quota.

## 🚀 Setup

> **Prerequisite**: Python **3.10 to 3.14** (required by aiogram 3.30).

```bash
# 1. Clone
git clone https://github.com/Macmachi/gptfoot.git
cd gptfoot

# 2. Create your local config from the template
cp config.ini.example config.ini

# 3. Edit config.ini and fill in your API keys, TEAM_ID, LEAGUE_IDS, etc.

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run
python gptfoot.py
```

> ⚠️ `config.ini` is intentionally listed in `.gitignore` so your secrets (API keys, tokens, team ID) never end up on GitHub. Always edit your local `config.ini`, never `config.ini.example`.

## 🔧 Configuration
The bot is configured via `config.ini` (copy `config.ini.example` first). Sections:

### `[KEYS]`
* `OPENROUTER_API_KEY` — Your OpenRouter API key (https://openrouter.ai/keys)
* `TELEGRAM_BOT_TOKEN` — Your Telegram bot token (from @BotFather)
* `DISCORD_BOT_TOKEN` — Your Discord bot token
* `API_FOOTBALL_KEY` — Your api-football.com API key
* `TEAM_ID` — Numeric ID of the team to track (find it on the api-football dashboard)
* `TEAM_NAME` — Display name of the team
* `LEAGUE_IDS` — Comma-separated list of league IDs to monitor for this team
* `SEASON_ID` — 4-digit season year (e.g. `2025` for the 2025-2026 season)

### `[OPTIONS]`
* `USE_TELEGRAM` — Enable/disable Telegram bot (true/false)
* `USE_DISCORD` — Enable/disable Discord bot (true/false)
* `IS_PAID_API` — Use paid api-football plan for more frequent updates (true/false)
* `ENABLE_COST_TRACKING` — Track and log AI API costs (true/false)

### `[API_MODELS]`
* `MAIN_MODEL` — AI model for match analysis (OpenRouter slug, e.g. `minimax/minimax-m3`, `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash-001`)
* `TRANSLATION_MODEL` — AI model for translations (can be the same)

### `[API_PRICING]`
* `INPUT_COST_PER_1M_TOKENS` — Cost per 1M input tokens in USD (your model)
* `OUTPUT_COST_PER_1M_TOKENS` — Cost per 1M output tokens in USD (your model)
* `CACHE_DISCOUNT_PERCENTAGE` — Cache discount percentage if applicable

### `[SERVER]`
* `TIMEZONE` — Server timezone (e.g. `Europe/Paris`)

### `[LANGUAGES]`
* `LANGUAGE` — Output language in lowercase English (e.g. `french`, `english`, `german`). Anything other than `french` triggers automatic LLM translation.

### `[LEAGUE_TYPES]` *(optional, new in v2.6.0)*
* `LEAGUES_WITH_EXTRA_TIME` — Comma-separated league IDs that may go to extra time (cups, knockout phases, continental competitions). Leagues listed here use an extended live-polling budget (+30 min). **Leave empty** if all your monitored leagues are regular championships.

  Example for a setup that includes one knockout competition (cup or continental knockout) where extra time is possible — replace the ID with the actual league ID(s) you monitor:
  ```
  [LEAGUE_TYPES]
  LEAGUES_WITH_EXTRA_TIME = 1234
  ```

## 📊 Technical Improvements

### Reliability
* Retry mechanism with exponential backoff (max 3 attempts)
* Improved error handling for network issues
* Graceful degradation when AI API is unavailable
* Timeout management (30 s for api-football, 60 s for AI API)

### Performance
* Optimized API call patterns (single `/teams/statistics` request per match, cached in memory)
* Live polling targeted at 85 polls per match to keep margin under the 100 req/day free quota
* Efficient event deduplication with dual-key system
* Smart message batching for multiple goals

### Maintainability
* Refactored code with helper functions
* Clear separation of concerns
* Comprehensive logging for debugging
* No hard-coded league IDs — everything driven by `config.ini`

### User Experience
* Intelligent message splitting (no truncation)
* Contextual AI analysis with match history AND current-season stats per competition
* Compact season-stats panel after each post-match analysis
* Clear error messages
* Cost transparency

## 📝 Licence
Attribution-NonCommercial 4.0 International (https://creativecommons.org/licenses/by-nc/4.0/legalcode)
