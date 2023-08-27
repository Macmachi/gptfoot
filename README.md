# ⚽ gptfoot (Telegram/Discord bot)

## 🌐 Overview
gptfoot is a bot for Telegram and Discord, meticulously designed to track match events for clubs across multiple leagues, all while minimizing message volume. It utilizes the cutting-edge GPT-4 technology from OpenAI to provide live match commentary. The bot offers a broad range of features, from showcasing team lineups to reporting goals, red cards, and delivering comprehensive match analyses, all backed by the advanced capabilities of GPT-4. It's a game-changer for those looking to stay updated on matches in a seamless and informative way.

✨ Follow your favorite football team by interacting alongside your friends and the community! Purchase my bot for your Discord or Telegram!
* 🚀 Checking match events with GPT-4 every 30 seconds!
* 🌐 Multi-language support
* 🔄 No installation required & Seamless bot updates
* 💸 Price: Only $4/month or $36/year (25% discount)
* 📩 Please contact me if interested : rymentz.studio@gmail.com

## 🛠 Features
* Detection of whether a team is playing a match today in different leagues
* Real-time monitoring of match events using the Telegram bot powered by OpenAI's GPT-4
* Integration with the api-football API for match data retrieval
* AI-driven match analysis powered by OpenAI's GPT-4
* Can be used with a Telegram bot, a Discord bot, or both (available options in the config.ini file)
* Can be used with either the free or paid API from api-football (available option in the config.ini file)
* The frequency of messages is limited to ensure a pleasant experience for Telegram users
* Can be used with the free version of the api-football (up to 100 calls per day)
* Support for dozens of languages 

## 🌟 Potential future updates
* Added the option to track player injury events for the followed team
* Improved handling of season ID retrieval (currently requires manual adjustment in config.ini at the beginning of each season)
* Inclusion of OpenAI API call costs
* Implement a better scoring management for penalty shootouts, as they are not handled the same way as regular goals

## ⚠ Known Issues
* [Free API] Due to API call limitations, 5-minute breaks during extra time are considered as regular half-times, causing the script to pause for 13 minutes
* [Free API] Due to API call limitations, during penalty shootout sessions, the script pauses for 20 minutes (good to know if ever but penalty goals are managed differently than goals during a match)
* [Free API] In very rare instances, if two goals are scored in quick succession and there's a delay in API score updates, the score might not be correctly updated until the next goal or the end of the match
* [Free API] In very rare instances, it's possible that a disallowed goal might go undetected if two scored goals are identified, including one that was disallowed, within the same interval between two checks. However, the score should still be displayed accurately in such cases
* [Paid API] The script does not update the score with penalty shots as this is handled differently
* [Paid API] Do not consider the goals that would be invalidated during the penalty shootout session
* The bot cannot provide ongoing match information if launched on a server during the match; only upcoming matches are considered

## Licence:
Attribution-NonCommercial 4.0 International (https://creativecommons.org/licenses/by-nc/4.0/legalcode) 

## ✍️ Author: 
Arnaud R. 
