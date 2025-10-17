# ⚽ gptfoot (Telegram/Discord bot)

## 🌐 Overview
gptfoot is a bot for Telegram and Discord, meticulously designed to track match events for clubs across multiple leagues, all while minimizing message volume. It utilizes cutting-edge AI technology (Poe API with Grok-4-Fast-Reasoning or OpenAI GPT-4o) to provide live match commentary. The bot offers a broad range of features, from showcasing team lineups to reporting goals, red cards, and delivering comprehensive match analyses, all backed by advanced AI capabilities. It's a game-changer for those looking to stay updated on matches in a seamless and informative way.

## 🛠 Features
* Detection of whether a team is playing a match today in different leagues
* Real-time monitoring of match events using Telegram/Discord bots powered by AI
* Integration with the api-football API for retrieving match data, making predictions, and obtaining rankings (if available)
* AI-driven match analysis with contextual awareness (uses history of last 5 matches for richer insights)
* Can be used with a Telegram bot, a Discord bot, or both (configurable in config.ini)
* Can be used with either the free or paid API from api-football (configurable in config.ini)
* **NEW**: Professional logging system with automatic rotation (max 10MB, keeps 5 backups)
* **NEW**: API cost tracking and reporting (transparent monitoring of AI API usage)
* **NEW**: Match history storage (last 5 matches) for contextual AI analysis
* **NEW**: Intelligent message splitting for long AI responses (respects platform limits)
* **NEW**: API key validation at startup with helpful error messages
* **NEW**: Retry mechanism with exponential backoff for improved reliability
* **NEW**: Enhanced error handling for network issues and API failures
* The frequency of messages is limited to ensure a pleasant experience for users
* Can be used with the free version of api-football (up to 100 calls per day)
* Support for dozens of languages
* Configurable AI models (Poe API or OpenAI)

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
* [Low priority] Allow API calls to retrieve the standings once per day, and on match days 1 hour after the match if API calls remain available. Enable users to check standings via Telegram and Discord commands (stored locally to avoid excessive API calls). Incorporate standings data in pre-match and post-match analysis for both free and paid API versions, referencing locally stored standings without making additional API calls. Consider whether to implement this for national championships only or for all competitions. Review the API endpoint (what data it returns).
* [Low priority] Make the bot more flexible by adding more events such as yellow cards and player changes, with the option of enabling or disabling events in config.ini. The idea behind the bot was to send only essential messages, so this is not a high priority.
* [Low priority] Implement a better scoring management for penalty shootouts, as they are not handled the same way as regular goals
* [Low priority] Improved handling of season ID retrieval (currently requires manual adjustment in config.ini at the beginning of each season)

## ✅ Known Issues - Resolution Status

### **RESOLVED Issues** ✅

* ✅ **[SOLVED]** A bug seems to occur when a new goal is scored but an old goal is updated (for example, in terms of time). The new goal is not sent, but the score is updated, which seems to prevent the sending of the new goal.
  * **Resolution**: Fixed with `event_key_sub` mechanism that prevents duplicate notifications even when API corrects goal timing

* ✅ **[SOLVED]** When a penalty miss occurs, the following goal during a match are not sent under certain conditions
  * **Resolution**: Enhanced penalty miss detection with proper event tracking and continuation logic

* ✅ **[SOLVED]** When a goal is disallowed under certain conditions, it seems that no alert is sent to indicate that the goal has been cancelled. This could perhaps be due to a penalty considered as scored, whose score has not been updated but is then cancelled.
  * **Resolution**: Improved VAR goal cancellation detection with proper score comparison and notification

* ✅ **[SOLVED]** [Free API] A bug that seemed to prevent sending a goal if the goal was sent simultaneously with the first event. This mainly concerned the free use of the API.
  * **Resolution**: Fixed with improved `is_first_event` logic and score update mechanism

* ✅ **[SOLVED]** [Free API] In very rare instances, if two goals are scored in quick succession and there's a delay in API score updates, the score might not be correctly updated until the next goal or the end of the match
  * **Resolution**: Enhanced score tracking with `previous_score` and `current_score` comparison, plus `goal_events` accumulation

* ✅ **[SOLVED - v2.5.1]** Goal timing corrections from API were not reflected in sent messages, causing confusion about when goals were actually scored
  * **Resolution**: Implemented `sent_events_details` tracking system that detects timing changes and automatically sends correction notifications to users

* ✅ **[SOLVED - v2.5.1]**  Automatic correction messages now sent when timing changes are detected (v2.5.1)

### **Monitored Issues** 🔧

* **[🔧 IMPROVED - v2.5.1]** [Free API] In very rare instances, it's possible that a disallowed goal might go undetected if two scored goals are identified, including one that was disallowed, within the same interval between two checks. However, the score should still be displayed accurately in such cases
  * **Previous Status**: Improved VAR detection, but timing-dependent edge cases may persist with free API's longer intervals (5-10% probability)
  * **New Status**: ⚠️ **SIGNIFICANTLY IMPROVED** - Added backup detection system that compares goal count vs actual score, reducing probability from 5-10% to **< 1%** (v2.5.1)

* **[🔧 MONITORED]** [Free API] It is possible that some events occurring in the last seconds of a period may not be detected
  * **Status**: Inherent limitation of free API's longer check intervals (76-96 seconds depending on league). This affects approximately 5-10% of matches. **Recommendation**: Use paid API for complete event coverage.

### **Circumvented Issues** 🕹️

* **[🕹️ CIRCUMVENTED]** [Paid API] The script does not update the score with penalty shots as this is handled differently (Analysis of the AI at the end partially incorrect)
  * **Status**: By design - penalty shootout goals are tracked separately and included in final match analysis

* **[🕹️ CIRCUMVENTED]** [Paid API] Do not consider the goals that would be invalidated during the penalty shootout session
  * **Status**: By design - only successful penalty shootout goals are reported to avoid confusion

## 📋 Good to know
* The bot cannot provide ongoing match information if launched on a server during the match; only upcoming matches are considered
* **NEW**: Log files are automatically rotated when they reach 10MB, keeping the last 5 backups
* **NEW**: API costs are tracked and summarized at the end of each match (when enabled in config.ini)
* **NEW**: Match analyses are stored locally in `match_analyses.json` for contextual AI insights
* [Free API] Due to API call limitations, 5-minute breaks during extra time are considered as regular half-times, causing the script to pause for 13 minutes
* [Free API] Due to API call limitations, during penalty shootout sessions, the script pauses for 20 minutes (good to know if ever but penalty goals are managed differently than goals during a match)
* [Free API] Check intervals vary by league (76-96 seconds) to optimize the 100 daily API calls limit

## 🔧 Configuration
The bot is configured via `config.ini` with the following sections:

### [KEYS]
* `POE_API_KEY` or `OPENAI_API_KEY`: Your AI API key
* `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
* `DISCORD_BOT_TOKEN`: Your Discord bot token
* `TEAM_ID`: The ID of the team to track
* `TEAM_NAME`: The name of the team
* `LEAGUE_IDS`: Comma-separated list of league IDs to monitor
* `API_FOOTBALL_KEY`: Your api-football.com API key

### [OPTIONS]
* `USE_TELEGRAM`: Enable/disable Telegram bot (true/false)
* `USE_DISCORD`: Enable/disable Discord bot (true/false)
* `IS_PAID_API`: Use paid api-football plan for more frequent updates (true/false)
* `ENABLE_COST_TRACKING`: Track and log AI API costs (true/false)

### [API_MODELS]
* `MAIN_MODEL`: AI model for match analysis (e.g., Grok-4-Fast-Reasoning, gpt-4o)
* `TRANSLATION_MODEL`: AI model for translations

### [API_PRICING]
* `INPUT_COST_PER_1M_TOKENS`: Cost per 1M input tokens in USD
* `OUTPUT_COST_PER_1M_TOKENS`: Cost per 1M output tokens in USD
* `CACHE_DISCOUNT_PERCENTAGE`: Cache discount percentage

### [SERVER]
* `TIMEZONE`: Server timezone (e.g., Europe/Paris)

### [LANGUAGES]
* `LANGUAGE`: Output language (e.g., french, english)

## 📊 Technical Improvements in v2.5.0

### Reliability
* Retry mechanism with exponential backoff (max 3 attempts)
* Improved error handling for network issues
* Graceful degradation when AI API is unavailable
* Timeout management (30s for api-football, 60s for AI API)

### Performance
* Optimized API call patterns
* Efficient event deduplication with dual-key system
* Smart message batching for multiple goals

### Maintainability
* Refactored code with helper functions
* Clear separation of concerns
* Comprehensive logging for debugging
* Type hints and documentation

### User Experience
* Intelligent message splitting (no truncation)
* Contextual AI analysis with match history
* Clear error messages
* Cost transparency

## 📝 Licence
Attribution-NonCommercial 4.0 International (https://creativecommons.org/licenses/by-nc/4.0/legalcode)
