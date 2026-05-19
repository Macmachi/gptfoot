# -*- coding: utf-8 -*-
#
# AUTEUR :  Rymentz (https://github.com/Macmachi/gptfoot)
# VERSION : v2.6.0
# LICENCE : Attribution-NonCommercial 4.0 International
#
import asyncio
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from aiohttp.client_exceptions import ClientConnectorError
import discord
from discord.ext import commands, tasks
import json
import os
import aiohttp
import pytz
import httpx
import configparser
import time
import atexit
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler

script_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir(script_dir)
config_path = os.path.join(script_dir, 'config.ini')

# Fonction pour valider les clés API
def validate_api_keys():
    """Valide l'existence et la validité basique des clés API"""
    errors = []
    warnings = []
    
    # Vérifier POE_API_KEY
    if not API_KEY or API_KEY == 'your_poe_api_key_here':
        errors.append("POE_API_KEY n'est pas configurée ou utilise la valeur par défaut")
    elif len(API_KEY) < 10:
        warnings.append("POE_API_KEY semble trop courte, vérifiez sa validité")
    
    # Vérifier API_FOOTBALL_KEY
    if not API_FOOTBALL_KEY or len(API_FOOTBALL_KEY) < 10:
        errors.append("API_FOOTBALL_KEY n'est pas configurée correctement")
    
    # Vérifier les tokens des bots si activés
    if USE_TELEGRAM:
        if not TOKEN_TELEGRAM or len(TOKEN_TELEGRAM) < 20:
            errors.append("TELEGRAM_BOT_TOKEN n'est pas configuré correctement")
    
    if USE_DISCORD:
        if not TOKEN_DISCORD or len(TOKEN_DISCORD) < 20:
            errors.append("DISCORD_BOT_TOKEN n'est pas configuré correctement")
    
    # Vérifier TEAM_ID
    try:
        team_id_int = int(TEAM_ID)
        if team_id_int <= 0:
            errors.append("TEAM_ID doit être un nombre positif")
    except (ValueError, TypeError):
        errors.append("TEAM_ID doit être un nombre valide")
    
    # Afficher les erreurs et warnings
    if errors:
        print("\n" + "="*60)
        print("❌ ERREURS DE CONFIGURATION CRITIQUES:")
        for error in errors:
            print(f"  • {error}")
        print("="*60 + "\n")
        return False
    
    if warnings:
        print("\n" + "="*60)
        print("⚠️  AVERTISSEMENTS DE CONFIGURATION:")
        for warning in warnings:
            print(f"  • {warning}")
        print("="*60 + "\n")
    
    print("✅ Validation des clés API réussie\n")
    return True

config = configparser.ConfigParser()

try:
    # Lire le contenu du fichier config.ini
    if not os.path.exists(config_path):
        print(f"❌ ERREUR: Le fichier config.ini n'existe pas à l'emplacement: {config_path}")
        sys.exit(1)
    
    config.read(config_path, encoding='utf-8')
    
    # Récupérer les variables de la section KEYS
    API_KEY = config['KEYS'].get('POE_API_KEY', '').strip()
    TOKEN_TELEGRAM = config['KEYS'].get('TELEGRAM_BOT_TOKEN', '').strip()
    TEAM_ID = config['KEYS'].get('TEAM_ID', '').strip()
    TEAM_NAME = config['KEYS'].get('TEAM_NAME', '').strip()
    LEAGUE_IDS_STR = config['KEYS'].get('LEAGUE_IDS', '').strip()
    SEASON_ID = config['KEYS'].get('SEASON_ID', '').strip()
    API_FOOTBALL_KEY = config['KEYS'].get('API_FOOTBALL_KEY', '').strip()
    TOKEN_DISCORD = config['KEYS'].get('DISCORD_BOT_TOKEN', '').strip()
    
    # Récupérer les variables de la section OPTIONS
    USE_TELEGRAM = config['OPTIONS'].getboolean('USE_TELEGRAM', fallback=True)
    USE_DISCORD = config['OPTIONS'].getboolean('USE_DISCORD', fallback=True)
    IS_PAID_API = config['OPTIONS'].getboolean('IS_PAID_API', fallback=False)
    ENABLE_COST_TRACKING = config['OPTIONS'].getboolean('ENABLE_COST_TRACKING', fallback=True)
    
    # Récupérer le fuseau horaire du serveur à partir de la section SERVER
    SERVER_TIMEZONE_STR = config['SERVER'].get('TIMEZONE', 'Europe/Paris')
    
    # Récupérer la langue à partir de la section LANGUAGES
    LANGUAGE = config['LANGUAGES'].get('LANGUAGE', 'english')
    
    # Récupérer les modèles API à partir de la section API_MODELS
    GPT_MODEL_NAME = config['API_MODELS'].get('MAIN_MODEL', 'Grok-4-Fast-Reasoning')
    GPT_MODEL_NAME_TRANSLATION = config['API_MODELS'].get('TRANSLATION_MODEL', 'Grok-4-Fast-Reasoning')
    
    # Récupérer la tarification à partir de la section API_PRICING
    INPUT_COST_PER_1M_TOKENS = float(config['API_PRICING'].get('INPUT_COST_PER_1M_TOKENS', '0.21'))
    OUTPUT_COST_PER_1M_TOKENS = float(config['API_PRICING'].get('OUTPUT_COST_PER_1M_TOKENS', '0.51'))
    CACHE_DISCOUNT_PERCENTAGE = float(config['API_PRICING'].get('CACHE_DISCOUNT_PERCENTAGE', '75'))

    # Récupérer la liste des ligues pouvant aller en prolongation (coupes / phases finales)
    # Tout ID listé ici est traité comme un match potentiellement avec prolongation (durée 145 min budget polling).
    # Les ligues non listées sont traitées comme championnats classiques (durée 115 min).
    # Cette section est optionnelle pour rester rétrocompatible.
    if config.has_section('LEAGUE_TYPES'):
        LEAGUES_WITH_EXTRA_TIME_STR = config['LEAGUE_TYPES'].get('LEAGUES_WITH_EXTRA_TIME', '').strip()
    else:
        LEAGUES_WITH_EXTRA_TIME_STR = ''
    LEAGUES_WITH_EXTRA_TIME = [int(x.strip()) for x in LEAGUES_WITH_EXTRA_TIME_STR.split(',') if x.strip()]

except KeyError as e:
    print(f"❌ ERREUR: Section ou clé manquante dans config.ini: {e}")
    print("Vérifiez que toutes les sections [KEYS], [OPTIONS], [SERVER], [LANGUAGES], [API_MODELS], [API_PRICING] existent")
    sys.exit(1)
except ValueError as e:
    print(f"❌ ERREUR: Valeur invalide dans config.ini: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERREUR lors de la lecture de config.ini: {e}")
    sys.exit(1)

# Valider les clés API au démarrage
if not validate_api_keys():
    print("\n⚠️  Le script va continuer mais des erreurs peuvent survenir avec des clés API invalides")
    print("Appuyez sur Ctrl+C pour arrêter et corriger la configuration\n")
    time.sleep(5)

# Variable pour suivre si le message a été envoyé pendant les tirs au but
penalty_message_sent = False
interruption_message_sent = False
# Convertir la chaîne du fuseau horaire en objet pytz
server_timezone = pytz.timezone(SERVER_TIMEZONE_STR)
# Convertir la chaîne de LEAGUE_IDS en une liste d'entiers
LEAGUE_IDS = [int(id) for id in LEAGUE_IDS_STR.split(',')]
# Empêche notre variable 'main' de se terminer après avoir créé la tâche pour lancer notre bot Discord.
is_running = True
# Défini notre variable pour stocker les événements envoyé pendant le match
sent_events = set()
# Stockage détaillé des événements pour détecter les corrections de timing
sent_events_details = {}
# Cache mémoire des statistiques de saison de notre équipe pour la ligue du match courant.
# Récupéré 1 seule fois par match (juste avant la compo) puis réutilisé pour le prompt
# d'analyse de début, de fin, ainsi que pour le bloc d'affichage en fin de match.
# Réinitialisé à chaque nouveau match.
current_season_stats = None
# Variables pour le suivi des coûts API
api_call_count = 0
total_input_tokens = 0
total_output_tokens = 0
total_cost_usd = 0.0
match_tracking_start_time = None
# Chemin du fichier de stockage des analyses de matchs
match_analyses_path = os.path.join(script_dir, 'match_analyses.json')

# Permet de générer une exception si on dépasse le nombre de call api défini dans une de ces fonctions
class RateLimitExceededError(Exception):
    pass

# Configuration du système de logging professionnel
def setup_logging():
    """Configure le système de logging avec rotation des fichiers"""
    logger = logging.getLogger('gptfoot')
    logger.setLevel(logging.INFO)
    
    # Éviter les doublons de handlers
    if logger.handlers:
        return logger
    
    # Handler pour fichier avec rotation (max 10MB, garde 5 fichiers)
    file_handler = RotatingFileHandler(
        'gptfoot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # Handler pour console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Format des logs
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialiser le logger
logger = setup_logging()

# Fonction pour afficher un message de journalisation avec un horodatage.
def log_message(message: str, level: str = "INFO"):
    """
    Fonction de logging améliorée compatible avec l'ancien code
    
    Args:
        message: Le message à logger
        level: Niveau de log (INFO, WARNING, ERROR, DEBUG)
    """
    level = level.upper()
    if level == "DEBUG":
        logger.debug(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

# Fonction pour tracker les coûts API
def track_api_cost(input_tokens: int, output_tokens: int, function_name: str = ""):
    """Track API costs based on token usage"""
    global api_call_count, total_input_tokens, total_output_tokens, total_cost_usd
    
    if not ENABLE_COST_TRACKING:
        return
    
    api_call_count += 1
    total_input_tokens += input_tokens
    total_output_tokens += output_tokens
    
    # Calculer le coût en USD
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_1M_TOKENS
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M_TOKENS
    call_cost = input_cost + output_cost
    total_cost_usd += call_cost
    
    log_message(f"[API_COST] {function_name} - Input: {input_tokens} tokens (${input_cost:.6f}), Output: {output_tokens} tokens (${output_cost:.6f}), Total call: ${call_cost:.6f}, Cumulative: ${total_cost_usd:.6f}")

# Fonction pour afficher le résumé des coûts
def log_cost_summary():
    """Log a summary of API costs at the end of the match"""
    if not ENABLE_COST_TRACKING:
        return
    
    log_message("=" * 80)
    log_message("[COST_SUMMARY] ===== RÉSUMÉ DES COÛTS API =====")
    log_message(f"[COST_SUMMARY] Nombre d'appels API : {api_call_count}")
    log_message(f"[COST_SUMMARY] Total tokens entrée : {total_input_tokens}")
    log_message(f"[COST_SUMMARY] Total tokens sortie : {total_output_tokens}")
    log_message(f"[COST_SUMMARY] Total tokens : {total_input_tokens + total_output_tokens}")
    log_message(f"[COST_SUMMARY] Coût total USD : ${total_cost_usd:.6f}")
    log_message(f"[COST_SUMMARY] Coût moyen par appel : ${total_cost_usd / api_call_count:.6f}" if api_call_count > 0 else "[COST_SUMMARY] Aucun appel API")
    log_message("=" * 80)

# Fonction qui nous permet de vider le fichier log lorsqu'un nouveau match est détecté optimise la place sur le serveur et laisse quelques jours pour vérifier les logs du match précédent entre chaque match
def clear_log():
    """Vide le fichier de log principal (garde les backups)"""
    try:
        # Fermer et rouvrir le handler pour vider le fichier
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                handler.close()
        
        with open("gptfoot.log", "w", encoding='utf-8'):
            pass
        
        # Réinitialiser le logger (pas besoin de global car logger est déjà module-level)
        setup_logging()
        log_message("Fichier de log vidé pour nouveau match")
    except Exception as e:
        log_message(f"Erreur lors du vidage du log: {e}", "ERROR")

### DEBUT DE GESTION DU STOCKAGE DES ANALYSES DE MATCHS

# Fonction pour charger l'historique des matchs depuis le fichier JSON
def load_match_history():
    """Charge l'historique des matchs depuis match_analyses.json"""
    try:
        if os.path.exists(match_analyses_path):
            with open(match_analyses_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                log_message(f"Historique des matchs chargé : {len(data.get('matches', []))} matchs trouvés")
                return data
        else:
            log_message("Fichier match_analyses.json n'existe pas, création d'une nouvelle structure")
            return {"matches": []}
    except json.JSONDecodeError:
        log_message("Erreur de décodage JSON dans match_analyses.json, création d'une nouvelle structure")
        return {"matches": []}
    except Exception as e:
        log_message(f"Erreur lors du chargement de l'historique des matchs : {e}")
        return {"matches": []}

# Fonction pour sauvegarder l'historique des matchs dans le fichier JSON
def save_match_history(data):
    """Sauvegarde l'historique des matchs dans match_analyses.json"""
    try:
        with open(match_analyses_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        log_message(f"Historique des matchs sauvegardé : {len(data.get('matches', []))} matchs")
    except Exception as e:
        log_message(f"Erreur lors de la sauvegarde de l'historique des matchs : {e}")

# Fonction pour sauvegarder une analyse de match
def save_match_analysis(fixture_id, match_info, pre_match_analysis, post_match_analysis=None):
    """Sauvegarde une analyse de match dans l'historique"""
    try:
        data = load_match_history()
        
        # Créer l'entrée du match
        match_entry = {
            "fixture_id": fixture_id,
            "date": match_info.get("date", datetime.datetime.now().isoformat()),
            "league": match_info.get("league", "Unknown"),
            "round": match_info.get("round", "Unknown"),
            "teams": match_info.get("teams", {}),
            "score": match_info.get("score", {}),
            "venue": match_info.get("venue", "Unknown"),
            "city": match_info.get("city", "Unknown"),
            "pre_match_analysis": pre_match_analysis,
            "post_match_analysis": post_match_analysis
        }
        
        # Vérifier si le match existe déjà (par fixture_id)
        existing_index = None
        for i, match in enumerate(data["matches"]):
            if match.get("fixture_id") == fixture_id:
                existing_index = i
                break
        
        if existing_index is not None:
            # Mettre à jour le match existant
            data["matches"][existing_index] = match_entry
            log_message(f"Match {fixture_id} mis à jour dans l'historique")
        else:
            # Ajouter le nouveau match
            data["matches"].append(match_entry)
            log_message(f"Match {fixture_id} ajouté à l'historique")
        
        # Garder seulement les 5 derniers matchs (utilisés pour le contexte)
        if len(data["matches"]) > 5:
            data["matches"] = data["matches"][-5:]
            log_message(f"Historique limité à 5 matchs")
        
        save_match_history(data)
    except Exception as e:
        log_message(f"Erreur lors de la sauvegarde de l'analyse du match : {e}")

# Fonction pour récupérer les N derniers matchs
def get_last_n_matches(n=5):
    """Récupère les N derniers matchs de l'historique"""
    try:
        data = load_match_history()
        matches = data.get("matches", [])
        return matches[-n:] if len(matches) >= n else matches
    except Exception as e:
        log_message(f"Erreur lors de la récupération des derniers matchs : {e}")
        return []

# Fonction pour formater l'historique des matchs pour le contexte IA
def format_match_history_for_context(matches):
    """Formate l'historique des matchs pour l'inclusion dans le contexte IA avec analyses complètes"""
    if not matches:
        return "Aucun match précédent disponible."
    
    formatted = "📊 HISTORIQUE DES 5 DERNIERS MATCHS (ANALYSES COMPLÈTES):\n"
    for i, match in enumerate(matches, 1):
        date = match.get("date", "Unknown")
        league = match.get("league", "Unknown")
        home = match.get("teams", {}).get("home", "Unknown")
        away = match.get("teams", {}).get("away", "Unknown")
        score = match.get("score", {})
        home_score = score.get("home", "?")
        away_score = score.get("away", "?")
        analysis = match.get("post_match_analysis", "Pas d'analyse disponible")
        
        # Inclure l'analyse COMPLÈTE sans troncature pour ne pas perdre d'informations importantes
        formatted += f"\n{i}. {date} - {league}\n"
        formatted += f"   {home} {home_score} - {away_score} {away}\n"
        formatted += f"   Analyse complète:\n{analysis}\n"
    
    return formatted

### FIN DE GESTION DU STOCKAGE DES ANALYSES DE MATCHS

### DEBUT DE GESTION DE LA FERMETURE DU SCRIPT

# Voir si notre script se termine 
def log_exit(normal_exit=True, *args, **kwargs):
    if normal_exit:
        log_message("Script terminé normalement.")
    else:
        log_message("Script fermé inopinément (signal reçu).")

# Enregistrez la fonction pour qu'elle s'exécute lorsque le script se termine normalement.
atexit.register(log_exit)

# Liste de signaux à gérer. Les signaux non disponibles sur la plateforme ne seront pas inclus.
signals_to_handle = [getattr(signal, signame, None) for signame in ["SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT"]]
signals_to_handle = [sig for sig in signals_to_handle if sig is not None]

# Gestion des signaux pour détecter la fermeture inattendue.
for sig in signals_to_handle:
    # Evite de marquer que le script se ferme alors que ce n'est pas le cas avec nohup et la fermeture du terminal!
    sighup = getattr(signal, 'SIGHUP', None)
    if sig == signal.SIGINT or (sighup is not None and sig == sighup):
        signal.signal(sig, signal.SIG_IGN)
    else:
        signal.signal(sig, lambda signal, frame: log_exit(False))

### FIN DE GESTION DE LA FERMETURE DU SCRIPT
### DEBUT DE GESTION DU BOT DISCORD

# Utilisez script_dir pour définir le chemin du fichier discord_channels.json
discord_channels_path = os.path.join(script_dir, 'discord_channels.json')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Activez l'intent message_content
bot_discord = commands.Bot(command_prefix="!", intents=intents)

@bot_discord.command()
async def register(ctx):
    try:
        log_message("Commande !register reçue")
        if not os.path.exists(discord_channels_path):
            with open(discord_channels_path, "w") as file:
                json.dump([], file)
                
        with open(discord_channels_path, "r") as file:
            channels = json.load(file)

        if ctx.channel.id not in channels:
            channels.append(ctx.channel.id)
            with open(discord_channels_path, "w") as file:
                json.dump(channels, file)
            await ctx.send("Ce channel a été enregistré.")
            log_message(f"Channel {ctx.channel.id} a été enregistré.")
        else:
            await ctx.send("Ce channel est déjà enregistré.")
            log_message(f"Channel {ctx.channel.id} est déjà enregistré.")
    except FileNotFoundError:
        log_message("Erreur: Le fichier discord_channels.json n'a pas été trouvé ou n'a pas pu être créé.")
    except Exception as e:
        log_message(f"Erreur lors de l'exécution de !register: {e}")     

@bot_discord.event
async def on_ready():
    if bot_discord.user:
        log_message(f'Bot Discord is now online as {bot_discord.user.name}')
    else:
        log_message('Bot Discord is now online but user is None')

@bot_discord.event
async def on_error(event, *args, **kwargs):
    log_message(f"Erreur dans l'événement {event} : {sys.exc_info()[1]}")    

@bot_discord.event
async def on_command_error(ctx, error):
    log_message(f"Erreur avec la commande {ctx.command}: {error}")    

@tasks.loop(count=1)
async def run_discord_bot(token):
    try:
        await bot_discord.start(token)
    except Exception as e:
        log_message(f"Erreur lors du démarrage du bot Discord: {e}")

### FIN DE GESTION DU BOT DISCORD
### DEBUT DE GESTION DU BOT TELEGRAM

# Fonction pour initialiser le fichier des IDs de chat autorisés s'il n'existe pas déjà.
def initialize_chat_ids_file():
    """
    Crée un fichier JSON vide pour stocker les ID de chat si le fichier n'existe pas déjà.
    """
    if not os.path.exists("telegram_chat_ids.json"):
        try:
            with open("telegram_chat_ids.json", "w") as file:
                json.dump([], file)
        except IOError as e:
            log_message(f"Erreur lors de la création du fichier telegram_chat_ids.json : {e}")

# Fonction déclenchée lorsqu'un utilisateur envoie la commande /start au bot.
async def on_start(message: types.Message):
    log_message("on_start(message: types.Message) appelée.")  
    chat_id = message.chat.id
    log_message(f"Fonction on_start() appelée pour le chat {chat_id}")

    # Récupérez les ID de chat existants à partir du fichier JSON
    with open("telegram_chat_ids.json", "r") as file:
        chat_ids = json.load(file)

    # Ajoutez l'ID de chat au fichier JSON s'il n'est pas déjà présent
    if chat_id not in chat_ids:
        chat_ids.append(chat_id)

        with open("telegram_chat_ids.json", "w") as file:
            json.dump(chat_ids, file)

        await message.reply("Le bot a été démarré et l'ID du chat a été enregistré.")
        log_message(f"Le bot a été démarré et l'ID du chat {chat_id} a été enregistré.")
    else:
        await message.reply("Le bot a déjà été démarré dans ce chat.")
        log_message(f"Le bot a déjà été démarré dans ce chat {chat_id}.")    

### FIN DE GESTION DU BOT TELEGRAM          
        
# Vérifie périodiquement si un match est prévu et, si c'est le cas, récupère les informations pertinentes et effectue des actions appropriées.
async def check_match_periodically():

    while True:
        now = datetime.datetime.now()
        target_time = datetime.datetime(now.year, now.month, now.day, 9, 0, 0)

        if now > target_time:
            target_time += datetime.timedelta(days=1)

        seconds_until_target_time = (target_time - now).total_seconds()
        log_message(f"Attente de {seconds_until_target_time} secondes jusqu'à la prochaine vérification des matchs (09:00).")
        await asyncio.sleep(seconds_until_target_time)
        
        # Vérifiez les matchs 
        log_message("Vérification du match en cours...")
        await check_matches()
    
# Vérifie si un match est prévu aujourd'hui et effectue les actions appropriées, comme envoyer des messages de début et de fin de match, et vérifier les événements pendant le match.
async def check_matches():
    global sent_events
    log_message("get_team_match_info() appelée.")
    #On ignore la dernière value (current_league_id) qui n'est pas importante ici et déjà déclaré comme une variable globale !
    match_today, match_start_time, fixture_id, current_league_id, teams, league, round_info, venue, city = await is_match_today()

    log_message(
        f"Résultat de is_match_today() dans la fonction check_match_periodically : "
        f"match_today = {match_today}, "
        f"match_start_time = {match_start_time}, "
        f"fixture_id = {fixture_id}, "
        f"current_league_id = {current_league_id}, "
        f"teams = {teams}, "
        f"league = {league}, "
        f"round_info = {round_info}, "
        f"venue = {venue}, "
        f"city = {city}"
    )

    if match_today:
        # Réinitialiser les variables de suivi des coûts pour ce match
        global api_call_count, total_input_tokens, total_output_tokens, total_cost_usd, penalty_message_sent, interruption_message_sent
        api_call_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        # Réinitialiser les flags de message pour le nouveau match
        penalty_message_sent = False
        interruption_message_sent = False
        
        # Vider le fichier de logs si un match est trouvé
        clear_log()
        log_message(f"un match a été trouvé")
        log_message(f"[COST_TRACKING] Début du suivi des coûts pour le match")
        # Vérifie que match_start_time n'est pas None et qu'il a des attributs hour et minute.
        if match_start_time and hasattr(match_start_time, 'hour') and hasattr(match_start_time, 'minute'):
            now = datetime.datetime.now()
            match_start_datetime = now.replace(hour=match_start_time.hour, minute=match_start_time.minute, second=0, microsecond=0)
            seconds_until_match_start = (match_start_datetime - now).total_seconds()
            log_message(f"Il reste {seconds_until_match_start} secondes avant le début du match.")
            # Calculer le temps pour envoyer le message 10 minutes avant le début du match
            seconds_until_message = max(0, seconds_until_match_start - 900)  # 900 secondes = 15 minutes
            # On envoie le message pour annoncer qu'il y a un match aujourd'hui
            await send_match_today_message(match_start_time, fixture_id, current_league_id, teams, league, round_info, venue, city)
           
            # Attendre jusqu'à l'heure d'envoi du message 10 minutes avant le début du match
            await asyncio.sleep(seconds_until_message)
            # Envoyer le message si IS_PAID_API est vrai
            if IS_PAID_API:
                # Attendez que le match débute réellement qui est vérifié dans wait_for_match_start
                match_data = (await wait_for_match_start(fixture_id, teams, league, round_info, venue, city))[3]
                log_message(f"match_data reçu de wait_for_match_start dans check_matches {match_data}\n")
            
            else:
                # Attendre jusqu'au début du match pour envoyer la compo et voir le match a réellement commencé si on utilise l'api free pour limiter les calls à l'api
                # On vérifie pas ici si le match a déjà commencé car la structure du code fait en sorte qu'on puisse pas lancer le script pendant un match qui a commencé pour récuprer ses infos il faut attendre les matchs suivants.
                remaining_seconds = seconds_until_match_start - seconds_until_message
                await asyncio.sleep(remaining_seconds)
                log_message(f"Fin de l'attente jusqu'à l'heure prévu de début de match")
                # Attendez que le match débute réellement
                match_data = (await wait_for_match_start(fixture_id, teams, league, round_info, venue, city))[3]
                log_message(f"match_data reçu de wait_for_match_start dans check_matches {match_data}\n")
        
            # Envoyez le message de début de match et commencez à vérifier les événements
            if match_data is not None:
                log_message(f"Envoie du message de début de match avec send_start_message (uniquement utile pour l'api payante avec interval court)")
                await send_start_message()
                log_message(f"Check des événements du match avec check_events")
                # Réinitialiser les événements envoyés au début de chaque match
                sent_events.clear()
                sent_events_details.clear()
                log_message(f"sent_events et sent_events_details vidés pour le nouveau match, taille: {len(sent_events)}")
                await check_events(fixture_id)
            else:
                log_message(f"Pas de match_data pour l'instant (fonction check_matches), résultat de match_data : {match_data}")
        else:
                    log_message(f"Pas d'heure de début de match")
    else:
        log_message(f"Aucun match prévu aujourd'hui")

# Fonction pour récupérer les statistiques de saison de l'équipe dans la ligue courante
async def get_team_season_statistics(league_id, team_id, season):
    """
    Récupère les stats de saison de l'équipe pour la compétition donnée
    via l'endpoint /teams/statistics. Renvoie le dict 'response' ou None.
    Cette fonction n'appelle l'API qu'une seule fois (1 requête / match).
    En cas de rate-limit faible (< 2), on skip silencieusement pour ne pas
    interrompre la fin du match.
    """
    log_message(f"get_team_season_statistics() appelée (league={league_id}, team={team_id}, season={season}).")
    url = f"https://v3.football.api-sports.io/teams/statistics?league={league_id}&team={team_id}&season={season}"
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                remaining_calls_per_day = int(resp.headers.get('x-ratelimit-requests-remaining', 0))
                log_message(f"Nombre d'appels à l'api restants : {remaining_calls_per_day}")

                # Tolérant : on ne raise pas, on skip si trop bas
                if remaining_calls_per_day < 2:
                    log_message("Quota API trop bas pour récupérer les stats de saison, skip.", "WARNING")
                    return None

                resp.raise_for_status()
                data = await resp.json()

                if not data.get('response'):
                    log_message("Pas de données récupérées depuis get_team_season_statistics", "WARNING")
                    return None

                return data['response']

    except asyncio.TimeoutError:
        log_message("Timeout lors de la récupération des stats de saison", "ERROR")
        return None
    except aiohttp.ClientError as e:
        log_message(f"Erreur réseau dans get_team_season_statistics: {e}", "ERROR")
        return None
    except KeyError as e:
        log_message(f"Données manquantes (get_team_season_statistics): {e}", "ERROR")
        return None
    except Exception as e:
        log_message(f"Erreur inattendue dans get_team_season_statistics: {e}", "ERROR")
        return None

# Fonction pour récupérer les prédictions
async def get_match_predictions(fixture_id):
    log_message("get_match_predictions() appelée.")
    url = f"https://v3.football.api-sports.io/predictions?fixture={fixture_id}"
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                remaining_calls_per_day = int(resp.headers.get('x-ratelimit-requests-remaining', 0))
                log_message(f"Nombre d'appels à l'api restants : {remaining_calls_per_day}")

                if remaining_calls_per_day < 3:
                    log_message(f"#####\nLe nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.\n#####", "WARNING")
                    await notify_users_max_api_requests_reached()
                    raise RateLimitExceededError("Le nombre d'appels maximum à l'API est dépassé.")

                resp.raise_for_status()
                data = await resp.json()
                
                if not data.get('response'):
                    log_message(f"Pas de données récupérées depuis get_match_predictions", "WARNING")
                    return None

                return data['response'][0]['predictions']

    except asyncio.TimeoutError:
        log_message(f"Timeout lors de la récupération des prédictions pour fixture {fixture_id}", "ERROR")
        return None
    except aiohttp.ClientError as e:
        log_message(f"Erreur réseau dans get_match_predictions: {e}", "ERROR")
        return None
    except RateLimitExceededError:
        raise
    except KeyError as e:
        log_message(f"Données manquantes dans la réponse API (get_match_predictions): {e}", "ERROR")
        return None
    except Exception as e:
        log_message(f"Erreur inattendue dans get_match_predictions: {e}", "ERROR")
        return None

#Fonction qui permet de vérifier quand le match démarre réellement par rapport à l'heure prévu en vérifiant si le match a toujours lieu!
async def wait_for_match_start(fixture_id, teams=None, league=None, round_info=None, venue=None, city=None):
    log_message(f"fonction wait_for_match_start appelée")

    # Récupérer les prédictions avant d'envoyer le message de compo (uniquement avec l'api payante car call limité avec gratuit)
    predictions = None
    if IS_PAID_API:
        predictions = await get_match_predictions(fixture_id)
        if predictions:
            log_message(f"Prédictions obtenues : {predictions}")

    # Permet d'envoyer la compo à l'heure du début du match prévue avant que le match commence réellement ! Attention coûte un appel API en plus !
    match_status, match_date, elapsed_time, match_data = await get_check_match_status(fixture_id)
    # Note : On peut potentiellement vérifier ici (actuellement pas le cas) si la compo renvoyée par get_check_match_status et pas none et on pourrait retenter 5 minutes plus tard en mettant le script sur pause uniquement si paid api ?!
    log_message(f"match_status: {match_status}, match_date: {match_date}, elapsed_time: {elapsed_time} et \n [DEBUG] match data :\n {match_data}\n\n")

    # Récupération unique des stats de saison de notre équipe pour la ligue du match (1 seul appel API par match).
    # Mises en cache dans la variable globale current_season_stats pour réutilisation par
    # call_chatgpt_api_compomatch (analyse de début), call_chatgpt_api_endmatch (analyse de fin)
    # et le bloc d'affichage en fin de match.
    global current_season_stats, current_league_id
    current_season_stats = None
    try:
        if current_league_id and TEAM_ID and SEASON_ID:
            current_season_stats = await get_team_season_statistics(current_league_id, TEAM_ID, SEASON_ID)
            log_message(f"Stats de saison récupérées et mises en cache : {bool(current_season_stats)}")
    except Exception as e:
        log_message(f"Erreur lors de la récupération des stats de saison : {e}", "ERROR")
        current_season_stats = None

    log_message(f"Envoie du message de compo de match avec send_compo_message")
    await send_compo_message(match_data, predictions, fixture_id, teams, league, round_info, venue, city)

    while True:
        match_status, match_date, elapsed_time, match_data = await get_check_match_status(fixture_id)

        if match_status and elapsed_time is not None:
            # Sortir de la boucle si le match commence, ou est annulé pour X raisons
            if elapsed_time > 0 or match_status in ('PST', 'CANC', 'ABD', 'AWD', 'WO'):
                log_message(f"le match a commencé sorti de la boucle wait_for_match_start")      
                break
        log_message("Le match n'a pas encore commencé, en attente...")

        # Si api gratuite utilisée Attendre 120 secondes avant de vérifier à nouveau (comme on envoie plus le message de début on peut limiter le nombre d'appels à l'api!)
        sleep_time = 30 if IS_PAID_API else 120 # On met 30 secondes et pas 15 car cela évite trop d'appeler la fonction trop fréquemment sachant que la composition est envoyé 15 minutes avant
        await asyncio.sleep(sleep_time)    

    # Retourner None si le match est reporté ou annulé
    if match_status in ('PST', 'CANC', 'ABD'):
        log_message(f"Le statut du match indique qu'il a été annulé ou reporté")  
        message = f"🤖 : Le statut du match indique qu'il a été annulé ou reporté"
        await send_message_to_all_chats(message)
        return None, None, None, None
    elif match_status in ('AWD', 'WO'):
        log_message(f"Défaite technique ou victoire par forfait ou absence de compétiteur")
        message = f"🤖 : Défaite technique ou victoire par forfait ou absence de compétiteur"
        await send_message_to_all_chats(message)
        return None, None, None, None
    else:
        log_message(f"match_status: {match_status}, match_date: {match_date}, elapsed_time: {elapsed_time}, match_data (pas log)\n")  
        return match_status, match_date, elapsed_time, match_data
    
# Récupère le statut et la date du match de la team dans la ligue spécifiée avec retry.
async def get_check_match_status(fixture_id, max_retries=3):
    log_message("get_check_match_status() appelée.")
    url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    # Vérifiez le nombre d'appels restants par jour
                    remaining_calls_per_day = int(resp.headers.get('x-ratelimit-requests-remaining', 0))
                    log_message(f"Nombre d'appels à l'api restants : {remaining_calls_per_day}")
                    
                    #Permet de sortir si on reste bloqué dans cette fonction pour x raisons
                    #3 car on check 3 league à la sortie
                    if remaining_calls_per_day < 3:
                        log_message(f"#####\nLe nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.\n#####")
                        await notify_users_max_api_requests_reached()
                        raise RateLimitExceededError("Le nombre d'appels maximum à l'API est dépassé.")
                    
                    # Vérifier le code de statut HTTP
                    if resp.status != 200:
                        log_message(f"Erreur HTTP {resp.status} de l'API football (tentative {attempt + 1}/{max_retries})")
                        if resp.status >= 500 and attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        elif resp.status == 429 and attempt < max_retries - 1:
                            await asyncio.sleep(5 * (2 ** attempt))
                            continue
                        return None, None, None, None
                        
                    data = await resp.json()
                    if not data.get('response'):
                        log_message(f"Pas de données récupérées depuis get_check_match_status")
                        return None, None, None, None

            fixture = data['response'][0]
            match_status = fixture['fixture']['status']['short']
            match_date = datetime.datetime.strptime(fixture['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z').astimezone(server_timezone)
            elapsed_time = fixture['fixture']['status']['elapsed']
            # Récupérez match_data à partir de la variable fixture
            match_data = {
                        "teams": {
                            "home": {
                                "name": fixture['teams']['home']['name']
                            },
                            "away": {
                                "name": fixture['teams']['away']['name']
                            }
                        },
                        "lineups": {}
                    }
                    
            if 'lineups' in fixture and len(fixture['lineups']) >= 2:
                home_lineup = fixture['lineups'][0]
                away_lineup = fixture['lineups'][1]
                
                home_startXI = home_lineup.get('startXI', [])
                away_startXI = away_lineup.get('startXI', [])
                
                match_data["lineups"] = {
                    home_lineup['team']['name']: {
                        "formation": home_lineup.get('formation', ''),
                        "startXI": home_startXI
                    },
                    away_lineup['team']['name']: {
                        "formation": away_lineup.get('formation', ''),
                        "startXI": away_startXI
                    }
                }
            else:
                match_data["lineups"] = {
                    match_data["teams"]["home"]["name"]: {
                        "formation": "",
                        "startXI": []
                    },
                    match_data["teams"]["away"]["name"]: {
                        "formation": "",
                        "startXI": []
                    }
                }

            log_message(f"Statut et données de match récupérés depuis get_check_match_status : {match_status}, \n Date du match : {match_date}, \n Temps écoulé : {elapsed_time}, \n match data : (no log) \n")
            return match_status, match_date, elapsed_time, match_data

        except asyncio.TimeoutError:
            log_message(f"Timeout lors de l'appel à l'API football (tentative {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None, None, None, None
        except aiohttp.ClientError as e:
            log_message(f"Erreur réseau lors de la requête à l'API football (tentative {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None, None, None, None
        except Exception as e:
            log_message(f"Erreur inattendue lors de la requête à l'API football (tentative {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None, None, None, None
    
    log_message(f"Tous les {max_retries} appels à l'API football ont échoué")
    return None, None, None, None

# Fonction asynchrone pour vérifier s'il y a un match aujourd'hui et retourner les informations correspondantes avec retry.
async def is_match_today(max_retries=3):
    log_message("is_match_today() appelée.")
    responses = []
    # déclaration de la variable comme globale
    global current_league_id
    # Variable pour stocker l'ID de la ligue en cours de traitement
    current_league_id = None

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                for LEAGUE_ID in LEAGUE_IDS:
                    url = f"https://v3.football.api-sports.io/fixtures?team={TEAM_ID}&league={LEAGUE_ID}&next=1"
                    headers = {
                        "x-apisports-key": API_FOOTBALL_KEY
                    }
                    try:
                        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get('response'):
                                    responses.append(data)
                                    current_league_id = LEAGUE_ID
                            elif resp.status >= 500 and attempt < max_retries - 1:
                                log_message(f"Erreur serveur {resp.status} pour la ligue {LEAGUE_ID}, retry...")
                                await asyncio.sleep(2 ** attempt)
                                continue
                            elif resp.status == 429 and attempt < max_retries - 1:
                                log_message(f"Rate limit pour la ligue {LEAGUE_ID}, attente...")
                                await asyncio.sleep(5 * (2 ** attempt))
                                continue
                    except asyncio.TimeoutError:
                        log_message(f"Timeout pour la ligue {LEAGUE_ID} (tentative {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                    except aiohttp.ClientError as e:
                        log_message(f"Erreur réseau pour la ligue {LEAGUE_ID} (tentative {attempt + 1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
            
            # Si on a au moins une réponse, on sort de la boucle de retry
            if responses:
                break
        except Exception as e:
            log_message(f"Erreur inattendue dans is_match_today (tentative {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
    
    if not responses:
        log_message(f"Impossible de récupérer les matchs après {max_retries} tentatives")
        await send_message_to_all_chats("🤖 : Impossible de vérifier les matchs. L'API football est indisponible. Veuillez réessayer plus tard.")
        return False, None, None, None, None, None, None, None, None

    match_today = False
    match_start_time = None
    fixture_id = None

    # Ajout de nouvelles variables pour les informations supplémentaires
    teams = None
    league = None
    round_info = None
    venue = None
    city = None

    for response in responses:
        if response['results'] > 0:
            fixture_data = response['response'][0]['fixture']
            league_data = response['response'][0]['league']
            teams_data = response['response'][0]['teams']
            venue_data = fixture_data['venue']

            match_date = datetime.datetime.strptime(fixture_data['date'], '%Y-%m-%dT%H:%M:%S%z')
            match_date = match_date.astimezone(server_timezone)
            match_date = match_date.date()
            today = datetime.date.today()

            if match_date == today:
                match_today = True
                match_start_datetime = datetime.datetime.strptime(fixture_data['date'], '%Y-%m-%dT%H:%M:%S%z')
                match_start_datetime = match_start_datetime.astimezone(server_timezone)
                match_start_time = match_start_datetime.time()
                fixture_id = fixture_data['id']

                # Extraction des informations supplémentaires
                teams = {
                    "home": teams_data['home']['name'],
                    "away": teams_data['away']['name']
                }
                league = league_data['name']
                round_info = league_data['round']
                venue = venue_data['name']
                city = venue_data['city']
                break

    # Inclure les nouvelles informations dans la valeur de retour
    return match_today, match_start_time, fixture_id, current_league_id, teams, league, round_info, venue, city

# Récupère les événements en direct (buts, cartons, etc.) et le statut du match pour un match donné.
async def get_team_live_events(fixture_id):
    log_message("get_team_live_events() appelée.")
    events_url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(events_url, headers=headers) as events_response:
                # Vérifiez le nombre d'appels restants par jour
                remaining_calls_per_day = int(events_response.headers.get('x-ratelimit-requests-remaining', 0))
                log_message(f"Nombre d'appels à l'api restants : {remaining_calls_per_day}")
                
                # 3 car on check 3 league à la sortie
                if remaining_calls_per_day < 3:
                    await notify_users_max_api_requests_reached()
                    log_message(f"#####\nLe nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.\n#####", "WARNING")
                    raise RateLimitExceededError("Le nombre d'appels maximum à l'API est dépassé.")
                
                events_response.raise_for_status()
                events_data = await events_response.json()
                
                if not events_data.get('response'):
                    log_message("Pas de réponse de l'API pour get_team_live_events", "WARNING")
                    return None, None, None, None, None
                    
                match_info = events_data['response'][0]
                events = match_info['events']
                match_status = match_info['fixture']['status']['short']
                elapsed_time = match_info['fixture']['status']['elapsed']
                match_data = match_info
                log_message(f"Temps écoulé du match : {elapsed_time}\n")
                match_statistics = match_info['statistics']
                
                return events, match_status, elapsed_time, match_data, match_statistics
                
    except asyncio.TimeoutError:
        log_message(f"Timeout lors de la récupération des événements pour fixture {fixture_id}", "ERROR")
        return None, None, None, None, None
    except aiohttp.ClientError as e:
        log_message(f"Erreur réseau lors de la requête à l'API (via get_team_live_events): {e}", "ERROR")
        return None, None, None, None, None
    except RateLimitExceededError:
        raise
    except KeyError as e:
        log_message(f"Données manquantes dans la réponse API (get_team_live_events): {e}", "ERROR")
        return None, None, None, None, None
    except Exception as e:
        log_message(f"Erreur inattendue lors de la requête à l'API (via get_team_live_events): {e}", "ERROR")
        return None, None, None, None, None

# Fonction helper pour gérer la mi-temps
async def handle_halftime(fixture_id, match_status, IS_PAID_API):
    """Gère la logique de mi-temps pour API payante et gratuite"""
    log_message(f"mi-temps détectée")
    
    if IS_PAID_API:
        log_message(f"API payante : vérification toutes les 15 secondes")
        
        # Boucle pour vérifier le statut du match après la pause
        while True:
            log_message(f"On vérifie si le match a repris (statut actuel : {match_status})")
            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
            log_message(f"Données récupérées de get_team_live_events dans handle_halftime;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")
            
            if match_status != 'HT':
                log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'execution du code")
                return None, match_status, elapsed_time, match_data, match_statistics
            
            await asyncio.sleep(15)
    else:
        # API gratuite
        log_message(f"mi-temps détectée - mise en pause de l'execution du code pour 780 secondes")
        await asyncio.sleep(780)  # 13 minutes
        
        # Boucle pour vérifier le statut du match après la pause
        while True:
            log_message(f"On vérifie si le match a repris (statut actuel : {match_status})")
            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
            log_message(f"Données récupérées de get_team_live_events dans handle_halftime;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")
            
            if match_status != 'HT':
                log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'execution du code")
                return None, match_status, elapsed_time, match_data, match_statistics
            
            await asyncio.sleep(120)

# Fonction helper pour gérer les tirs au but
async def handle_penalty_shootout(fixture_id, penalty_message_sent, IS_PAID_API):
    """Gère la logique des tirs au but"""
    if not penalty_message_sent:
        log_message("Séance de tir au but : attente de 20 minutes la fin des pénos pour envoyer les informations du match restants + fin de match pour limiter le nombre d'appels à l'api !")
        await pause_for_penalty_shootout()
        penalty_message_sent = True
    
    if IS_PAID_API:
        wait_time = 30
    else:
        await asyncio.sleep(1200)  # 20 minutes
        wait_time = 300
    
    # Boucle pour vérifier le statut du match après les pénos
    while True:
        log_message(f"On vérifie si les pénos (PEN) sont terminés")
        events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
        log_message("Données récupérées de get_team_live_events; Statistiques de match : (pas log), Status de match : {}, Events {}, match_data : (pas log)".format(match_status, events))
        
        if match_status != 'PEN':
            log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'exécution du code")
            return penalty_message_sent, events, match_status, elapsed_time, match_data, match_statistics
        
        await asyncio.sleep(wait_time)

# Fonction helper pour gérer les interruptions
async def handle_interruption(fixture_id, interruption_message_sent, IS_PAID_API):
    """Gère la logique des interruptions de match"""
    log_message(f"Match interrompu (INT)")
    
    if not interruption_message_sent:
        await notify_match_interruption()
        interruption_message_sent = True
    
    if IS_PAID_API:
        wait_time = 120
    else:
        await asyncio.sleep(600)  # 10 minutes
        wait_time = 600
    
    # Boucle pour vérifier le statut du match après l'interruption
    while True:
        log_message(f"On vérifie si l'interruption est terminée (statut actuel : INT)")
        events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
        log_message(f"Données récupérées de get_team_live_events;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")
        
        if match_status != 'INT':
            log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'execution du code")
            return interruption_message_sent, events, match_status, elapsed_time, match_data, match_statistics
        
        await asyncio.sleep(wait_time)

# Fonction helper pour traiter un événement de but
async def process_goal_event(event, match_data, elapsed_time, current_score, previous_score, is_first_event, IS_PAID_API, match_status):
    """Traite un événement de but et retourne les informations nécessaires"""
    if event['detail'] == 'Missed Penalty':
        last_missed_penalty_time = event['time']['elapsed']
        log_message(f"Penalty manqué détecté à {last_missed_penalty_time} minutes.")
        
        # Notifier uniquement si ce n'est PAS pendant les tirs au but
        if match_status not in ('P', 'PEN'):
            player = event['player']
            team = event['team']
            if player is not None and team is not None:
                await send_missed_penalty_message(player, team, last_missed_penalty_time)
        
        return None, False, is_first_event
    
    log_message(f"Not Missed Penalty")
    player = event['player']
    team = event['team']
    current_elapsed_time = elapsed_time
    goal_elapsed_time = event['time']['elapsed']
    allowed_difference = -10
    
    # Créer un dictionnaire avec toutes les informations du but
    goal_info = {
        'player': player,
        'team': team,
        'event': event,
        'elapsed_time': goal_elapsed_time,
        'event_key': f"{event['type']}_{event['time']['elapsed']}_{player['id'] if player and player.get('id') else None}",
        'player_statistics': None,
        'significant_increase': False
    }
    
    # Récupérer les statistiques du joueur si disponibles
    if player is not None and player.get('id'):
        player_id = player['id']
        if 'players' in match_data:
            for team_data in match_data['players']:
                for player_stats in team_data['players']:
                    if 'player' in player_stats and player_stats['player']['id'] == player_id:
                        goal_info['player_statistics'] = player_stats['statistics']
                        break
                if goal_info['player_statistics']:
                    break
    
    # Vérifier si on a un temps de match valide avant de faire des comparaisons
    if current_elapsed_time is None:
        log_message(f"[AVERTISSEMENT] Impossible de vérifier l'horodatage du but car le temps de match écoulé est None.")
        return None, False, is_first_event
    
    # Vérifier si le but est dans l'intervalle de temps acceptable
    if not (player is not None and player.get('id') and player.get('name') and
            goal_elapsed_time is not None and
            goal_elapsed_time >= current_elapsed_time + allowed_difference):
        if goal_elapsed_time is not None and goal_elapsed_time < current_elapsed_time + allowed_difference:
            log_message(f"[ATTENTION] L'event goal (temps: {goal_elapsed_time}) est trop ancien par rapport au temps actuel ({current_elapsed_time}).")
        return None, False, is_first_event
    
    log_message(f"L'événement de goal a été détecté dans un interval de 10 minutes")
    
    # Calculer le nouveau score depuis match_data
    new_score = {
        'home': match_data['goals']['home'],
        'away': match_data['goals']['away']
    }
    
    if is_first_event or new_score != previous_score:
        # Vérifier l'augmentation significative du score (plus de 1 but marqué par une équipe)
        significant_increase_in_score = False
        if team['id'] == match_data['teams']['home']['id'] and new_score['home'] - current_score['home'] > 1:
            significant_increase_in_score = True
        elif team['id'] == match_data['teams']['away']['id'] and new_score['away'] - current_score['away'] > 1:
            significant_increase_in_score = True
        
        goal_info['significant_increase'] = significant_increase_in_score
        return goal_info, True, False
    
    elif IS_PAID_API and match_status == 'P':
        await send_shootout_goal_message(player, team,
            goal_info['player_statistics'] if goal_info['player_statistics'] else [],
            event)
        return None, False, is_first_event
    else:
        log_message(f"Le score n'a pas été modifié car l'API ne l'a pas mis à jour")
        return None, False, is_first_event

# Fonction asynchrone pour vérifier les événements en cours pendant un match, tels que les buts et les cartons rouges.
async def check_events(fixture_id):
    log_message("check_events(fixture_id) appelée.")
    global sent_events
    global sent_events_details
    global IS_PAID_API
    global penalty_message_sent
    global interruption_message_sent
    current_score = {'home': 0, 'away': 0}
    previous_score = {'home': 0, 'away': 0}
    score_updated = False
    is_first_event = True
    # Nouvelle liste pour stocker temporairement les événements de but
    goal_events = []

    while True:
        try:
            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
            # S'assurer que match_data n'est pas None avant d'en extraire 'goals'.
            if match_data and match_data.get('goals'):
                new_score = {
                    'home': match_data['goals']['home'],
                    'away': match_data['goals']['away']
                }
                
                if new_score != current_score:
                    log_message(f"Mise à jour du score après les événements VAR : {current_score} -> {new_score}")
                    previous_score = current_score.copy()
                    current_score = new_score.copy()
            else:
                log_message(f"Pas de match_data ou de données de buts disponibles (none)\n")
                new_score = current_score # Garder le score actuel si pas de nouvelles données

            # Calcul de l'intervalle optimisé selon api payante ou non
            if IS_PAID_API:
                interval = 15
            else:
                # API gratuite : on cible 85 polls/match pour rester sous le quota 100 req/jour.
                # Les ~15 appels restants couvrent : is_match_today (1 par ligue surveillée),
                # wait_for_match_start (compo), /teams/statistics (saison) et marges éventuelles.
                target_polls = 85
                # Durée totale en minutes : pre-match buffer + 1ère mi-temps + pause + 2ème mi-temps + marge fin.
                # +30 min ajoutées si la compétition peut aller en prolongation (configurable via [LEAGUE_TYPES]).
                base_duration_min = 5 + 45 + 10 + 45 + 10
                if current_league_id in LEAGUES_WITH_EXTRA_TIME:
                    total_duree_championnat = base_duration_min + 30
                else:
                    total_duree_championnat = base_duration_min
                interval = (total_duree_championnat * 60) / target_polls

            # Gestion de la mi-temps
            if match_status == 'HT':
                result = await handle_halftime(fixture_id, match_status, IS_PAID_API)
                if result:
                    events, match_status, elapsed_time, match_data, match_statistics = result
                    events = None  # Réinitialiser pour éviter de renvoyer les événements de la première mi-temps

            # Gestion des tirs au but
            if match_status == 'P' or match_status == 'PEN':
                penalty_message_sent, events, match_status, elapsed_time, match_data, match_statistics = await handle_penalty_shootout(fixture_id, penalty_message_sent, IS_PAID_API)

            # Gestion des interruptions
            if match_status == 'INT':
                interruption_message_sent, events, match_status, elapsed_time, match_data, match_statistics = await handle_interruption(fixture_id, interruption_message_sent, IS_PAID_API)

            # Vérifiez que events n'est pas None avant de l'itérer
            if events is None:
                await asyncio.sleep(interval)
                continue

            # Boucle pour vérifier les événements
            for event in events:
                # Vérifier si match_data n'est pas None
                if match_data is None:
                    log_message("match_data est None, impossible de continuer le traitement des événements")
                    break
                
                # Vérifiez si l'attribut 'player' existe sinon on lui attribue une valeur nulle
                player_id = event['player']['id'] if 'player' in event and event['player'] is not None else None
                # On créé une clé uniquement pour identifier l'événement en question
                event_key = f"{event['type']}_{event['time']['elapsed']}_{player_id}"
                # Clé pour détecter les corrections (inclut le timing pour distinguer les doublés)
                event_key_sub = f"{event['type']}_{player_id}_{event['time']['elapsed']}"

                # ISSUE 6: Vérifier si l'événement a déjà été envoyé et si le timing a changé
                if event_key_sub in sent_events_details:
                    old_data = sent_events_details[event_key_sub]
                    old_time = old_data.get('time')
                    new_time = event['time']['elapsed']
                    
                    # Vérifier si c'est une vraie correction (petite différence de timing) ou un doublon (nouveau but)
                    # Si la différence est > 2 minutes, c'est probablement un nouveau but (doublon), pas une correction
                    time_difference = abs(new_time - old_time) if old_time is not None else 0
                    
                    if old_time is not None and old_time != new_time and not old_data.get('correction_sent', False):
                        if time_difference <= 2:
                            # Petite différence (≤2 min) = correction de timing du même but
                            player_name = old_data.get('player_name', 'Joueur inconnu')
                            team_name = old_data.get('team_name', 'Équipe inconnue')
                            message = f"⚠️ Correction: Le but de {player_name} ({team_name}) était à {new_time}' (et non {old_time}')"
                            await send_message_to_all_chats(message)
                            log_message(f"Correction de timing envoyée: {old_time}' → {new_time}' pour {player_name}")
                            
                            # Mettre à jour le timing et marquer correction envoyée
                            sent_events_details[event_key_sub]['time'] = new_time
                            sent_events_details[event_key_sub]['correction_sent'] = True
                            continue
                        else:
                            # Grande différence = nouveau but du même joueur (doublon/triplé)
                            log_message(f"Nouveau but détecté pour le même joueur (différence de {time_difference} min): {old_time}' vs {new_time}'")
                            # Ne pas continuer, traiter comme un nouveau but
                    else:
                        # Même timing ou correction déjà envoyée = ignorer
                        continue
                
                if event_key in sent_events:
                    continue

                if event['type'] == "Goal":
                    log_message(f"type == Goal")
                    log_message(f"Données de score récupéré dans match_data pour la variable new_score : {new_score}")
                    log_message(f"Previous score : {previous_score}")
                    log_message(f"Contenu de l'event de type goal :\n {event}\n\n")

                    # Traiter le but avec la fonction helper
                    goal_info, should_update_score, is_first_event = await process_goal_event(
                        event, match_data, elapsed_time, current_score, previous_score,
                        is_first_event, IS_PAID_API, match_status
                    )
                    
                    if goal_info:
                        goal_events.append(goal_info)
                        score_updated = should_update_score
                    else:
                        # Événement déjà traité ou non valide
                        sent_events.add(event_key)
                        continue

                # Gestion des buts annulés par le VAR (doit être au même niveau que Goal, pas imbriqué)
                elif event['type'] == "Var" and "Goal Disallowed" in event['detail']:
                    log_message("But annulé détecté par le VAR")
                    team = event['team']
                    new_score_var = {
                        'home': match_data['goals']['home'],
                        'away': match_data['goals']['away']
                    }
                    # Vérifier si le score a diminué
                    if new_score_var['home'] < current_score['home'] or new_score_var['away'] < current_score['away']:
                        await send_goal_cancelled_message(current_score, new_score_var)
                        previous_score = current_score.copy()
                        current_score = new_score_var.copy()
                    else:
                        log_message("Le score n'a pas changé après l'annulation du but")
                    sent_events.add(event_key)
                    continue

                elif event['type'] == "Card" and event['detail'] == "Red Card":
                    log_message(f"Carton rouge détecté")
                    player = event['player']
                    team = event['team']

                    log_message(f"Contenu de l'event de type carton rouge :\n {event}\n\n")
                    
                    # Vérifiez si le joueur n'est pas None et si son nom est présent
                    if player is not None and 'name' in player:
                        # Vérifiez si l'événement de carton rouge est dans les dernières minutes
                        current_elapsed_time = elapsed_time
                        red_card_elapsed_time = event['time']['elapsed']
                        allowed_difference = -10
                        log_message(f"if {red_card_elapsed_time} >= {current_elapsed_time} + {allowed_difference}")

                        if red_card_elapsed_time is not None and current_elapsed_time is not None and red_card_elapsed_time >= current_elapsed_time + allowed_difference:
                            await send_red_card_message(player, team, event['time']['elapsed'], event)
                            log_message(f"event_key enregistrée : {event_key}")
                            sent_events.add(event_key)
                        else:
                            log_message(f"Le carton rouge a été donné il y a plus de 10 minutes. Le message n'a pas été envoyé.")
                    else:
                        log_message(f"Le nom du joueur est manquant ou 'player' est None, le message de carton rouge n'a pas été envoyé")
                        continue
            
            #Fin de la boucle for event in events:

            # Traiter tous les buts accumulés
            if goal_events:
                # Vérifier si un des buts avait une augmentation significative AVANT de vider la liste
                has_significant_increase = any(goal['significant_increase'] for goal in goal_events)
                
                for goal_info in goal_events:
                    if goal_info['event_key'] not in sent_events:
                        if goal_info['significant_increase']:
                            await send_goal_message_significant_increase_in_score(
                                goal_info['player'],
                                goal_info['team'],
                                goal_info['player_statistics'] if goal_info['player_statistics'] else [],
                                goal_info['elapsed_time'],
                                match_data,
                                goal_info['event']
                            )
                        else:
                            await send_goal_message(
                                goal_info['player'],
                                goal_info['team'],
                                goal_info['player_statistics'] if goal_info['player_statistics'] else [],
                                goal_info['elapsed_time'],
                                match_data,
                                goal_info['event']
                            )
                        sent_events.add(goal_info['event_key'])
                        
                        # ISSUE 6: Stocker les détails de l'événement pour détecter les corrections futures
                        # Utiliser une clé unique incluant le timing approximatif pour distinguer les doublés
                        event_key_sub = f"Goal_{goal_info['player']['id'] if goal_info['player'] else None}_{goal_info['elapsed_time']}"
                        sent_events_details[event_key_sub] = {
                            'time': goal_info['elapsed_time'],
                            'player_id': goal_info['player']['id'] if goal_info['player'] else None,
                            'player_name': goal_info['player']['name'] if goal_info['player'] else 'Inconnu',
                            'team_id': goal_info['team']['id'] if goal_info['team'] else None,
                            'team_name': goal_info['team']['name'] if goal_info['team'] else 'Inconnue',
                            'correction_sent': False
                        }
                        
                        await asyncio.sleep(1)  # Petit délai entre les messages
                
                # Envoyer le score actualisé si plusieurs buts ont été marqués
                if score_updated and has_significant_increase:
                    log_message(f"score_updated is true et augmentation significative détectée")
                    await updated_score(match_data)
                
                goal_events.clear()  # Vider la liste après traitement

            if score_updated:
                # Mettre à jour les scores
                previous_score = current_score.copy()
                log_message(f"previous_score mis à jour avec current_score.copy() pas encore mis à jour avec new_score : {previous_score}")
                current_score = new_score.copy()
                log_message(f"current_score mise à jour avec new_score.copy() : {current_score}")
                score_updated = False

            # Vérifier si un goal a été annulé
            if current_score['home'] < previous_score['home'] or current_score['away'] < previous_score['away']:
                log_message(f"Données previous_score : {previous_score} et current_score : {current_score} avant la condition if current_score['home'] < previous_score['home'] or...")
                log_message("Un goal a été annulé.")
                await send_goal_cancelled_message(previous_score, current_score)
                previous_score = current_score.copy()

            # Si le match est terminé ou s'est terminé en prolongation, envoyez le message de fin et arrêtez de vérifier les événements
            if match_status in ['FT', 'AET', 'PEN']:
                log_message(f"Le match est terminé, status : {match_status}\n")

                # Avant le bloc de conditions
                home_team = None
                away_team = None
                home_score = None
                away_score = None

                if match_data is None:
                    log_message("match_data est None, impossible de continuer le traitement des événements")
                elif 'teams' not in match_data or 'home' not in match_data['teams'] or 'name' not in match_data['teams']['home']:
                    log_message("Certaines informations d'équipe manquent dans match_data")
                elif 'score' not in match_data or 'fulltime' not in match_data['score'] or 'home' not in match_data['score']['fulltime']:
                    log_message("Certaines informations de score manquent dans match_data")
                else:
                    home_team = match_data['teams']['home']['name']
                    away_team = match_data['teams']['away']['name']
                    home_score = match_data['score']['fulltime']['home']
                    away_score = match_data['score']['fulltime']['away']

                log_message(f"Envoi des variables à send_end_message avec chat_ids: home_team: {home_team}, away_team: {away_team}, home_score: {home_score}, away_score: {away_score}, match_statistics: {match_statistics}, events: {events}\n")
                await send_end_message(home_team, away_team, home_score, away_score, match_statistics, events)
                break

        # Si le nombre d'appels à l'API restant est dépassé, on lève une exception et on sort de la boucle !
        except RateLimitExceededError as e:
            log_message(f"Erreur : {e}")
            # Propagez l'exception pour sortir de la boucle
            raise e

        # Pause avant de vérifier à nouveau les événements
        await asyncio.sleep(interval)

# Fonction pour découper un message selon les limites de la plateforme
def split_message_by_platform(message, platform="telegram"):
    """
    Découpe un message selon les limites de caractères de la plateforme
    - Discord: 2000 caractères max
    - Telegram: 4096 caractères max
    
    Retourne une liste de messages découpés intelligemment
    """
    if platform.lower() == "discord":
        max_length = 2000
    elif platform.lower() == "telegram":
        max_length = 4096
    else:
        max_length = 4096  # Par défaut Telegram
    
    # Si le message est plus court que la limite, retourner tel quel
    if len(message) <= max_length:
        return [message]
    
    # Découper intelligemment le message
    messages = []
    current_message = ""
    
    # Diviser par paragraphes (sauts de ligne doubles)
    paragraphs = message.split("\n\n")
    
    for paragraph in paragraphs:
        # Si un paragraphe seul dépasse la limite, le découper par lignes
        if len(paragraph) > max_length:
            lines = paragraph.split("\n")
            for line in lines:
                if len(current_message) + len(line) + 2 <= max_length:
                    current_message += line + "\n"
                else:
                    if current_message:
                        messages.append(current_message.strip())
                    current_message = line + "\n"
        else:
            # Ajouter le paragraphe au message courant
            if len(current_message) + len(paragraph) + 4 <= max_length:
                current_message += paragraph + "\n\n"
            else:
                if current_message:
                    messages.append(current_message.strip())
                current_message = paragraph + "\n\n"
    
    # Ajouter le dernier message
    if current_message:
        messages.append(current_message.strip())
    
    # Ajouter des indicateurs de partie (1/3, 2/3, etc.) si plusieurs messages
    if len(messages) > 1:
        formatted_messages = []
        for i, msg in enumerate(messages, 1):
            indicator = f"\n\n[Partie {i}/{len(messages)}]"
            if len(msg) + len(indicator) <= max_length:
                formatted_messages.append(msg + indicator)
            else:
                formatted_messages.append(msg)
        return formatted_messages
    
    return messages

# Cette fonction reçoit un message, puis envoie le message à chaque chat_id
async def send_message_to_all_chats(message, language=LANGUAGE):
    log_message("send_message_to_all_chats() appelée.")

    # Traduction du message si la langue n'est pas le français en faisant appel à la fonction spévifique utilisant gpt3.5
    if language.lower() != "french":
        log_message(f"Traduction du message car la langue détectée est {language}.")
        message = await translate_message(message, language)
    
    log_message(f"Contenu du message envoyé : {message}")

    # Pour Telegram:
    if USE_TELEGRAM:
        log_message("Lecture des IDs de chat enregistrés pour Telegram...")
        try:
            with open("telegram_chat_ids.json", "r") as file:
                chat_ids = json.load(file)
                log_message(f"Chat IDs chargés depuis le fichier telegram_chat_ids.json : {chat_ids}")
            
            # Découper le message selon les limites de Telegram (4096 caractères)
            message_parts = split_message_by_platform(message, "telegram")
            log_message(f"Message découpé en {len(message_parts)} partie(s) pour Telegram")
            
            for chat_id in chat_ids:
                try:
                    for part in message_parts:
                        # Utiliser Markdown legacy pour compatibilité avec le formatage Discord
                        await bot.send_message(chat_id=chat_id, text=part, parse_mode="Markdown")
                        await asyncio.sleep(0.5)  # Délai entre les messages pour éviter le rate limiting
                except TelegramForbiddenError:
                    # Évite de log si le bot a été bloqué par des utilisateurs
                    continue
                except TelegramBadRequest as e:
                    log_message(f"Erreur lors de l'envoi du message à Telegram (BadRequest) : {e}")
                except ClientConnectorError as e:
                    log_message(f"Erreur lors de l'envoi du message à Telegram (ClientConnectorError) : {e}")
                except TelegramNetworkError as e:
                    log_message(f"Erreur lors de l'envoi du message à Telegram (NetworkError) : {e}")
                except TelegramAPIError as e:
                    if "user is deactivated" not in str(e).lower():
                        log_message(f"Erreur lors de l'envoi du message à Telegram : {e}")
                except Exception as e:
                    log_message(f"Erreur inattendue lors de l'envoi du message à Telegram : {e}")
        except FileNotFoundError:
            log_message("Fichier telegram_chat_ids.json non trouvé")
        except json.JSONDecodeError:
            log_message("Erreur de décodage JSON dans telegram_chat_ids.json")
        except Exception as e:
            log_message(f"Erreur lors de la lecture des IDs Telegram: {e}")

    # Pour Discord:
    if USE_DISCORD:
        log_message("Lecture des IDs de channel pour Discord...")

        # Utilisez le chemin correct pour le fichier discord_channels.json
        try:
            if os.path.exists(discord_channels_path):
                with open(discord_channels_path, "r") as file:
                    channels = json.load(file)
                
                # Découper le message selon les limites de Discord (2000 caractères)
                message_parts = split_message_by_platform(message, "discord")
                log_message(f"Message découpé en {len(message_parts)} partie(s) pour Discord")
                
                for channel_id in channels:
                    channel = bot_discord.get_channel(channel_id)
                    if channel and isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                        try:
                            for part in message_parts:
                                await channel.send(part)
                                await asyncio.sleep(0.5)  # Délai entre les messages pour éviter le rate limiting
                        except discord.Forbidden as e:
                            # Évite de log si le bot a été bloqué par des utilisateurs, concerne aussi d'autres problèmes de permission...
                            continue 
                        except discord.NotFound as e:
                            log_message(f"Erreur: Canal Discord {channel_id} non trouvé : {e}")
                        except discord.HTTPException as e:
                            log_message(f"Erreur HTTP lors de l'envoi du message au canal Discord {channel_id}: {e}")
                        except discord.ClientException as e:
                            log_message(f"Erreur: Argument invalide pour le canal Discord {channel_id}: {e}")
                        except Exception as e:
                            log_message(f"Erreur inattendue lors de l'envoi du message à Discord : {e}")
            else:
                log_message("Erreur: Le fichier discord_channels.json n'a pas été trouvé.")
        except json.JSONDecodeError:
            log_message("Erreur de décodage JSON dans discord_channels.json")
        except Exception as e:
            log_message(f"Erreur lors de la lecture des IDs Discord: {e}")

# Envoie un message lorsqu'un match est détecté le jour même
async def send_match_today_message(match_start_time, fixture_id, current_league_id, teams, league, round_info, venue, city):
    log_message("send_match_today_message() appelée.")
    # Appeler l'API ChatGPT
    chatgpt_analysis = await call_chatgpt_api_matchtoday(match_start_time, teams, league, round_info, venue, city)
    message = f"🤖 : {chatgpt_analysis}"
    
    # Envoyer le message du match à tous les chats.
    await send_message_to_all_chats(message)

# Envoie un message de début de match aux utilisateurs avec des informations sur le match, les compositions des équipes.
async def send_compo_message(match_data, predictions=None, fixture_id=None, teams=None, league=None, round_info=None, venue=None, city=None):
    log_message("send_compo_message() appelée.")
    log_message(f"Informations reçues par l'API : match_data={match_data}, predictions={predictions}")

    if match_data is None:
        log_message("Erreur : match_data est None dans send_compo_message")
        message = "🤖 : Désolé, je n'ai pas pu obtenir les informations sur la composition des équipes pour le moment."
        chatgpt_analysis = None
    else:
        # Appeler l'API ChatGPT
        chatgpt_analysis = await call_chatgpt_api_compomatch(match_data, predictions)
        message = "🤖 : " + chatgpt_analysis
        
        # Sauvegarder l'analyse pré-match (compositions) dans l'historique
        if fixture_id and chatgpt_analysis:
            match_info = {
                "date": datetime.datetime.now().isoformat(),
                "league": league if league else "Unknown",
                "round": round_info if round_info else "Unknown",
                "teams": teams if teams else {},
                "score": {},
                "venue": venue if venue else "Unknown",
                "city": city if city else "Unknown"
            }
            save_match_analysis(fixture_id, match_info, chatgpt_analysis)

    # Envoyer le message du match à tous les chats.
    await send_message_to_all_chats(message)

# Envoie un message de début de match aux utilisateurs avec des informations sur le match, les compositions des équipes.
async def send_start_message():
    log_message("send_start_message() appelée.")
    if IS_PAID_API:
        message = f"🤖 : Le match commence !"
        # Envoyer le message du match à tous les chats.
        await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer d'un but marqué lors du match en cours, y compris les informations sur le joueur, l'équipe et les statistiques.
async def send_goal_message(player, team, player_statistics, elapsed_time, match_data, event):
    log_message("send_goal_message() appelée.")
    #log_message(f"Player: {player}")
    #log_message(f"Team: {team}")
    #log_message(f"Player statistics: {player_statistics}")
    log_message(f"Minute du match pour le goal : {elapsed_time}")
    home_score = match_data['goals']['home']
    away_score = match_data['goals']['away']
    # Utilisez team['name'] pour obtenir uniquement le nom de l'équipe
    message = f"⚽️ {elapsed_time}' - {team['name']}\n {match_data['teams']['home']['name']} {home_score} - {away_score} {match_data['teams']['away']['name']}\n\n"
    # Pour passer le score à l'api de chatgpt
    score_string = f"{match_data['teams']['home']['name']} {home_score} - {away_score} {match_data['teams']['away']['name']}"
    # Appeler l'API ChatGPT  
    chatgpt_analysis = await call_chatgpt_api_goalmatch(player, team, player_statistics, elapsed_time, event, score_string)
    message += "🤖 Infos sur le but :\n" + chatgpt_analysis
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer d'un but marqué lors du match en cours SANS LE SCORE !, y compris les informations sur le joueur, l'équipe et les statistiques.
async def send_goal_message_significant_increase_in_score(player, team, player_statistics, elapsed_time, match_data, event):
    log_message("send_goal_message_significant_increase_in_score() appelée.")
    #log_message(f"Player: {player}")
    #log_message(f"Team: {team}")
    #log_message(f"Player statistics: {player_statistics}")
    log_message(f"Minute du match pour le goal : {elapsed_time}")
    home_score = match_data['goals']['home']
    away_score = match_data['goals']['away']
    # Utilisez team['name'] pour obtenir uniquement le nom de l'équipe
    message = f"⚽️ {elapsed_time}' - {team['name']}\n\n"
    # Pour passer le score à l'api de chatgpt
    score_string = f"{match_data['teams']['home']['name']} {home_score} - {away_score} {match_data['teams']['away']['name']}"
    # Appeler l'API ChatGPT  
    chatgpt_analysis = await call_chatgpt_api_goalmatch(player, team, player_statistics, elapsed_time, event, score_string)
    message += "🤖 Infos sur le but :\n" + chatgpt_analysis
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer d'un but marqué lors de la séance au tir aux but
async def send_shootout_goal_message(player, team, player_statistics, event):
    log_message("send_shootout_goal_message() appelée.")
    #log_message(f"Player: {player}")
    #log_message(f"Team: {team}")
    #log_message(f"Player statistics: {player_statistics}")
    # Utilisez team['name'] pour obtenir uniquement le nom de l'équipe
    message = f"⚽️ Pénalty réussi' - {team['name']}\n\n"
    # Appeler l'API ChatGPT  
    chatgpt_analysis = await call_chatgpt_api_shootout_goal_match(player, team, player_statistics, event)
    message += "🤖 Infos sur le pénalty :\n" + chatgpt_analysis
    await send_message_to_all_chats(message)    

# Envoie juste le score du match si plusieurs buts marqués dans le même intervalle 
async def updated_score(match_data):
    log_message("updated_score() appelée.")
    home_score = match_data['goals']['home']
    away_score = match_data['goals']['away']
    score_string = f"{match_data['teams']['home']['name']} {home_score} - {away_score} {match_data['teams']['away']['name']}"
    message = f"🤖 : Score actualisé après les buts : {score_string}"
    await send_message_to_all_chats(message)    

# Envoie un message si un but est annulé
async def send_goal_cancelled_message(previous_score, current_score):
    log_message("send_goal_cancelled_message() appelée.")
    message = f"❌ But annulé ! Le score revient à {current_score['home']} - {current_score['away']}."
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer d'un carton rouge lors du match en cours, y compris les informations sur le joueur et l'équipe.
async def send_red_card_message(player, team, elapsed_time, event):
    log_message("send_red_card_message() appelée.")
    message = f"🟥 Carton rouge ! {elapsed_time}'\n ({team['name']})\n\n"
    # Appeler l'API ChatGPT  
    chatgpt_analysis = await call_chatgpt_api_redmatch(player, team, elapsed_time, event)
    message += "🤖 Infos sur le carton rouge :\n" + chatgpt_analysis    
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer qu'un pénalty a été manqué pendant le match
async def send_missed_penalty_message(player, team, elapsed_time):
    log_message("send_missed_penalty_message() appelée.")
    message = f"❌ Pénalty manqué ! {elapsed_time}'\n ({team['name']})\n\n"
    message += f"🤖 : {player['name']} a manqué son pénalty à la {elapsed_time}ème minute."
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer que le suivi est mis en pause pour les tirs aux but qu'un résumé du match sera envoyé à la fin du match
async def pause_for_penalty_shootout():
    log_message("pause_for_penalty_shootout appelée")
    message = "🤖 : Le suivi est mis en pause pour les tirs aux but mais je vous enverrai un résumé du match à la fin.\n"
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer que le match a été interrompu
async def notify_match_interruption():
    log_message("notify_match_interruption appelée")
    message = "🤖 : Le match a été interrompu !\n"   
    await send_message_to_all_chats(message)   

# Envoie un message aux utilisateurs pour informer qu'on a atteint le maximum de call à l'api et qu'on doit stopper le suivi du match
async def notify_users_max_api_requests_reached():
    log_message("notify_users_max_api_requests_reached appelée")
    message = "🤖 : Le nombre maximum de requêtes à l'api de foot a été atteinte. Je dois malheureusement mettre fin au suivi du match.\n"   
    await send_message_to_all_chats(message)          

# Fonction pour formater les événements bruts en cas d'indisponibilité de l'API Poe
def format_season_stats_for_prompt(season_stats, team_name):
    """
    Version ultra-compacte des stats de saison destinée à être injectée dans
    le prompt LLM (analyse de début et de fin de match). Vise ~50-80 tokens
    pour ne pas alourdir la consommation Poe en fin de saison.
    Renvoie une string vide si stats indisponibles.
    """
    if not season_stats or not isinstance(season_stats, dict):
        return ""
    try:
        league = (season_stats.get('league', {}) or {})
        league_name = league.get('name', 'compétition')
        season_year = league.get('season', '')

        fixtures = season_stats.get('fixtures', {}) or {}
        played_total = (fixtures.get('played', {}) or {}).get('total', 0) or 0
        if played_total == 0:
            return ""
        wins_total = (fixtures.get('wins', {}) or {}).get('total', 0) or 0
        draws_total = (fixtures.get('draws', {}) or {}).get('total', 0) or 0
        loses_total = (fixtures.get('loses', {}) or {}).get('total', 0) or 0

        goals = season_stats.get('goals', {}) or {}
        gf = ((goals.get('for', {}) or {}).get('total', {}) or {}).get('total', 0) or 0
        ga = ((goals.get('against', {}) or {}).get('total', {}) or {}).get('total', 0) or 0

        clean_sheet = (season_stats.get('clean_sheet', {}) or {}).get('total', 0) or 0
        failed = (season_stats.get('failed_to_score', {}) or {}).get('total', 0) or 0

        form_full = season_stats.get('form') or ""
        form_recent = form_full[-5:] if form_full else ""

        # Format compact en une ligne dense
        season_label = f" {season_year}" if season_year else ""
        line = (
            f"STATS SAISON {team_name} en {league_name}{season_label} : "
            f"{played_total}J ({wins_total}V/{draws_total}N/{loses_total}D), "
            f"buts {gf}/{ga}, clean sheets {clean_sheet}, sans marquer {failed}"
        )
        if form_recent:
            line += f", forme 5 derniers : {form_recent}"
        return line
    except Exception as e:
        log_message(f"Erreur format_season_stats_for_prompt : {e}", "ERROR")
        return ""

def format_season_stats_for_display(season_stats, team_name, league_name):
    """
    Formate de manière compacte les statistiques de saison de l'équipe
    pour affichage en fin de match. Compatible Telegram + Discord (Markdown legacy).
    Renvoie une string vide si les données sont indisponibles.
    """
    if not season_stats or not isinstance(season_stats, dict):
        return ""

    try:
        fixtures = season_stats.get('fixtures', {}) or {}
        played = fixtures.get('played', {}) or {}
        wins = fixtures.get('wins', {}) or {}
        draws = fixtures.get('draws', {}) or {}
        loses = fixtures.get('loses', {}) or {}

        played_total = played.get('total', 0) or 0
        wins_total = wins.get('total', 0) or 0
        draws_total = draws.get('total', 0) or 0
        loses_total = loses.get('total', 0) or 0

        goals = season_stats.get('goals', {}) or {}
        gf = (goals.get('for', {}) or {}).get('total', {}) or {}
        ga = (goals.get('against', {}) or {}).get('total', {}) or {}
        goals_for = gf.get('total', 0) or 0
        goals_against = ga.get('total', 0) or 0
        goal_diff = goals_for - goals_against

        clean_sheet = (season_stats.get('clean_sheet', {}) or {}).get('total', 0) or 0
        failed = (season_stats.get('failed_to_score', {}) or {}).get('total', 0) or 0

        # Forme : 5 derniers matchs (les plus récents = fin de la chaîne)
        form_full = season_stats.get('form') or ""
        form_recent = form_full[-5:] if form_full else ""
        # Mapper W/D/L vers emojis pour lisibilité
        form_map = {"W": "🟢", "D": "⚪", "L": "🔴"}
        form_emoji = "".join(form_map.get(c, c) for c in form_recent) if form_recent else "—"

        # Si aucun match joué, ne rien afficher
        if played_total == 0:
            return ""

        # En-tête sobre, sans titre Markdown lourd (compat Telegram parse_mode=Markdown)
        lines = []
        lines.append(f"\n📈 *Saison {team_name} — {league_name}*")
        lines.append(f"• Bilan : {played_total} J | {wins_total}V {draws_total}N {loses_total}D")
        sign = "+" if goal_diff > 0 else ""
        lines.append(f"• Buts : {goals_for} pour / {goals_against} contre (diff {sign}{goal_diff})")
        lines.append(f"• Clean sheets : {clean_sheet} | Sans marquer : {failed}")
        if form_recent:
            lines.append(f"• Forme (5 derniers) : {form_emoji}")

        return "\n".join(lines)
    except Exception as e:
        log_message(f"Erreur lors du formatage des stats de saison : {e}", "ERROR")
        return ""

def format_raw_events(events, home_team, away_team):
    """Formate les événements bruts de l'API football en cas d'indisponibilité de l'API Poe"""
    if not events:
        return "Aucun événement enregistré."
    
    formatted = "📋 ÉVÉNEMENTS DU MATCH:\n"
    for event in events:
        try:
            time_elapsed = event.get('time', {}).get('elapsed', '?')
            team_name = event.get('team', {}).get('name', 'Unknown')
            player_name = event.get('player', {}).get('name', 'Unknown')
            event_type = event.get('type', 'Unknown')
            event_detail = event.get('detail', '')
            
            # Formater l'événement de manière lisible
            if event_type == "Goal":
                formatted += f"⚽️ {time_elapsed}' - {team_name}: {player_name} marque"
                if event_detail and event_detail != "Normal Goal":
                    formatted += f" ({event_detail})"
                formatted += "\n"
            elif event_type == "Card":
                if event_detail == "Red Card":
                    formatted += f"🟥 {time_elapsed}' - {team_name}: {player_name} carton rouge\n"
                elif event_detail == "Yellow Card":
                    formatted += f"🟨 {time_elapsed}' - {team_name}: {player_name} carton jaune\n"
            elif event_type == "Substitution":
                formatted += f"🔄 {time_elapsed}' - {team_name}: {player_name} remplacé\n"
            elif event_type == "Var":
                formatted += f"📺 {time_elapsed}' - VAR: {event_detail}\n"
        except Exception as e:
            log_message(f"Erreur lors du formatage d'un événement : {e}")
            continue
    
    return formatted

# Envoie un message de fin de match aux utilisateurs avec le score final.
async def send_end_message(home_team, away_team, home_score, away_score, match_statistics, events):
    log_message("send_end_message() appelée.")
    message = f"🏁 Fin du match !\n{home_team} {home_score} - {away_score} {away_team}\n\n"
    
    # Appeler l'API ChatGPT et ajouter la réponse à la suite des statistiques du match
    chatgpt_analysis = await call_chatgpt_api_endmatch(match_statistics, events, home_team, home_score, away_score, away_team)
    
    # Vérifier si l'analyse est un message d'erreur (commence par "🤖 :")
    if chatgpt_analysis.startswith("🤖 :"):
        log_message("API Poe indisponible, envoi des événements bruts à la place")
        message += "⚠️ Analyse IA indisponible, voici les événements du match :\n\n"
        message += format_raw_events(events, home_team, away_team)
        
        # Ajouter les statistiques si disponibles
        if match_statistics and len(match_statistics) >= 2:
            message += "\n📊 STATISTIQUES:\n"
            try:
                for home_stat, away_stat in zip(match_statistics[0].get('statistics', []), match_statistics[1].get('statistics', [])):
                    if 'type' in home_stat and 'value' in home_stat:
                        message += f"• {home_stat['type']}: {home_stat['value']} - {away_stat.get('value', '?')}\n"
            except Exception as e:
                log_message(f"Erreur lors du formatage des statistiques : {e}")
    else:
        message += "🤖 Mon analyse :\n" + chatgpt_analysis
    
    # Sauvegarder l'analyse post-match dans l'historique
    league_name_for_stats = None
    try:
        data = load_match_history()
        if data.get("matches"):
            # Mettre à jour le dernier match avec l'analyse post-match
            last_match = data["matches"][-1]
            last_match["score"] = {
                "home": home_score,
                "away": away_score
            }
            last_match["post_match_analysis"] = chatgpt_analysis
            league_name_for_stats = last_match.get("league")
            save_match_history(data)
            log_message(f"Analyse post-match sauvegardée pour le match {last_match.get('fixture_id')}")
    except Exception as e:
        log_message(f"Erreur lors de la sauvegarde de l'analyse post-match : {e}")

    # Ajouter les statistiques pertinentes de la saison pour notre équipe dans la ligue du match.
    # On réutilise le cache mémoire alimenté avant la compo (zéro appel API ici).
    # Fallback : si le cache est vide (ex: échec à la compo), on tente un appel tardif.
    try:
        global current_season_stats, current_league_id
        season_stats = current_season_stats
        if not season_stats and current_league_id and TEAM_ID and SEASON_ID:
            log_message("Cache stats saison vide, fallback : tentative de récupération en fin de match.")
            season_stats = await get_team_season_statistics(current_league_id, TEAM_ID, SEASON_ID)
        if season_stats:
            if not league_name_for_stats:
                league_name_for_stats = (season_stats.get('league', {}) or {}).get('name', 'Compétition')
            stats_block = format_season_stats_for_display(season_stats, TEAM_NAME, league_name_for_stats)
            if stats_block:
                message += "\n" + stats_block
    except Exception as e:
        log_message(f"Erreur lors de l'ajout des stats de saison au message de fin : {e}", "ERROR")

    await send_message_to_all_chats(message)
    
    # Afficher le résumé des coûts à la fin du match
    log_cost_summary()

# DEBUT DE CODE POUR CONFIGURATION IA

# Fonction pour traduire les messages dans la langue désirée
async def translate_message(message, language):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
        
    log_message(f"La langue détectée n'est pas le français donc on lance la traduction")
    translation_prompt = f"Translate the following sentence from french to {language}: {message}"
    translation_data = {
        "model": GPT_MODEL_NAME_TRANSLATION,
        "messages": [{"role": "user", "content": translation_prompt}],
        "max_tokens": 2000
    }
    
    async with httpx.AsyncClient() as client:
        try:
            translation_response = await client.post("https://api.poe.com/v1/chat/completions", headers=headers, json=translation_data, timeout=60.0)
            translation_response.raise_for_status()
            response_data = translation_response.json()
            translated_message = response_data["choices"][0]["message"]["content"].strip()
            
            # Tracker les tokens et coûts si disponibles
            if ENABLE_COST_TRACKING and "usage" in response_data:
                input_tokens = response_data["usage"].get("prompt_tokens", 0)
                output_tokens = response_data["usage"].get("completion_tokens", 0)
                track_api_cost(input_tokens, output_tokens, "translate_message")
            
            return translated_message
        except httpx.HTTPError as e:
            log_message(f"Error during message translation with the Poe API: {e}")
            return f"🤖 : Sorry, an error occurred while communicating with the translation API."
        except Exception as e:
            log_message(f"Unexpected error during message translation: {e}")
            return f"🤖 : Sorry, an unexpected error occurred during message translation."

# Fonction générique pour appeler l'API ChatGPT avec retry
async def call_chatgpt_api(data, max_retries=3):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Appel initial à Grok-4-Fast-Reasoning pour obtenir le message
                response_json = await client.post("https://api.poe.com/v1/chat/completions", headers=headers, json=data)
                response_json.raise_for_status()
                response_data = response_json.json()
                
                # Vérifier que la réponse contient les données attendues
                if "choices" not in response_data or not response_data["choices"]:
                    log_message(f"Réponse API invalide (pas de choices) : {response_data}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Backoff exponentiel
                        continue
                    return f"🤖 : Désolé, l'API a retourné une réponse invalide."
                
                message = response_data["choices"][0]["message"]["content"].strip()
                
                # Tracker les tokens et coûts si disponibles
                if ENABLE_COST_TRACKING and "usage" in response_data:
                    input_tokens = response_data["usage"].get("prompt_tokens", 0)
                    output_tokens = response_data["usage"].get("completion_tokens", 0)
                    track_api_cost(input_tokens, output_tokens, f"call_chatgpt_api({data.get('model', 'unknown')})")
                 
                log_message(f"Succès de la récupération de la réponse {data.get('model', 'unknown')}")
                return message

        except httpx.TimeoutException as e:
            log_message(f"Timeout lors de l'appel à l'API Poe (tentative {attempt + 1}/{max_retries}) : {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Backoff exponentiel
                continue
            return f"🤖 : Désolé, l'API Poe ne répond pas (timeout). Veuillez réessayer plus tard."
        
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            log_message(f"Erreur HTTP {status_code} lors de l'appel à l'API Poe (tentative {attempt + 1}/{max_retries}) : {e}")
            
            # Gestion spécifique des codes d'erreur
            if status_code == 401:
                log_message("Erreur d'authentification : Vérifiez votre clé API Poe")
                return f"🤖 : Erreur d'authentification API. Vérifiez votre clé API."
            elif status_code == 429:
                log_message("Rate limit atteint, attente avant retry...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (2 ** attempt))  # Backoff plus long pour rate limit
                    continue
                return f"🤖 : Trop de requêtes. Veuillez réessayer dans quelques instants."
            elif status_code >= 500:
                log_message(f"Erreur serveur {status_code}, retry...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return f"🤖 : L'API Poe rencontre des problèmes. Veuillez réessayer plus tard."
            else:
                log_message(f"Erreur HTTP {status_code}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return f"🤖 : Erreur lors de la communication avec l'API Poe (code {status_code})."
        
        except httpx.NetworkError as e:
            log_message(f"Erreur réseau lors de l'appel à l'API Poe (tentative {attempt + 1}/{max_retries}) : {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return f"🤖 : Erreur réseau. Vérifiez votre connexion Internet."
        
        except Exception as e:
            log_message(f"Erreur inattendue lors de l'appel à l'API Poe (tentative {attempt + 1}/{max_retries}) : {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return f"🤖 : Désolé, une erreur inattendue s'est produite."
    
    # Si tous les retries ont échoué
    log_message(f"Tous les {max_retries} tentatives ont échoué pour l'appel API")
    return f"🤖 : Impossible de contacter l'API après {max_retries} tentatives. Veuillez réessayer plus tard."

# Analyse pour l'heure de début du match
async def call_chatgpt_api_matchtoday(match_start_time, teams, league, round_info, venue, city):
    log_message(f"Informations reçues par l'API : match_start_time={match_start_time}, teams={teams}, league={league}, round_info={round_info}, venue={venue}, city={city}")
    
    # Construire la saison complète (ex: "2025-2026" si SEASON_ID = "2025")
    season_year = int(SEASON_ID)
    current_season = f"{season_year}-{season_year + 1}"
    
    user_message = (f"SAISON ACTUELLE : {current_season}\n\n"
                    f"Les informations du match qui a lieu aujourd'hui sont les suivantes : \n"
                    f"Ligue actuelle : {league}\n"
                    f"Tour : {round_info}\n"
                    f"Équipes du match : {teams['home']} contre {teams['away']}\n"
                    f"Stade et ville du stade : {venue}, {city}\n"
                    f"Heure de début : {match_start_time}\n"
                    f"L'heure actuelle est : {datetime.datetime.now()}\n"
                    f"Équipe analysée : {TEAM_NAME}")
    system_prompt = (f"Tu es un journaliste sportif expert spécialisé dans l'analyse de matchs de football. "
                    f"IMPORTANT : Nous sommes en saison {current_season}. "
                    f"Tu dois te baser UNIQUEMENT sur les informations fournies dans le message utilisateur. "
                    f"N'utilise JAMAIS tes connaissances sur les saisons antérieures à {current_season}. "
                    f"Fais une présentation simple et factuelle du match qui aura lieu aujourd'hui **en 3-4 phrases maximum** : "
                    f"annonce les équipes qui s'affrontent, la compétition, le lieu et l'heure. "
                    f"**Traduis les noms de villes dans la langue {LANGUAGE}** (ex: Geneva → Genève si french, Geneva → Genf si german, etc.). "
                    f"Reste général sans inventer de détails sur la forme des équipes ou les enjeux. "
                    f"Embellis la présentation avec des émojis pertinents. "
                    f"Sois concis, engageant et informatif. "
                    f"FORMATAGE : Utilise un formatage Markdown simple compatible avec Discord et Telegram (gras avec **texte**, italique avec *texte*, pas de titres avec # ni de formatage complexe).")
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 800
    }
    return await call_chatgpt_api(data)

# Analyse de début de match avec des smileys
async def call_chatgpt_api_compomatch(match_data, predictions=None):
    log_message(f"Informations reçues par l'API : match_data={match_data}, predictions={predictions}")
    
    # Construire la saison complète
    season_year = int(SEASON_ID)
    current_season = f"{season_year}-{season_year + 1}"
    
    user_message = f"SAISON ACTUELLE : {current_season}\n\n"
    
    if match_data is not None:
        user_message += f"Voici les informations du match qui va commencer d'ici quelques minutes : {match_data}"
    else:
        user_message += "Aucune information sur le match n'est disponible pour le moment."

    if predictions:
        user_message += f"\nPrédictions de l'issue du match : {predictions['winner']['name']} (Comment: {predictions['winner']['comment']})"

    # Ajouter les stats de saison de l'équipe dans la ligue où le match est joué (contexte bref)
    season_stats_line = format_season_stats_for_prompt(current_season_stats, TEAM_NAME) if current_season_stats else ""
    if season_stats_line:
        user_message += f"\n\n{season_stats_line}"

    # Ajouter l'historique des 5 derniers matchs pour enrichir le contexte
    last_matches = get_last_n_matches(5)
    if last_matches and len(last_matches) > 0:
        match_history_context = format_match_history_for_context(last_matches)
        user_message += f"\n\n{match_history_context}"

    system_prompt = (f"Tu es un journaliste sportif expert spécialisé dans l'analyse tactique de matchs de football. "
                    f"IMPORTANT : Nous sommes en saison {current_season}. "
                    f"Tu dois te baser UNIQUEMENT sur les informations fournies (compositions, formations, prédictions si disponibles, stats de saison dans la compétition du match, historique des matchs). "
                    f"N'utilise JAMAIS tes connaissances sur les saisons antérieures à {current_season}. "
                    f"\n\n"
                    f"**STRUCTURE OBLIGATOIRE DE TA RÉPONSE** (utilise des sauts de ligne entre chaque section) :\n"
                    f"1️⃣ **COMPOSITIONS** (2-3 phrases) : Analyse les formations et joueurs clés des deux équipes\n"
                    f"2️⃣ **CONTEXTE RÉCENT** (2-3 phrases) : Résume brièvement la forme récente basée sur l'historique fourni\n"
                    f"3️⃣ **PRONOSTIC** (1-2 phrases) : Donne ton pronostic basé sur les données (prédictions si disponibles)\n"
                    f"\n"
                    f"Utilise des émojis pertinents (⚽🛡️🔥📊) pour aérer. "
                    f"Sois concis, factuel et engageant. Chaque section doit être séparée par un saut de ligne.\n"
                    f"FORMATAGE : Utilise un formatage Markdown simple compatible avec Discord et Telegram (gras avec **texte**, italique avec *texte*, pas de titres avec # ni de formatage complexe).")
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 1500
    }
    
    return await call_chatgpt_api(data)

# Commentaire sur le goal récent
async def call_chatgpt_api_goalmatch(player, team, player_statistics, elapsed_time, event, score_string):
    log_message(f"Informations reçues par l'API : player={player}, team={team}, player_statistics={player_statistics}, elapsed_time={elapsed_time}, event={event}, score_string={score_string}")
    user_message = f"Le joueur qui a marqué : {player} "
    user_message += f"L'équipe pour laquelle le but a été comptabilisé : {team}"
    if player_statistics:
        user_message += f"Les statistiques du joueur pour ce match qui a marqué (IGNORE COMPLÈTEMENT le temps de jeu 'minutes' du joueur) : {player_statistics} "
    user_message += f"La minute du match quand le goal a été marqué : {elapsed_time} "
    user_message += f"Le score actuel après le but qui vient d'être marqué pour contextualisé ta réponse , mais ne met pas le score dans ta réponse : {score_string} "
    user_message += f"Voici les détails de l'événement goal du match en cours {event}, utilise les informations pertinentes liées au goal marqué à la {elapsed_time} minute sans parler d'assist!"

    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, commente moi le goal le plus récent du match qui est en cours, tu ne dois pas faire plus de deux phrases courtes en te basant sur les informations que je te donne comme qui est le buteur et ses statistiques (si disponible). **INTERDIT ABSOLU de mentionner le temps de jeu du joueur (minutes jouées) car cette donnée est souvent incorrecte.** Concentre-toi sur le type de but, la position du joueur, et les statistiques de passes/tirs uniquement. FORMATAGE : Utilise un formatage Markdown simple compatible avec Discord et Telegram (gras avec **texte**, italique avec *texte*, pas de titres avec # ni de formatage complexe)."
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 500
    }
    return await call_chatgpt_api(data)

# Commentaire sur le goal lors de la séance de tir aux penaltys
async def call_chatgpt_api_shootout_goal_match(player, team, player_statistics, event):
    log_message(f"Informations reçues par l'API : player={player}, team={team}, player_statistics={player_statistics}, event={event}")
    user_message = f"Le joueur qui a marqué le pénalty lors de la séance aux tirs aux buts : {player} "
    user_message += f"L'équipe pour laquelle le but a été comptabilisé : {team}"
    if player_statistics:  
        user_message += f"Les statistiques du joueur pour ce match qui a marqué (n'utilise pas le temps de jeu du joueur): {player_statistics} "
    user_message += f"Voici les détails de l'événement goal du match en cours {event}."

    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, commente moi le goal lors de cette séance aux tirs au but, tu ne dois pas faire plus de deux phrases courtes en te basant sur les informations que je te donne. FORMATAGE : Utilise un formatage Markdown simple compatible avec Discord et Telegram (gras avec **texte**, italique avec *texte*, pas de titres avec # ni de formatage complexe)."
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 1000
    }
    return await call_chatgpt_api(data)

# Commentaire sur le carton rouge 
async def call_chatgpt_api_redmatch(player, team, elapsed_time, event):
    log_message(f"Informations reçues par l'API : player={player}, team={team}, elapsed_time={elapsed_time}, event={event}")
    user_message = (f"Le joueur qui a pris un carton rouge : {player} "
                    f"L'équipe dont il fait parti : {team} "
                    f"La minute du match à laquelle il a pris un carton rouge : {elapsed_time} "
                    f"Voici les détails de l'événement du carton rouge du match en cours {event}, utilise uniquement les informations pertinentes liées à ce carton rouge de la {elapsed_time} minute.")
    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, commente moi ce carton rouge le plus récent du match qui est en cours, tu ne dois pas faire plus de deux phrases courtes en te basant sur les informations que je te donne. FORMATAGE : Utilise un formatage Markdown simple compatible avec Discord et Telegram (gras avec **texte**, italique avec *texte*, pas de titres avec # ni de formatage complexe)."
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 1000
    }
    return await call_chatgpt_api(data)

# Analyse de fin de match
async def call_chatgpt_api_endmatch(match_statistics, events, home_team, home_score, away_score, away_team):
    log_message(f"Informations reçues par l'API : match_statistics={match_statistics}, events={events}")
    
    # Construire la saison complète
    season_year = int(SEASON_ID)
    current_season = f"{season_year}-{season_year + 1}"
    
    # Récupérer l'analyse pré-match et l'historique des 5 derniers matchs
    last_matches = get_last_n_matches(5)
    match_history_context = format_match_history_for_context(last_matches)
    
    # Récupérer l'analyse pré-match du match actuel (le dernier match dans l'historique)
    pre_match_analysis = ""
    if last_matches and len(last_matches) > 0:
        pre_match_analysis = last_matches[-1].get("pre_match_analysis", "")
        if not pre_match_analysis:
            pre_match_analysis = ""
    
    # Score final
    user_message = f"SAISON ACTUELLE : {current_season}\n\n"
    user_message += f"📊 Score Final:\n{home_team} {home_score} - {away_score} {away_team}\n\n"
    
    # Ajouter l'analyse pré-match pour contexte
    if pre_match_analysis:
        user_message += f"📋 CONTEXTE PRÉ-MATCH:\n{pre_match_analysis}\n\n"

    # Ajouter les stats de saison de l'équipe dans la ligue où le match est joué (contexte bref)
    season_stats_line = format_season_stats_for_prompt(current_season_stats, TEAM_NAME) if current_season_stats else ""
    if season_stats_line:
        user_message += f"{season_stats_line}\n\n"

    # Ajouter l'historique des matchs
    user_message += f"{match_history_context}\n\n"
    
    # Formater les événements du match
    formatted_events = ["📢 Événements du Match:"]
    if events:
        for event in events:
            time_elapsed = event['time']['elapsed']
            time_extra = event['time']['extra']
            team_name = event['team']['name']
            player_name = event['player']['name']
            event_type = event['type']
            event_detail = event['detail']
            formatted_event = f"• À {time_elapsed}{'+' + str(time_extra) if time_extra else ''} min, {team_name} - {player_name} {event_detail} ({event_type})"
            formatted_events.append(formatted_event)
        user_message += '\n'.join(formatted_events)

    # Traitement des match_statistics
    if len(match_statistics) >= 2 and 'statistics' in match_statistics[0] and 'statistics' in match_statistics[1]:
        user_message += f"\n\n📉 Statistiques du Match:\n"
        for home_stat, away_stat in zip(match_statistics[0]['statistics'], match_statistics[1]['statistics']):
            if 'type' in home_stat and 'value' in home_stat and 'type' in away_stat and 'value' in away_stat:
                user_message += f"• {home_stat['type']}: {home_stat['value']} - {away_stat['value']}\n"

    system_prompt = (f"Tu es un journaliste sportif expert spécialisé dans l'analyse de matchs de football. "
                    f"IMPORTANT : Nous sommes en saison {current_season}. "
                    f"Tu dois te baser UNIQUEMENT sur les informations fournies : contexte pré-match, historique des matchs fourni, "
                    f"score final, événements et statistiques du match. "
                    f"N'utilise JAMAIS tes connaissances sur les saisons antérieures à {current_season}. "
                    f"\n\n"
                    f"**STRUCTURE OBLIGATOIRE DE TA RÉPONSE** (utilise des sauts de ligne entre chaque section) :\n"
                    f"1️⃣ **RÉSULTAT & CONTEXTE** (2-3 phrases) : Compare le résultat aux attentes pré-match et à la forme récente\n"
                    f"2️⃣ **ANALYSE TACTIQUE** (2-3 phrases) : Formation, possession, style de jeu et statistiques clés\n"
                    f"3️⃣ **MOMENTS DÉCISIFS** (2-3 phrases) : Joueurs clés, buts, cartons et tournants du match\n"
                    f"4️⃣ **BILAN** (1-2 phrases) : Conclusion sur la performance globale du {TEAM_NAME}\n"
                    f"\n"
                    f"Utilise des émojis pertinents (⚽🛡️🔥📊⭐) pour aérer. "
                    f"Sois concis, factuel et engageant. Chaque section doit être séparée par un saut de ligne.\n"
                    f"FORMATAGE : Utilise un formatage Markdown simple compatible avec Discord et Telegram (gras avec **texte**, italique avec *texte*, pas de titres avec # ni de formatage complexe).")
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 2000
    }

    return await call_chatgpt_api(data)

# FIN DU CODE DE CONFIGURATION IA

# Fonction principale pour initialiser le bot, enregistrer les gestionnaires de messages et lancer la vérification périodique des matchs.
async def main():
    try:
        log_message("fonction main executée")
        
        if USE_TELEGRAM:
            log_message("Bot telegram lancé")
            global bot
            bot = Bot(token=TOKEN_TELEGRAM)
            dp = Dispatcher()
            initialize_chat_ids_file()
            dp.message.register(on_start, Command("start"))
            
            # Démarrer le bot Telegram en tâche de fond
            asyncio.create_task(dp.start_polling(bot))

        if USE_DISCORD:
            log_message("Bot Discord lancé")
            # Lancez le bot Discord dans une nouvelle tâche
            asyncio.create_task(run_discord_bot(TOKEN_DISCORD))

        # Si au moins un des deux bots est activé, exécutez les tâches de vérification
        if USE_TELEGRAM or USE_DISCORD:
            # Check immediate puis vérification périodique
            asyncio.create_task(check_matches())
            asyncio.create_task(check_match_periodically())

    except Exception as e:
        log_message(f"Erreur inattendue dans main(): {e}")     
   
    # Boucle d'attente pour empêcher main() (donc le script) de se terminer
    while is_running:
        # Attente de 10 secondes avant de vérifier à nouveau
        await asyncio.sleep(10)  

if __name__ == "__main__":
    asyncio.run(main())