# ⚽ gptfoot (Telegram/Discord bot)

## 🌐 Overview
gptfoot is a bot for Telegram and Discord, meticulously designed to track match events for clubs across multiple leagues, all while minimizing message volume. It utilizes the cutting-edge GPT-4o technology from OpenAI to provide live match commentary. The bot offers a broad range of features, from showcasing team lineups to reporting goals, red cards, and delivering comprehensive match analyses, all backed by the advanced capabilities of GPT-4. It's a game-changer for those looking to stay updated on matches in a seamless and informative way.

## 🛠 Features
* Detection of whether a team is playing a match today in different leagues
* Real-time monitoring of match events using the Telegram bot powered by OpenAI's GPT-4-turbo
* Integration with the api-football API for retrieving match data, making predictions, and obtaining rankings (if available).
* AI-driven match analysis powered by OpenAI's GPT-4o
* Can be used with a Telegram bot, a Discord bot, or both (available options in the config.ini file)
* Can be used with either the free or paid API from api-football (available option in the config.ini file)
* The frequency of messages is limited to ensure a pleasant experience for Telegram and Discord users
* Can be used with the free version of the api-football (up to 100 calls per day)
* Support for dozens of languages 

## 🛠 Demo & press articles
* Video link (fr) : https://www.youtube.com/shorts/XLvecHDjJGk?feature=share
* Blog api-football.com (en) : https://www.api-football.com/news/post/gptfoot-the-ultimate-telegram-and-discord-bot-for-football-fanatics-powered-by-ai 

## 🌟 Potential future updates
* ✅ [DONE] Change of OpenAI's model to use GPT-4o 
* [Low priority] Make the bot more flexible by adding more events such as yellow cards and player changes, with the option of enabling or disabling events in config.ini. The idea behind the bot was to send only essential messages, so this is not a high priority.
* [Low priority] Implement a better scoring management for penalty shootouts, as they are not handled the same way as regular goals
* [Low priority] Improved handling of season ID retrieval (currently requires manual adjustment in config.ini at the beginning of each season)
* [Low priority] Inclusion of OpenAI API call costs

## ⚠ Known Issues
* ✅ [SOLVED] A bug seems to occur when a new goal is scored but an old goal is updated (for example, in terms of time). The new goal is not sent, but the score is updated, which seems to prevent the sending of the new goal.
* ✅ [SOLVED] When a penalty miss occurs, the following goal during a match are not sent under certain conditions (Monitoring Correction)
* When a goal is disallowed under certain conditions, it seems that no alert is sent to indicate that the goal has been cancelled. This could perhaps be due to a penalty considered as scored, whose score has not been updated but is then cancelled. (Monitoring for Correction)
* In very rare instances, it is possible that if a goal is scored and then corrected, and in the meantime goals are scored, the score sent back may have been updated during the correction (message of a new goal). However, the details of the match and the information linked to the goal should make it possible to identify that it is a correction of the goal and not a new goal.
* The bot cannot provide ongoing match information if launched on a server during the match; only upcoming matches are considered
* [Free API] Due to API call limitations, 5-minute breaks during extra time are considered as regular half-times, causing the script to pause for 13 minutes
* [Free API] Due to API call limitations, during penalty shootout sessions, the script pauses for 20 minutes (good to know if ever but penalty goals are managed differently than goals during a match)
* [Free API] In very rare instances, if two goals are scored in quick succession and there's a delay in API score updates, the score might not be correctly updated until the next goal or the end of the match
* [Free API] In very rare instances, it's possible that a disallowed goal might go undetected if two scored goals are identified, including one that was disallowed, within the same interval between two checks. However, the score should still be displayed accurately in such cases
* [Free API] It is possible that some events occurring in the last seconds of a period may not be detected
* [Paid API] The script does not update the score with penalty shots as this is handled differently (Analysis of the AI at the end partially incorrect)
* [Paid API] Do not consider the goals that would be invalidated during the penalty shootout session


## Licence:
Attribution-NonCommercial 4.0 International (https://creativecommons.org/licenses/by-nc/4.0/legalcode) 

## ✍️ Author: 
[Arnaud R.](https://www.linkedin.com/in/arnaud-ricci-592847b6/ )
