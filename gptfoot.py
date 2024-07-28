# -*- coding: utf-8 -*-
#
# AUTEUR :  Arnaud R. (https://github.com/Macmachi/gptfoot) 
# VERSION : v2.2.5
# LICENCE : Attribution-NonCommercial 4.0 International
#
import asyncio
import datetime
from aiogram import Bot, Dispatcher, types, exceptions
from aiogram.utils.exceptions import BadRequest, ChatNotFound
from aiohttp.client_exceptions import ClientConnectorError
from aiogram.utils.exceptions import NetworkError
import discord
from discord.ext import commands, tasks
import json
import os
import aiohttp
import pytz
import httpx
import configparser
import os
import time
import atexit
import signal
import sys

script_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir(script_dir)
config_path = os.path.join(script_dir, 'config.ini')

config = configparser.ConfigParser()
# Lire le contenu du fichier config.ini
config.read(config_path)

# Récupérer les variables de la section KEYS
API_KEY = config['KEYS']['OPENAI_API_KEY']
TOKEN_TELEGRAM = config['KEYS']['TELEGRAM_BOT_TOKEN']
TEAM_ID = config['KEYS']['TEAM_ID']
TEAM_NAME = config['KEYS']['TEAM_NAME']
LEAGUE_IDS_STR = config['KEYS']['LEAGUE_IDS']
SEASON_ID = config['KEYS']['SEASON_ID']
API_FOOTBALL_KEY = config['KEYS']['API_FOOTBALL_KEY']
TOKEN_DISCORD = config['KEYS']['DISCORD_BOT_TOKEN']
# Récupérer les variables de la section OPTIONS
USE_TELEGRAM = config['OPTIONS'].getboolean('USE_TELEGRAM', fallback=True) 
USE_DISCORD = config['OPTIONS'].getboolean('USE_DISCORD', fallback=True)
IS_PAID_API = config['OPTIONS'].getboolean('IS_PAID_API', fallback=False)
# Récupérer le fuseau horaire du serveur à partir de la section SERVER
SERVER_TIMEZONE_STR = config['SERVER'].get('TIMEZONE', 'Europe/Paris')
# Récupérer la langue à partir de la section LANGUAGES
LANGUAGE = config['LANGUAGES'].get('LANGUAGE', 'english')
# Définition de la variable globale pour le modèle pour l'analyse des ébénements
GPT_MODEL_NAME = "gpt-4o"
# Définition de la variable globale pour la traduction des événements
GPT_MODEL_NAME_TRANSLATION = "gpt-3.5-turbo"

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

# Permet de générer une exception si on dépasse le nombre de call api défini dans une de ces fonctions
class RateLimitExceededError(Exception):
    pass

# Fonction pour afficher un message de journalisation avec un horodatage.
def log_message(message: str):
    with open("gptfoot.log", "a") as log_file:
        log_file.write(f"{datetime.datetime.now()} - {message}\n")

# Fonction qui nous permet de vider le fichier log lorsqu'un nouveau match est détecté optimise la place sur le serveur et laisse quelques jours pour vérifier les logs du match précédent entre chaque match
def clear_log():
    with open("gptfoot.log", "w"):
        pass

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
    if sig == signal.SIGINT or sig == signal.SIGHUP:
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
    log_message(f'Bot Discord is now online as {bot_discord.user.name}')

@bot_discord.event
async def on_error(event, *args, **kwargs):
    log_message(f"Erreur dans l'événement {event} : {sys.exc_info()[1]}")    

@bot_discord.event
async def on_command_error(ctx, error):
    log_message(f"Erreur avec la commande {ctx.command}: {error}")    

@tasks.loop(count=1)
async def run_discord_bot(token):
    await bot_discord.start(token)

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
        # Vider le fichier de logs si un match est trouvé
        clear_log()
        log_message(f"un match a été trouvé")
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
                match_data = (await wait_for_match_start(fixture_id))[3]
                log_message(f"match_data reçu de wait_for_match_start dans check_matches {match_data}\n")
            
            else:
                # Attendre jusqu'au début du match pour envoyer la compo et voir le match a réellement commencé si on utilise l'api free pour limiter les calls à l'api
                # On vérifie pas ici si le match a déjà commencé car la structure du code fait en sorte qu'on puisse pas lancer le script pendant un match qui a commencé pour récuprer ses infos il faut attendre les matchs suivants. 
                remaining_seconds = seconds_until_match_start - seconds_until_message
                await asyncio.sleep(remaining_seconds)
                log_message(f"Fin de l'attente jusqu'à l'heure prévu de début de match") 
                # Attendez que le match débute réellement
                match_data = (await wait_for_match_start(fixture_id))[3]
                log_message(f"match_data reçu de wait_for_match_start dans check_matches {match_data}\n")
        
            # Envoyez le message de début de match et commencez à vérifier les événements
            if match_data is not None:
                log_message(f"Envoie du message de début de match avec send_start_message (uniquement utile pour l'api payante avec interval court)")
                await send_start_message()
                log_message(f"Check des événements du match avec check_events")
                #Permet de réinialiser les clés au début de chaque match !
                sent_events.clear()
                await check_events(fixture_id)  
            else:
                log_message(f"Pas de match_data pour l'instant (fonction check_matches), résultat de match_data : {match_data}")
        else:
                    log_message(f"Pas d'heure de début de match")
    else:
        log_message(f"Aucun match prévu aujourd'hui")

# Fonction pour récupérer les prédictions
async def get_match_predictions(fixture_id):
    log_message("get_match_predictions() appelée.")
    url = f"https://v3.football.api-sports.io/predictions?fixture={fixture_id}"
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                remaining_calls_per_day = int(resp.headers.get('x-ratelimit-requests-remaining', 0))
                log_message(f"Nombre d'appels à l'api restants : {remaining_calls_per_day}")

                if remaining_calls_per_day < 3:
                    log_message(f"#####\nLe nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.\n#####")
                    await notify_users_max_api_requests_reached()
                    raise RateLimitExceededError("Le nombre d'appels maximum à l'API est dépassé.")

                data = await resp.json()
                if not data.get('response'):
                    log_message(f"Pas de données récupérées depuis get_match_predictions")
                    return None

                return data['response'][0]['predictions']  # Ajustez cette partie en fonction de la structure de la réponse

    except Exception as e:
        log_message(f"Erreur dans get_match_predictions: {e}")
        return None

#Fonction qui permet de vérifier quand le match démarre réellement par rapport à l'heure prévu en vérifiant si le match a toujours lieu!
async def wait_for_match_start(fixture_id):
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
    log_message(f"Envoie du message de compo de match avec send_compo_message")
    await send_compo_message(match_data, predictions)

    while True:
        match_status, match_date, elapsed_time, match_data = await get_check_match_status(fixture_id)
        #log_message(f"match_status: {match_status}, match_date: {match_date}, elapsed_time: {elapsed_time} et match_data (pas log)\n")
        #log_message(f"match_status: {match_status}, match_date: {match_date}, elapsed_time: {elapsed_time}, match_data: {match_data}")  

        if match_status and elapsed_time is not None:
            #log_message(f"if match_status")  
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
    
# Récupère le statut et la date du match de la team dans la ligue spécifiée.
async def get_check_match_status(fixture_id):
    log_message("get_check_match_status() appelée.")
    url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                # Vérifiez le nombre d'appels restants par jour
                remaining_calls_per_day = int(resp.headers.get('x-ratelimit-requests-remaining', 0))
                log_message(f"Nombre d'appels à l'api restants' : {remaining_calls_per_day}")
                
                #Permet de sortir si on reste bloqué dans cette fonction pour x raisons
                #3 car on check 3 league à la sortie
                if remaining_calls_per_day < 3:
                    log_message(f"#####\nLe nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.\n#####")
                    await notify_users_max_api_requests_reached()
                    raise RateLimitExceededError("Le nombre d'appels maximum à l'API est dépassé.")
                    
                data = await resp.json()
                #log_message(f"Réponse de l'API pour get_check_match_status : {data}\n")
                if not data.get('response'):
                    log_message(f"Pas de données récupérées depuis get_check_match_status")
                    return None, None, None, None

        fixture = data['response'][0]
        #log_message(f"fixture depuis get_check_match_status {fixture}\n")
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

    except aiohttp.ClientError as e:
        log_message(f"Erreur lors de la requête à l'API (via get_check_match_status): {e}")
        return None, None, None, None
    except Exception as e:
        log_message(f"Erreur inattendue lors de la requête à l'API (via get_check_match_status): {e}")
        return None, None, None, None

# Fonction asynchrone pour vérifier s'il y a un match aujourd'hui et retourner les informations correspondantes.
async def is_match_today():
    log_message("is_match_today() appelée.")
    responses = []
    # déclaration de la variable comme globale
    global current_league_id
    # Variable pour stocker l'ID de la ligue en cours de traitement  
    current_league_id = None  

    try:
        async with aiohttp.ClientSession() as session:
            for LEAGUE_ID in LEAGUE_IDS:
                url = f"https://v3.football.api-sports.io/fixtures?team={TEAM_ID}&league={LEAGUE_ID}&next=1"
                headers = {
                    "x-apisports-key": API_FOOTBALL_KEY
                }
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    if data.get('response'):
                        responses.append(data)
                        current_league_id = LEAGUE_ID  # Mettez à jour l'ID de la ligue en cours de traitement
    except aiohttp.ClientError as e:
        log_message(f"Erreur lors de la requête à l'API (via is_match_today): {e}")
        return False, None, None, None, None, None, None, None, None
    except Exception as e:
        log_message(f"Erreur inattendue lors de la requête à l'API (via is_match_today): {e}")
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
        async with aiohttp.ClientSession() as session:
            async with session.get(events_url, headers=headers) as events_response:
                # Vérifiez le nombre d'appels restants par jour
                remaining_calls_per_day = int(events_response.headers.get('x-ratelimit-requests-remaining', 0))
                log_message(f"Nombre d'appels à l'api restants' : {remaining_calls_per_day}")
                
                # 3 car on check 3 league à la sortie
                if remaining_calls_per_day < 3:
                    await notify_users_max_api_requests_reached()
                    log_message(f"#####\nLe nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.\n#####")
                    raise RateLimitExceededError("Le nombre d'appels maximum à l'API est dépassé.")
                
                events_data = await events_response.json()
                # log_message(f"Réponse de l'API pour get_team_live_events : {events_data}")
                if not events_data.get('response'):
                    return None, None, None, None, None
                match_info = events_data['response'][0]
                # log_message(f"Réponse de l'API pour get_team_live_events : {match_info}\n")
                events = match_info['events']
                # Ajout du statut du match
                match_status = match_info['fixture']['status']['short']
                # Ajout du temps écoulé pour les logs (on ne renvoie pas la variable)
                elapsed_time = match_info['fixture']['status']['elapsed']
                # Ajout des données du match
                match_data = match_info
                log_message(f"Temps écoulé du match ' : {elapsed_time}\n")
                # Ajout des statistiques du match
                match_statistics = match_info['statistics']
                # Retourne les événements, le statut du match, les données du match et les statistiques du match
                return events, match_status, elapsed_time, match_data, match_statistics
    except aiohttp.ClientError as e:
        log_message(f"Erreur lors de la requête à l'API (via get_team_live_events): {e}")
        return None, None, None, None, None
    except Exception as e:
        log_message(f"Erreur inattendue lors de la requête à l'API (via get_team_live_events): {e}")
        return None, None, None, None, None

# Fonction asynchrone pour vérifier les événements en cours pendant un match, tels que les buts et les cartons rouges.
async def check_events(fixture_id): 
    log_message("check_events(fixture_id) appelée.")
    global sent_events
    global IS_PAID_API
    global penalty_message_sent  
    global interruption_message_sent  
    current_score = {'home': 0, 'away': 0}
    previous_score = {'home': 0, 'away': 0}
    score_updated = False
    is_first_event = True

    while True:
        try:
            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
            # S'assurer que match_data n'est pas None avant d'en extraire 'goals'.
            if match_data:
                new_score = {
                    'home': match_data['goals']['home'],
                    'away': match_data['goals']['away']
                }
            else:
                log_message(f"Pas de match_data disponible (none)\n")

            #log_message(f"Données récupérées de get_team_live_events dans check_events;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n score actuel : {new_score['home']} - {new_score['away']} \n match_data : (pas log)\n")
            # Calcul de l'intervalle optimisé selon api payante ou non 
            if IS_PAID_API:
                interval = 15

            elif not IS_PAID_API:
                # Pour API gratuite
                # Utilisez current_league_id pour définir un intervalle différent selon l'id de la ligue
                # 90 est le nombre d'appel max d'appel à l'api pour cette fonction en fonction du temps de match estimé, on laisse une marge car le nombre de call est de 100 maximum
                if current_league_id == 3:
                    total_duree_championnat = 5 + 45 + 10 + 45 + 10 + 30
                    interval = (total_duree_championnat * 60) / 90
                elif current_league_id == 207:
                    total_duree_championnat = 5 + 45 + 10 + 45 + 10
                    interval = (total_duree_championnat * 60) / 90
                elif current_league_id == 209:
                    total_duree_championnat = 5 + 45 + 10 + 45 + 10 + 30
                    interval = (total_duree_championnat * 60) / 90
                else:
                    total_duree_championnat = 5 + 45 + 10 + 45 + 10 + 30
                    interval = (total_duree_championnat * 60) / 90

                # Permet de ne pas mettre en pause pendant 5 minutes après une mi-temps pour manquer aucun événement!
                ht_counter = 0

                # Dans votre boucle principale de vérification
                if match_status == 'HT':
                    log_message(f"mi-temps détectée")
                    if IS_PAID_API:
                        log_message(f"Incrémentation du compteur de 15 secondes")
                        ht_counter += 15  # Augmente de 15 secondes à chaque détection de HT

                        # Si 5 minutes (300 secondes) se sont écoulées après la détection du statut HT permet de gérer les événements qui auraient été créés juste avant la mi-temps!
                        if ht_counter >= 300:
                            log_message(f"5 minutes après la détection de mi-temps on check le statut")
                            # Mis en commentaire car en cas de prolongation pause de 5 minutes suffisent !
                            # On met en pause 5 minutes car les mi-temps du temps additionnelles dure 5 minutes !  
                            # await asyncio.sleep(300)
                            

                        # Ajout d'une boucle pour vérifier le statut du match après la pause
                        while True:
                            log_message(f"On vérifie si le match a repris (statut actuel : {match_status})")
                            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
                            log_message(f"Données récupérées de get_team_live_events dans check_events;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")

                            if match_status != 'HT':
                                log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'execution du code (check_events)")
                                if events is not None:
                                    log_message("Réinitialisation des événements à None après la mi-temps pour éviter d'être renvoyé car on recommence la deuxième mi-temps à la 46ème car on vérifie : if events is None!\n")
                                    events = None
                                    # Réinitialiser le compteur pour les futures détections HT
                                    ht_counter = 0  
                                break

                            # Attendre un certain temps avant de vérifier à nouveau le statut du match
                            await asyncio.sleep(15)

                    # Pause de 13 minutes (780 secondes) si le statut du match est 'HT' (mi-temps) afin de gagner des calls API attention le fait aussi si prolongation donc il y aura un léger décalage comme une HT de prolongation est de 5 minutes !  
                    if not IS_PAID_API:
                        log_message(f"mi-temps détectée - mise en pause de l'execution du code pour 780 secondes")
                        #14min*60=840 secondes
                        await asyncio.sleep(780)

                        # Ajout d'une boucle pour vérifier le statut du match après la pause
                        while True:
                            log_message(f"On vérifie si le match a repris (statut actuel : {match_status})")
                            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
                            log_message(f"Données récupérées de get_team_live_events dans check_events;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")

                            if match_status != 'HT':
                                log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'execution du code (check_events)")
                                if events is not None:
                                    log_message("Réinitialisation des événements à None après la mi-temps pour éviter d'être renvoyé car on recommence la deuxième mi-temps à la 46ème car on vérifie : if events is None!\n")
                                    events = None
                                break

                            # Attendre un certain temps avant de vérifier à nouveau le statut du match
                            await asyncio.sleep(120)

            if match_status == 'P':
                if not penalty_message_sent:
                    # On met de côté les penalties car pas pertinent dans la façon dont le code les gère actuellement et pas forcément pertinent tout court car beaucoup de messages envoyés.
                    log_message("Séance de tir au but : attente de 20 minutes la fin des pénos pour envoyer les informations du match restants + fin de match pour limiter le nombre d'appels à l'api !")
                    await pause_for_penalty_shootout()
                    penalty_message_sent = True

                if IS_PAID_API:
                    # Attente spécifique pour l'API payante
                    wait_time = 30  # Temps d'attente entre chaque vérification en secondes pour l'API payante
                else:
                    # Pause de 20 minutes pour l'API non payante
                    await asyncio.sleep(1200)  # Temps d'attente initial pour l'API non payante
                    wait_time = 300  # Temps d'attente entre chaque vérification en secondes pour l'API non payante

                # Ajout d'une boucle pour vérifier le statut du match après les pénos
                while True:
                    log_message(f"On vérifie si les pénos (PEN) sont terminés (statut actuel : {match_status})")
                    events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
                    log_message("Données récupérées de get_team_live_events dans check_events; Statistiques de match : (pas log), Status de match : {}, Events {}, match_data : (pas log)".format(match_status, events))

                    if match_status != 'PEN':
                        log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'exécution du code (check_events)")
                        penalty_message_sent = False  # Réinitialiser pour les prochains tirs au but si nécessaire
                        break

                    # Attendre un certain temps avant de vérifier à nouveau le statut du match
                    await asyncio.sleep(wait_time)           

            if match_status == 'INT':
                log_message(f"Match interrompu (INT)")
                # Envoie d'un message aux utilisateurs pour dire aux utilisateurs qu'une interruption du match a lieu
                if not interruption_message_sent:
                    await notify_match_interruption()
                    interruption_message_sent = True

                if IS_PAID_API:
                    # Attente spécifique pour l'API payante
                    wait_time = 120  # Temps d'attente entre chaque vérification en secondes pour l'API payante
                else:
                    # Pause de 20 minutes pour l'API non payante
                    await asyncio.sleep(600)  # Temps d'attente initial pour l'API non payante
                    wait_time = 600  # Temps d'attente entre chaque vérification en secondes pour l'API non payante
                    
                    # Ajout d'une boucle pour vérifier le statut du match après les pénos
                    while True:
                        log_message(f"On vérifie les pénos (PEN) sont terminés (statut actuel : {match_status})")
                        events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
                        log_message(f"Données récupérées de get_team_live_events dans check_events;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")

                        if match_status != 'INT':
                            log_message(f"Le match a repris (statut actuel : {match_status}), continuation de l'execution du code (check_events)")
                            '''
                            if events is not None:
                                log_message("Réinitialisation des événements à None après la mi-temps pour éviter d'être renvoyé.\n")
                                events = None
                            '''    
                            # Réinitialiser pour les prochaines interruptions si nécessaire
                            interruption_message_sent = False
                            break  
                        
                        # Attendre un certain temps avant de vérifier à nouveau le statut du match
                        await asyncio.sleep(wait_time)       

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
                event_key_sub = f"{event['type']}_{player_id}"

                if event_key in sent_events or event_key_sub in sent_events:
                    continue

                if event['type'] == "Goal":
                    log_message(f"type == Goal")   
                    log_message(f"Données de score récupéré dans match_data pour la variable new_score : {new_score}")
                    log_message(f"Previous score : {previous_score}")

                    log_message(f"Contenu de l'event de type goal :\n {event}\n\n")
                
                    # On vérifie qu'il n'y pas eu de pénalté manqué 
                    if event['detail'] != 'Missed Penalty':
                        log_message(f"Not Missed Penalty")
                        player = event['player']
                        team = event['team']   
                        # Récupérez les statistiques du joueur
                        player_id = player['id']
                        #log_message(f"match_data['players']: {match_data['players']}")
                        player_statistics = None
                        for team_data in match_data['players']:
                            for player_stats in team_data['players']:
                                #log_message(f"for player_stats : {player_stats}\n")
                                if 'player' in player_stats and player_stats['player']['id'] == player_id:
                                    player_statistics = player_stats['statistics']
                                    #log_message(f"player_statistics : {player_statistics}\n")
                                    break
                            if player_statistics:
                                break
                        #log_message(f"player value : {player}")
                        # Véfirier également que l'ID et le nom du joueur ne sont pas None. 
                        if player is not None and player['id'] is not None and player['name'] is not None:
                            log_message(f"player value is not none")
                            # Vérifiez si l'événement de but est dans les 10 dernières minutes (10 minutes car il faut tenir compte des pauses surestimées lors des prolongations et on considère 10 minutes comme acceptable pour avoir des corrections d'événements)
                            # Attention des événements de la fin de la première mi-temps non envoyés mais pris en compte par le script comme une correction pourrait être envoyé au début de la deuxième mi-temps si un événement se passe rapidement à la reprise surtout avec l'api payante.
                            current_elapsed_time = elapsed_time
                            goal_elapsed_time = event['time']['elapsed']
                            # Avec l'api payante comme on rafraichit plus souvent aussi on peut légèrement réduire l'intervall de vérification maximum afin de réduire les risque que les corrections de goal soient envoyées
                            if IS_PAID_API:
                                allowed_difference = -10
                            else:
                                allowed_difference = -10
                            log_message(f"if {goal_elapsed_time} >= {current_elapsed_time} + {allowed_difference}")

                            if goal_elapsed_time is not None and current_elapsed_time is not None:
                                log_message(f"goal_elapsed_time et current_elapsed_time ne sont pas égals à none!") 
                                
                                # Permet d'éviter qu'on rentre dans une modification d'un goal marqué trop tard ce qui pourrait apporter de la confusion comme il serait considéré comme un nouveau but et envoyé longtemps après
                                if goal_elapsed_time >= current_elapsed_time + allowed_difference:
    
                                    log_message(f"L'événement de goal a été détecté dans un interval de 10 minutes par rapport au temps actuel du match")    
                                    # On pourrait envoyer l'événement goal avant cette condition pour avoir un bot plus réactif MAIS les données envoyées soient corrigées ou incomplètes (joueur qui a marqué, ses statistiques, détail du goal ou annulation du goal)
                                    # Cette nouvelle condition avec l'ajout de is_first_event permet de détecter et d'envoyer le message pour le premier but du match,
                                    #  même si new_score est encore égal à current_score (ce qui peut arriver si le premier but est détecté avant que new_score ne soit mis à jour).  
                                    if is_first_event or new_score != current_score:
                                        log_message(f"Premier événement ou nouveau score détecté")
                                        # Ajout de la logique pour vérifier une augmentation significative du score entre deux vérifications (ex : on passe de 0-2 à 0-4) afin d'éviter d'envoyer le score à ce moment mais à la sortie de la boucle dans un nouveau message ! 
                                        significant_increase_in_score = False
                                        # Si l'équipe à domicile a marqué plus d'un but
                                        if team['id'] == match_data['teams']['home']['id'] and new_score['home'] - current_score['home'] > 1:
                                            significant_increase_in_score = True
                                        # Si l'équipe à l'extérieur a marqué plus d'un but    
                                        elif team['id'] == match_data['teams']['away']['id'] and new_score['away'] - current_score['away'] > 1:
                                            significant_increase_in_score = True
                                        # Si chaque équipe a marqué au moins un but par rapport au score précédent
                                        elif (new_score['home'] - current_score['home'] >= 1) and (new_score['away'] - current_score['away'] >= 1):
                                            significant_increase_in_score = True    
                                
                                        # Si augmentation significative, envoyez un message spécial
                                        if significant_increase_in_score:
                                            await send_goal_message_significant_increase_in_score(player, team, player_statistics if player_statistics else [], event['time']['elapsed'], match_data, event)
                                            log_message(f"event_key enregistrée : {event_key}")
                                            sent_events.add(event_key)
                                            # On mettra a jour le score à la sortie de la boucle for event in events: car il peut avoir plusieurs événements à véfirier (et pas forcément des buts) dans un itération avant de mettre à jour le score comme une correction d'un but qui empêcherait de repasser dans if new_score != current_score: si le score était mis à jour là !
                                            score_updated = True  

                                        # Sinon message normal
                                        if not significant_increase_in_score:
                                            await send_goal_message(player, team, player_statistics if player_statistics else [], event['time']['elapsed'], match_data, event)
                                            log_message(f"event_key enregistrée : {event_key}")
                                            sent_events.add(event_key)
                                            # On mettra a jour le score à la sortie de la boucle for event in events: car il peut avoir plusieurs événements à véfirier (et pas forcément des buts) dans un itération avant de mettre à jour le score comme une correction d'un but qui empêcherait de repasser dans if new_score != current_score: si le score était mis à jour là !
                                            score_updated = True
                                            is_first_event = False  
                                    else:
                                        log_message(f"new_score == current_score")
                                        # Car le score n'est plus mis à jour de la même façon pendant les tirs au penaltys donc on rentre normalement dans cette condition si on utilise l'api payante uniquement !
                                        if IS_PAID_API and match_status == 'P':
                                            await send_shootout_goal_message(player, team, player_statistics if player_statistics else [], event)
                                            log_message(f"event_key enregistrée : {event_key}")
                                            sent_events.add(event_key)
                                            # On ne met pas le score à jour car cela est géré de façon différente lors des tirs aux buts
                                            score_updated = False  
                                        else:
                                            log_message(f"Le score n'a pas été modifié car l'API ne l'a pas mis à jour soit car retard, soit car modification du temps de l'événement d'un goal")
                                            log_message(f"[EN ATTENTE] informations non envoyées :\n Goal : {player}, {team}, {player_statistics if player_statistics else []}, {event['time']['elapsed']},{match_data['teams']['home']['name']} {match_data['goals']['home']} - {match_data['goals']['away']} {match_data['teams']['away']['name']}")
                                # Evite de bloquer les prochains goals si un goal est trop tardivement validé pour être envoyé!
                                if goal_elapsed_time < current_elapsed_time + allowed_difference:
                                    log_message(f"[ATTENTION] L'event goal a été enregistré mais n'a pas été a été détecté dans un interval de 10 minutes par rapport au temps actuel du match (car trop de temps a passé!)")
                                    sent_events.add(event_key)
                        
                    # Traiter un penalty manqué
                    if event['type'] == 'Goal' and event['detail'] == 'Missed Penalty':
                        last_missed_penalty_time = event['time']['elapsed']
                        log_message(f"Penalty manqué détecté à {last_missed_penalty_time} minutes.")
                        log_message(f"event_key enregistrée (penalty missed) : {event_key}")
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
                        if IS_PAID_API:
                            allowed_difference = -10
                        else:
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
            if score_updated:
                log_message(f"score_updated is true")
                # Permet d'envoyer le score actualisé si plusieurs goal ont été marqué entre deux vérifications et qui eux seront envoyé sans le score !
                if significant_increase_in_score:
                    await updated_score(match_data)
                    previous_score = current_score.copy()
                    log_message(f"previous_score mis à jour avec current_score.copy() pas encore mis à jour avec new_score : {previous_score}")
                    current_score = new_score.copy()
                    log_message(f"current_score mise à jour avec new_score.copy() : {current_score}")
                    score_updated = False 

                if not significant_increase_in_score:
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
            if match_status == 'FT' or match_status == 'AET' or match_status == 'PEN':
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
        with open("telegram_chat_ids.json", "r") as file:
            chat_ids = json.load(file)
            log_message(f"Chat IDs chargés depuis le fichier telegram_chat_ids.json : {chat_ids}")
        
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=message)
            except exceptions.BotBlocked:
                # Évite de log si le bot a été bloqué par des utilisateurs
                continue
            except BadRequest as e:
                log_message(f"Erreur lors de l'envoi du message à Telegram (BadRequest) : {e}")
            except ClientConnectorError as e:
                log_message(f"Erreur lors de l'envoi du message à Telegram (ClientConnectorError) : {e}")
            except NetworkError as e:
                log_message(f"Erreur lors de l'envoi du message à Telegram (NetworkError) : {e}")
            except exceptions.TelegramAPIError as e:
                log_message(f"Erreur lors de l'envoi du message à Telegram TelegramAPIError : {e}")    
            except Exception as e:
                log_message(f"Erreur inattendue lors de l'envoi du message à Telegram : {e}")

    # Pour Discord:
    if USE_DISCORD:
        log_message("Lecture des IDs de channel pour Discord...")

        # Utilisez le chemin correct pour le fichier discord_channels.json
        if os.path.exists(discord_channels_path):
            with open(discord_channels_path, "r") as file:
                channels = json.load(file)
            
            for channel_id in channels:
                channel = bot_discord.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(message)
                    except discord.Forbidden as e:
                        # Évite de log si le bot a été bloqué par des utilisateurs, concerne aussi d'autres problèmes de permission...
                        continue 
                    except discord.NotFound as e:
                        log_message(f"Erreur: Canal Discord {channel_id} non trouvé : {e}")
                    except discord.HTTPException as e:
                        log_message(f"Erreur HTTP lors de l'envoi du message au canal Discord {channel_id}: {e}")
                    except discord.InvalidArgument as e:
                        log_message(f"Erreur: Argument invalide pour le canal Discord {channel_id}: {e}")
                    except Exception as e:
                        log_message(f"Erreur inattendue lors de l'envoi du message à Discord : {e}")
        else:
            log_message("Erreur: Le fichier discord_channels.json n'a pas été trouvé.")

# Envoie un message lorsqu'un match est détecté le jour même 
async def send_match_today_message(match_start_time, fixture_id, current_league_id, teams, league, round_info, venue, city):
    log_message("send_match_today_message() appelée.")
    # Appeler l'API ChatGPT  
    chatgpt_analysis = await call_chatgpt_api_matchtoday(match_start_time, teams, league, round_info, venue, city)
    message = f"🤖 : {chatgpt_analysis}"
    # Envoyer le message du match à tous les chats.
    await send_message_to_all_chats(message)

# Envoie un message de début de match aux utilisateurs avec des informations sur le match, les compositions des équipes.
async def send_compo_message(match_data, predictions=None):
    log_message("send_compo_message() appelée.")
    log_message(f"Informations reçues par l'API : match_data={match_data}, predictions={predictions}")

    if match_data is None:
        log_message("Erreur : match_data est None dans send_compo_message")
        message = "🤖 : Désolé, je n'ai pas pu obtenir les informations sur la composition des équipes pour le moment."
    else:
        # Appeler l'API ChatGPT  
        chatgpt_analysis = await call_chatgpt_api_compomatch(match_data, predictions)
        message = "🤖 : " + chatgpt_analysis

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
    message = f"🤖 : ❌ But annulé !\n"
    message += f"Score précédent: {previous_score['home']} - {previous_score['away']}\n"
    message += f"Score actuel: {current_score['home']} - {current_score['away']}\n"
    await send_message_to_all_chats(message)

# Envoie un message aux utilisateurs pour informer d'un carton rouge lors du match en cours, y compris les informations sur le joueur et l'équipe.
async def send_red_card_message(player, team, elapsed_time, event):
    log_message("send_red_card_message() appelée.")
    message = f"🟥 Carton rouge ! {elapsed_time}'\n ({team['name']})\n\n"
    # Appeler l'API ChatGPT  
    chatgpt_analysis = await call_chatgpt_api_redmatch(player, team, elapsed_time, event)
    message += "🤖 Infos sur le carton rouge :\n" + chatgpt_analysis    
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

# Envoie un message de fin de match aux utilisateurs avec le score final.
async def send_end_message(home_team, away_team, home_score, away_score, match_statistics, events):
    log_message("send_end_message() appelée.")
    message = f"🏁 Fin du match !\n{home_team} {home_score} - {away_score} {away_team}\n\n"
    # Appeler l'API ChatGPT et ajouter la réponse à la suite des statistiques du match
    chatgpt_analysis = await call_chatgpt_api_endmatch(match_statistics, events, home_team, home_score, away_score, away_team)
    message += "🤖 Mon analyse :\n" + chatgpt_analysis
    await send_message_to_all_chats(message)

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
            translation_response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=translation_data, timeout=200.0)
            translation_response.raise_for_status()
            translated_message = translation_response.json()["choices"][0]["message"]["content"].strip()
            return translated_message
        except httpx.HTTPError as e:
            log_message(f"Error during message translation with the OpenAI API: {e}")
            return f"🤖 : Sorry, an error occurred while communicating with the translation API."
        except Exception as e:
            log_message(f"Unexpected error during message translation: {e}")
            return f"🤖 : Sorry, an unexpected error occurred during message translation."

# Fonction générique pour appeler l'API ChatGPT
async def call_chatgpt_api(data):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Appel initial à gpt-4-turbo pour obtenir le message
            response_json = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=200.0)
            response_json.raise_for_status()
            message = response_json.json()["choices"][0]["message"]["content"].strip()
             
            log_message(f"\n Succès de la récupération de la réponse gpt-4-turbo \n")
            return message

        except httpx.HTTPError as e:
            log_message(f"Erreur lors de l'appel à l'API ChatGPT : {e}")
            return f"🤖 : Désolé une erreur lors de la communication avec l'API ChatGPT est survenue."
        except Exception as e:
            log_message(f"Erreur inattendue lors de l'appel à l'API ChatGPT : {e}")
            return f"🤖 : Désolé, une erreur inattendue s'est produite."

# Analyse pour l'heure de début du match
async def call_chatgpt_api_matchtoday(match_start_time, teams, league, round_info, venue, city):
    log_message(f"Informations reçues par l'API : match_start_time={match_start_time}, teams={teams}, league={league}, round_info={round_info}, venue={venue}, city={city}")
    user_message = (f"Les informations du match qui a lieu aujourd'hui sont les suivantes : \n"
                    f"Ligue actuelle : {league}\n"
                    f"Tour : {round_info}\n"
                    f"Équipes du match : {teams['home']} contre {teams['away']}\n"
                    f"Stade et ville du stade : {venue}, {city}\n"
                    f"Heure de début : {match_start_time}\n"
                    f"L'heure actuelle est : {datetime.datetime.now()}")
    system_prompt = f"Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, fait une brève et pertinente présentation en français du match qui aura lieu aujourd'hui avec les informations que je te donne, embellie cette présentation avec quelques émojis"
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 1000
    }
    return await call_chatgpt_api(data)

# Analyse de début de match avec des smileys
async def call_chatgpt_api_compomatch(match_data, predictions=None):
    log_message(f"Informations reçues par l'API : match_data={match_data}, predictions={predictions}")
    
    user_message = ""
    
    if match_data is not None:
        user_message = f"Voici les informations du match qui va commencer d'ici quelques minutes : {match_data}"
    else:
        user_message = "Aucune information sur le match n'est disponible pour le moment."

    if predictions:
        user_message += f"\nPrédictions de l'issue du match : {predictions['winner']['name']} (Comment: {predictions['winner']['comment']})"

    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football. Si et uniquement si je te fournis ces informations : fournis-moi une analyse concise des compositions avec des émojis pour rendre la présentation attrayante et en commentant les formations de début de match et les prédictions."
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 2000
    }
    
    return await call_chatgpt_api(data)

# Commentaire sur le goal récent
async def call_chatgpt_api_goalmatch(player, team, player_statistics, elapsed_time, event, score_string):
    log_message(f"Informations reçues par l'API : player={player}, team={team}, player_statistics={player_statistics}, elapsed_time={elapsed_time}, event={event}, score_string={score_string}")
    user_message = f"Le joueur qui a marqué : {player} "
    user_message += f"L'équipe pour laquelle le but a été comptabilisé : {player}"
    if player_statistics:  
        user_message += f"Les statistiques du joueur pour ce match qui a marqué, n'utilise pas le temps de jeu du joueur : {player_statistics} "
    user_message += f"La minute du match quand le goal a été marqué : {elapsed_time} "
    user_message += f"Le score actuel après le but qui vient d'être marqué pour contextualisé ta réponse , mais ne met pas le score dans ta réponse : {score_string} "
    user_message += f"Voici les détails de l'événement goal du match en cours {event}, utilise les informations pertinentes liées au goal marqué à la {elapsed_time} minute sans parler d'assist!"

    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, commente moi le goal le plus récent du match qui est en cours, tu ne dois pas faire plus de trois phrases courtes en te basant sur les informations que je te donne comme qui est le buteur et ses statistiques (si disponible)"
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 2000
    }
    return await call_chatgpt_api(data)

# Commentaire sur le goal lors de la séance de tir aux penaltys
async def call_chatgpt_api_shootout_goal_match(player, team, player_statistics, event):
    log_message(f"Informations reçues par l'API : player={player}, team={team}, player_statistics={player_statistics}, event={event}")
    user_message = f"Le joueur qui a marqué le pénalty lors de la séance aux tirs aux buts : {player} "
    user_message += f"L'équipe pour laquelle le but a été comptabilisé : {player}"
    if player_statistics:  
        user_message += f"Les statistiques du joueur pour ce match qui a marqué (n'utilise pas le temps de jeu du joueur): {player_statistics} "
    user_message += f"Voici les détails de l'événement goal du match en cours {event}."

    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, commente moi le goal lors de cette séance aux tirs au but, tu ne dois pas faire plus de deux phrases courtes en te basant sur les informations que je te donne."
    
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
                    f"L'équipe dont il fait parti': {team} "
                    f"La minute du match à laquelle il a pris un carton rouge : {elapsed_time} "
                    f"Voici les détails de l'événement du carton rouge du match en cours {event}, utilise uniquement les informations pertinentes liées à ce carton rouge de la {elapsed_time} minute.")
    system_prompt = "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football, commente moi ce carton rouge le plus récent du match qui est en cours, tu ne dois pas faire plus de deux phrases courtes en te basant sur les informations que je te donne."
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 1000
    }
    return await call_chatgpt_api(data)

# Analyse de fin de match
async def call_chatgpt_api_endmatch(match_statistics, events, home_team, home_score, away_score, away_team):
    log_message(f"Informations reçues par l'API : match_statistics={match_statistics}, events={events}")
    
    # Score final
    user_message = f"📊 Score Final:\n{home_team} {home_score} - {away_score} {away_team}\n\n"
    
    # Formater les événements du match
    formatted_events = ["📢 Événements du Match:"]
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

    system_prompt = f"Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football. En utilisant le score final, les événements et statistiques de match fournis, donne une analyse détaillée de 270 mots maximum de la prestation du {TEAM_NAME} pendant le match."
    
    data = {
        "model": GPT_MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        "max_tokens": 1300
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
            dp = Dispatcher(bot)
            initialize_chat_ids_file()
            dp.register_message_handler(on_start, commands=["start"])
            asyncio.create_task(dp.start_polling())

        if USE_DISCORD:
            log_message("Bot Discord lancé")
            # Lancez le bot Discord dans une nouvelle tâche
            asyncio.create_task(run_discord_bot(TOKEN_DISCORD))

        # Si au moins un des deux bots est activé, exécutez les tâches de vérification
        if USE_TELEGRAM or USE_DISCORD:
            # Si on appel check_matches depuis cette fonction main et qu'un match est détecté alors à la fin du match check_match_periodically() n'est pas executé mais le sera le lendemain
            asyncio.create_task(check_matches())
            asyncio.create_task(check_match_periodically())

    except Exception as e:
        log_message(f"Erreur inattendue: {e}")     
   
    # Boucle d'attente pour empêcher main() (donc le script) de se terminer
    while is_running:
        # Attente de 10 secondes avant de vérifier à nouveau
        await asyncio.sleep(10)  

if __name__ == "__main__":
    asyncio.run(main())      