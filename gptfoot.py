# -*- coding: utf-8 -*-
"""
### INFORMATIONS SUR LE SCRIPT GPTFOOT ###
# AUTEUR :  Arnaud (https://github.com/Macmachi) 
# VERSION : v1.2
# FONCTIONALITES : Bot telegram pour suivre les événements de matchs d'un club dans une compétition (sans trop de messages) : Début du match avec composition, buts, cartons rouges et analyse du match par GPT4 à la fin. 
# My XMR wallet if you like my telegram bot : 47aRxaose3a6Uoi8aEo6sDPz3wiqfTePt725zDbgocNuBFSBSXmZNSKUda6YVipRMC9r6N8mD99QjFNDvz9wYGmqHUoMHbR
### FONCTIONALITES NICE TO HAVE ###
# Envoyer le classement 30 minutes après le match pour le championnat 
# Récupérer saison ID 
### EXPLOIT CONNUS ###
* Vérifie à heure fixe donc si le bot est lancé un jour de match, celui-ci ne sera pas détecté!
* (1 match sur 100) un goal soit annulé et qu'un autre soit marqué dans la même minute = confusion de la logique entre l'annulation du premier but avec le second but marqué
* (1 match sur 100) Si la correction de temps écoulé pour le premier but est reçue après un autre but est marqué (intervalle de 5min), la logique actuelle considérera le premier but corrigé comme un nouveau but.
"""
import asyncio
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils.exceptions import BadRequest, ChatNotFound
from aiohttp.client_exceptions import ClientConnectorError
from aiogram.utils.exceptions import NetworkError
import json
import os
import aiohttp
import pytz
import httpx
import configparser

config = configparser.ConfigParser()
# read the content of the config.ini file
config.read('config.ini')  

# Please replace this information in the code (NOT HERE) with your leagues id competition from api-football.com.
'''
    LEAGUE_IDS = [2, 207, 209] 
'''
# Please replace this information in the code (NOT HERE) with your language and team name for the AI analysis.
''' 
    conversation_history = [
    {
        "role": "system",
        "content": (
            "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football. "
            "En utilisant les événements et statistiques de match fournis, donne une analyse détaillée de la prestation du Servette FC pendant le match."
        ),
    }
]
'''

# KEYs from the INI file
API_KEY = config['KEYS']['OPENAI_API_KEY']
TOKEN_TELEGRAM = config['KEYS']['TELEGRAM_BOT_TOKEN']
TEAM_ID = config['KEYS']['TEAM_ID']
SEASON_ID = config['KEYS']['SEASON_ID']
API_FOOTBALL_KEY = config['KEYS']['API_FOOTBALL_KEY']

# You may need to do this depending on your server's time zone
paris_tz = pytz.timezone('Europe/Paris')
sent_events = set()

# Permet de générer une exception si on dépasse le nombre de call api défini dans une de ces fonctions
class RateLimitExceededError(Exception):
    pass

# Fonction pour afficher un message de journalisation avec un horodatage.
def log_message(message: str):
    with open("sfcbotlog.log", "a") as log_file:
        log_file.write(f"{datetime.datetime.now()} - {message}\n")

# Fonction pour initialiser le fichier des IDs de chat autorisés s'il n'existe pas déjà.
def initialize_chat_ids_file():
    """
    Crée un fichier JSON vide pour stocker les ID de chat si le fichier n'existe pas déjà.
    """
    if not os.path.exists("chat_ids_sfcbot.json"):
        try:
            with open("chat_ids_sfcbot.json", "w") as file:
                json.dump([], file)
        except IOError as e:
            log_message(f"Erreur lors de la création du fichier chat_ids_sfcbot.json : {e}")

# Fonction déclenchée lorsqu'un utilisateur envoie la commande /start au bot.
async def on_start(message: types.Message):
    log_message("on_start(message: types.Message) appelée.")  
    chat_id = message.chat.id
    log_message(f"Fonction on_start() appelée pour le chat {chat_id}")

    # Récupérez les ID de chat existants à partir du fichier JSON
    with open("chat_ids_sfcbot.json", "r") as file:
        chat_ids = json.load(file)

    # Ajoutez l'ID de chat au fichier JSON s'il n'est pas déjà présent
    if chat_id not in chat_ids:
        chat_ids.append(chat_id)

        with open("chat_ids_sfcbot.json", "w") as file:
            json.dump(chat_ids, file)

        await message.reply("Le bot a été démarré et l'ID du chat a été enregistré.")
        log_message(f"Le bot a été démarré et l'ID du chat {chat_id} a été enregistré.")
    else:
        await message.reply("Le bot a déjà été démarré dans ce chat.")
        log_message(f"Le bot a déjà été démarré dans ce chat {chat_id}.")      
        
# Vérifie périodiquement si un match est prévu et, si c'est le cas, récupère les informations pertinentes et effectue des actions appropriées.
async def check_match_periodically():

    while True:
        now = datetime.datetime.now()
        target_time = datetime.datetime(now.year, now.month, now.day, 2, 1, 0)

        if now > target_time:
            target_time += datetime.timedelta(days=1)

        seconds_until_target_time = (target_time - now).total_seconds()
        log_message(f"Attente de {seconds_until_target_time} secondes jusqu'à la prochaine vérification (02h01).")
        await asyncio.sleep(seconds_until_target_time)
        
        # Vérifiez les matchs 
        log_message("Vérification du match en cours...")
        await check_matches()
    
# Vérifie si un match est prévu aujourd'hui et effectue les actions appropriées, comme envoyer des messages de début et de fin de match, et vérifier les événements pendant le match.
async def check_matches():
    global sent_events
    log_message("get_team_match_info() appelée.")
    #On ignore la dernière value (current_league_id) qui n'est pas importante ici et déjà déclaré comme une variable globale !
    match_today, match_start_time, fixture_id, _ = await is_match_today()
    log_message(f"Résultat de is_match_today() dans la fonction check_match_periodically : match_today = {match_today}, match_start_time = {match_start_time}, fixture_id = {fixture_id}")

    if match_today:
        log_message(f"un match a été trouvé")
        now = datetime.datetime.now()
        match_start_datetime = now.replace(hour=match_start_time.hour, minute=match_start_time.minute, second=0, microsecond=0)
        seconds_until_match_start = (match_start_datetime - now).total_seconds()
        log_message(f"Il reste {seconds_until_match_start} secondes avant le début du match.")
        await asyncio.sleep(seconds_until_match_start)
        log_message(f"Fin de l'attente jusqu'à l'heure prévu de début de match") 
        # Attendez que le match débute réellement
        match_data = (await wait_for_match_start(fixture_id))[3]
        log_message(f"match_data reçu de wait_for_match_start dans check_matches {match_data}\n")

        # Récupérez les ID de chat enregistrés
        log_message("Lecture des IDs de chat enregistrés...")
        with open("chat_ids_sfcbot.json", "r") as file:
            chat_ids = json.load(file)
            log_message(f"Chat IDs chargés depuis le fichier chat_ids_sfcbot.json : {chat_ids}")

        # Envoyez le message de début de match et commencez à vérifier les événements
        if match_data is not None:
            for chat_id in chat_ids:
                log_message(f"Envoie du message de début de match avec send_start_message")
                await send_start_message(chat_id, match_data)
                log_message(f"Check des événements du match avec check_events")
                #Permet de réinialiser les clés au début de chaque match !
                sent_events.clear()
                await check_events(chat_id, fixture_id)  
        else:
            log_message(f"Pas de match_data pour l'instant (fonction check_matches), résultat de match_data : {match_data}")
    else:
        log_message(f"Aucun match prévu aujourd'hui")

#Fonction qui permet de vérifier quand le match démarre réellement par rapport à l'heure prévu en vérifiant si le match a toujours lieu!
async def wait_for_match_start(fixture_id):
    log_message(f"fonction wait_for_match_start appelée")    
    while True:
        match_status, match_date, elapsed_time, match_data = await get_check_match_status(fixture_id)
        log_message(f"match_status: {match_status}, match_date: {match_date}, elapsed_time: {elapsed_time} et match_data (pas log)\n")
        #log_message(f"match_status: {match_status}, match_date: {match_date}, elapsed_time: {elapsed_time}, match_data: {match_data}")  

        if match_status and elapsed_time is not None:
            #log_message(f"if match_status")  
            # Sortir de la boucle si le match commence, est reporté ou annulé
            if elapsed_time > 0 or match_status in ('PST', 'CANC'):
                log_message(f"le match a commencé sorti de la boucle wait_for_match_start")      
                break
        log_message("Le match n'a pas encore commencé, en attente...")
        await asyncio.sleep(60)  # Attendre 60 secondes avant de vérifier à nouveau

    # Retourner None si le match est reporté ou annulé
    if match_status in ('PST', 'CANC'):
        log_message(f"son statut indique qu'il a été annulé ou reporté")  
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
                
                if remaining_calls_per_day < 2:
                    raise RateLimitExceededError("Le nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.")
                    
                data = await resp.json()
                #log_message(f"Réponse de l'API pour get_check_match_status : {data}\n")
                if not data.get('response'):
                    log_message(f"Pas de données récupérées depuis get_check_match_status")
                    return None, None, None, None

        fixture = data['response'][0]
        #log_message(f"fixture depuis get_check_match_status {fixture}\n")
        match_status = fixture['fixture']['status']['short']
        match_date = datetime.datetime.strptime(fixture['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z').astimezone(paris_tz)
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
        
        if fixture['lineups']:
            home_lineup = fixture['lineups'][0]
            away_lineup = fixture['lineups'][1]
            match_data["lineups"] = {
                home_lineup['team']['name']: {
                    "formation": home_lineup['formation'],
                    "startXI": home_lineup['startXI']
                },
                away_lineup['team']['name']: {
                    "formation": away_lineup['formation'],
                    "startXI": away_lineup['startXI']
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

        log_message(f"Statut et données de match récupérés depuis get_check_match_status : {match_status}, \n Date du match : {match_date}, \n Temps écoulé : {elapsed_time}, \n match data : {match_data} \n")
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
    
    # Mettez vos identifiants de ligue ici (Champions league (A MODIFIER en fonction des résultats pour éviter trop de call inutile pour europa, conference league!!!), championnat et coupe) et adapter les intervalles car prolongation pour certains championnats !
    LEAGUE_IDS = [2, 207, 209]  
    responses = []
    
    global current_league_id  # déclaration de la variable comme globale
    current_league_id = None  # Variable pour stocker l'ID de la ligue en cours de traitement

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
        return False, None, None, None
    except Exception as e:
        log_message(f"Erreur inattendue lors de la requête à l'API (via is_match_today): {e}")
        return False, None, None, None

    match_today = False
    match_start_time = None
    fixture_id = None

    for response in responses:
        if response['results'] > 0:
            match_date = datetime.datetime.strptime(response['response'][0]['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
            match_date = match_date.astimezone(paris_tz)  # Convert to Paris/Berlin timezone
            match_date = match_date.date()
            today = datetime.date.today()

            if match_date == today:
                match_today = True
                match_start_datetime = datetime.datetime.strptime(response['response'][0]['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
                match_start_datetime = match_start_datetime.astimezone(paris_tz)  # Convert to Paris/Berlin timezone
                match_start_time = match_start_datetime.time()        
                fixture_id = response['response'][0]['fixture']['id']
                break
            
    return match_today, match_start_time, fixture_id, current_league_id

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
                
                if remaining_calls_per_day < 2:
                    raise RateLimitExceededError("Le nombre d'appels à l'API est dépassé. Le suivi du match est stoppé.")
                
                events_data = await events_response.json()
                #log_message(f"Réponse de l'API pour get_team_live_events : {events_data}")
                if not events_data.get('response'):
                    return None, None, None, None, None
                match_info = events_data['response'][0]
                #log_message(f"Réponse de l'API pour get_team_live_events : {match_info}\n")
                events = match_info['events']
                # Ajout du statut du match
                match_status = match_info['fixture']['status']['short']
                # Ajout du temps écoulé pour les logs (on ne renvoie pas la variable)
                elapsed_time = match_info['fixture']['status']['elapsed']
                log_message(f"Temps écoulé du match ' : {elapsed_time}\n")
                # Ajout des données du match
                match_data = match_info
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

# Fonction asynchrone pour vérifier les événements en cours pendant un match, tels que les buts et les cartons rouges, et envoyer des messages correspondants au chat_id fourni.
async def check_events(chat_id, fixture_id): 
    log_message("check_events(chat_id, fixture_id) appelée.")
    global sent_events
    current_score = {'home': 0, 'away': 0}
    previous_score = {'home': 0, 'away': 0}
    
    while True:
        try:
            events, match_status, elapsed_time, match_data, match_statistics = await get_team_live_events(fixture_id)
            log_message(f"Données récupérées de get_team_live_events dans check_events;\n Statistiques de match : (pas log),\n Status de match : {match_status},\n Events {events},\n match_data : (pas log)\n")
            # Calcul de l'intervalle optimisé (90 est le nombre d'appel max d'appel à l'api pour cette fonction en fonction du temps de match estimé)
            # DEBUG : Pour API payante max 7500 calls par jours
            #total_duree_championnat = 45 + 5 + 45 + 10
            #interval = (total_duree_championnat * 60) / 500
            # Pour API gratuite
            # Utilisez current_league_id pour définir un intervalle différent selon l'id de la ligue
            if current_league_id == 2:
                total_duree_championnat = 5 + 45 + 10 + 45 + 10 + 30
                interval = (total_duree_championnat * 60) / 90
            elif current_league_id == 207:
                total_duree_championnat = 5 + 45 + 10 + 45 + 10
                interval = (total_duree_championnat * 60) / 90
            elif current_league_id == 209:
                total_duree_championnat = 5 + 45 + 10 + 45 + 10 + 30
                interval = (total_duree_championnat * 60) / 90
            else:
                total_duree_championnat = 5 + 45 + 10 + 45 + 10
                interval = (total_duree_championnat * 60) / 90

            # Pause de 13 minutes (780 secondes) si le statut du match est 'HT' (mi-temps) car api vérifie statut toutes les 1-2minutes
            if match_status == 'HT':
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
                            log_message("Réinitialisation des événements à None après la mi-temps pour éviter d'être renvoyé.\n")
                            events = None
                        break

                    # Attendre un certain temps avant de vérifier à nouveau le statut du match
                    await asyncio.sleep(45)

            # Vérifiez que events n'est pas None avant de l'itérer
            if events is None:
                await asyncio.sleep(interval)
                continue

            # Check events 
            for event in events:
                # Vérifiez si l'attribut 'player' existe sinon on lui attribue une valeur nulle 
                player_id = event['player']['id'] if 'player' in event and event['player'] is not None else None
                # On créé une clé uniquement pour identifier l'événement en question
                event_key = f"{event['type']}_{event['time']['elapsed']}_{player_id}"
                event_key_sub = f"{event['type']}_{player_id}"

                if event_key in sent_events or event_key_sub in sent_events:
                    continue

                if event['type'] == "Goal":
                    log_message(f"type == Goal")   
                    # Vérifier si le score a été modifié
                    new_score = {'home': match_data['goals']['home'],
                                 'away': match_data['goals']['away']}
                    log_message(f"Données de score récupéré dans match_data pour la variable new_score : {new_score}")
                    log_message(f"Previous score : {previous_score}")
                
                    #On vérifie qu'il n'y pas eu de pénalté manqué 
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
                                    log_message(f"player_statistics : {player_statistics}\n")
                                    break
                            if player_statistics:
                                break
                        log_message(f"player value : {player}")
                        # Véfirier également que l'ID et le nom du joueur ne sont pas None. 
                        if player is not None and player['id'] is not None and player['name'] is not None:
                            log_message(f"player value is not none")
                            # Vérifiez si l'événement de but est dans les 2 dernières minutes
                            current_elapsed_time = elapsed_time
                            goal_elapsed_time = event['time']['elapsed']
                            log_message(f"if {goal_elapsed_time} >= {current_elapsed_time} - 5")
                            #Permet d'éviter qu'on rentre dans une modification trop tard ce qui pourrait poser problème avec les vérifications du score si des buts sont marqués entre temps.
                            if goal_elapsed_time >= current_elapsed_time - 5:
                                log_message(f"L'événement de goal a été détecté dans un interval de 5 minutes par rapport au temps actuel du match")    
                                if new_score != current_score:
                                    log_message(f"new_score != current_score")
                                    await send_goal_message(chat_id, player, team, player_statistics if player_statistics else [], event['time']['elapsed'], match_data)
                                    log_message(f"event_key enregistrée : {event_key}")
                                    sent_events.add(event_key)
                                    previous_score = current_score.copy()
                                    log_message(f"previous_score après maj avec current_score.copy() : {previous_score}")
                                    current_score = new_score.copy()
                                    log_message(f"current_score après maj avec new_score.copy() : {current_score}")
                                else:   
                                    log_message(f"new_score == current_score")
                                    log_message("Le score n'a pas été modifié, il s'agit probablement d'une correction d'un goal précédemment envoyé.")
                                    await send_goal_edited_message(chat_id, player, team, player_statistics if player_statistics else [], event['time']['elapsed'], match_data)
                                    sent_events.add(event_key)
                          
                # Vérifier si un goal a été annulé
                log_message(f"Données previous_score : {previous_score} et current_score : {current_score} avant la condition if current_score['home'] < previous_score['home'] or...")
                if current_score['home'] < previous_score['home'] or current_score['away'] < previous_score['away']:
                   log_message("Un goal a été annulé.")
                   await send_goal_cancelled_message(chat_id, previous_score, current_score)
                   previous_score = current_score.copy()
           
                            
                elif event['type'] == "Card" and event['detail'] == "Red Card":
                    log_message(f"Carton rouge détecté")
                    player = event['player']
                    team = event['team']
                    
                    log_message(f"Nom du joueur ayant un carton rouge : {player}")
                    # Vérifiez si le joueur n'est pas None et si son nom est présent
                    if player is not None and 'name' in player:
                        await send_red_card_message(chat_id, player, team, event['time']['elapsed'])
                        log_message(f"event_key enregistrée : {event_key}")
                        sent_events.add(event_key)
                    else:
                        log_message(f"Le nom du joueur est manquant ou 'player' est None, le message de carton rouge n'a pas été envoyé")
                        continue

            # Si le match est terminé ou s'est terminé en prolongation, envoyez le message de fin et arrêtez de vérifier les événements
            if match_status == 'FT' or match_status == 'AET':
                log_message(f"Le match est terminé, status : {match_status}\n")
                #log_message(f"match_data pour décomposé les statistiques du match : {match_data}\n")
                home_team = match_data['teams']['home']['name']
                away_team = match_data['teams']['away']['name']
                home_score = match_data['score']['fulltime']['home']
                away_score = match_data['score']['fulltime']['away']

                log_message(f"Envoi des variables à send_end_message avec chat_id: {chat_id}, home_team: {home_team}, away_team: {away_team}, home_score: {home_score}, away_score: {away_score}, match_statistics: {match_statistics}, events: {events}\n")
                await send_end_message(chat_id, home_team, away_team, home_score, away_score, match_statistics, events)
                break

        # Si le nombre d'appels à l'API restant est dépassé, on lève une exception et on sort de la boucle !
        except RateLimitExceededError as e:
            log_message(f"Erreur : {e}")
            # Propagez l'exception pour sortir de la boucle
            raise e

        # Pause avant de vérifier à nouveau les événements
        await asyncio.sleep(interval)

# Envoie un message de début de match aux utilisateurs avec des informations sur le match, les compositions des équipes.
async def send_start_message(chat_id, match_data):
    log_message("send_start_message() appelée.")
    
    home_team = match_data['teams']['home']['name']
    away_team = match_data['teams']['away']['name']
    
    home_lineup = match_data['lineups'][home_team]['formation']
    away_lineup = match_data['lineups'][away_team]['formation']
    
    home_players = match_data['lineups'][home_team]['startXI']
    away_players = match_data['lineups'][away_team]['startXI']
    
    home_players_str = "Composition de {} :\n".format(home_team)
    for player in home_players:
        home_players_str += "• {} ({}, {})\n".format(player['player']['name'], player['player']['number'], player['player'].get('pos', 'N/A'))
    
    away_players_str = "Composition de {} :\n".format(away_team)
    for player in away_players:
        away_players_str += "• {} ({}, {})\n".format(player['player']['name'], player['player']['number'], player['player'].get('pos', 'N/A'))
    
    message = f"🚩 Le match commence !\n{home_team} ({home_lineup})\n ⚔️ \n{away_team} ({away_lineup})\n\n"
    message += home_players_str + "\n"
    message += away_players_str
    
    log_message(f"Contenu du message de send_start_message : {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        log_message(f"Message de début de match envoyé au chat {chat_id}.")
    except BadRequest as e:
        log_message(f"Erreur lors de l'envoi du message de goal (BadRequest) : {e}")
    except ClientConnectorError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ClientConnectorError) : {e}")
    except NetworkError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (NetworkError) : {e}")
    except Exception as e:
        log_message(f"Erreur inattendue lors de l'envoi du message de goal : {e}")
 
# Envoie un message aux utilisateurs pour informer d'un but marqué lors du match en cours, y compris les informations sur le joueur, l'équipe et les statistiques.
async def send_goal_message(chat_id, player, team, player_statistics, elapsed_time, match_data):
    log_message("send_goal_message() appelée.")
    log_message(f"Player: {player}")
    log_message(f"Team: {team}")
    log_message(f"Player statistics: {player_statistics}")
    message = f"⚽️ But ! {elapsed_time}'\n{player['name']} ({team['name']})\n"
    
    home_score = match_data['goals']['home']
    away_score = match_data['goals']['away']
    log_message(f"Données de but récupéré dans la fonction_send_goal_message : home_score : {home_score} & away_score {away_score}")
    message += f"{match_data['teams']['home']['name']} {home_score} - {away_score} {match_data['teams']['away']['name']}\n\n"

    # Ajoutez les statistiques du joueur ici
    message += f"Statistiques du buteur :\n"

    if player_statistics:
        log_message(f"if player_statistics passée avec succès")
        stats = player_statistics[0]
        none_count = 0  # Compteur pour les statistiques ayant une valeur 'None'

        for key, value in stats.items():
            if isinstance(value, dict) and 'total' in value:
                # Vérifiez si la valeur 'total' est différente de 'None'
                if value['total'] is not None:
                    message += f"{key}: {value['total']}\n"
                else:
                    none_count += 1

        # Vérifiez si toutes les statistiques ont une valeur 'None'
        if none_count == len(stats):
            message += "Aucune statistique disponible.\n"

    else:
        message += "Aucune statistique disponible.\n"

    log_message(f"Contenu du message de but : {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        log_message(f"Message de but envoyé au chat {chat_id}.")
    except BadRequest as e:
        log_message(f"Erreur lors de l'envoi du message de goal (BadRequest) : {e}")
    except ClientConnectorError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ClientConnectorError) : {e}")
    except NetworkError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (NetworkError) : {e}")
    except Exception as e:
        log_message(f"Erreur inattendue lors de l'envoi du message de goal : {e}")

async def send_goal_edited_message(chat_id, player, team, player_statistics, elapsed_time, match_data):
    log_message("send_goal_edited_message() appelée.")
    message = f"ℹ️ Mise à jour des infos du but !\n"
    
    message = f"⚽️ But ! {elapsed_time}'\n{player['name']} ({team['name']})\n"
    
    home_score = match_data['goals']['home']
    away_score = match_data['goals']['away']
    log_message(f"Données de but récupéré dans la fonction_send_goal_message : home_score : {home_score} & away_score {away_score}")
    message += f"{match_data['teams']['home']['name']} {home_score} - {away_score} {match_data['teams']['away']['name']}\n\n"

    # Ajoutez les statistiques du joueur ici
    message += f"Statistiques du buteur :\n"

    if player_statistics:
        log_message(f"if player_statistics passée avec succès")
        stats = player_statistics[0]
        none_count = 0  # Compteur pour les statistiques ayant une valeur 'None'

        for key, value in stats.items():
            if isinstance(value, dict) and 'total' in value:
                # Vérifiez si la valeur 'total' est différente de 'None'
                if value['total'] is not None:
                    message += f"{key}: {value['total']}\n"
                else:
                    none_count += 1

        # Vérifiez si toutes les statistiques ont une valeur 'None'
        if none_count == len(stats):
            message += "Aucune statistique disponible.\n"

    else:
        message += "Aucune statistique disponible.\n"

    log_message(f"Contenu du message de mise à jour du but : {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        log_message(f"Message de mise à jour du but envoyé au chat {chat_id}.")
    except BadRequest as e:
        log_message(f"Erreur lors de l'envoi du message de goal (BadRequest) : {e}")
    except ClientConnectorError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ClientConnectorError) : {e}")
    except NetworkError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (NetworkError) : {e}")
    except Exception as e:
        log_message(f"Erreur inattendue lors de l'envoi du message de goal : {e}")

async def send_goal_cancelled_message(chat_id, previous_score, current_score):
    log_message("send_goal_cancelled_message() appelée.")
    message = f"❌ But annulé !\n"
    message += f"Score précédent: {previous_score['home']} - {previous_score['away']}\n"
    message += f"Score actuel: {current_score['home']} - {current_score['away']}\n\n"

    try:
        await bot.send_message(chat_id=chat_id, text=message)
        log_message(f"Message de but annulé envoyé au chat {chat_id}.")
    except BadRequest as e:
        log_message(f"Erreur lors de l'envoi du message de goal (BadRequest) : {e}")
    except ClientConnectorError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ClientConnectorError) : {e}")
    except NetworkError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (NetworkError) : {e}")
    except Exception as e:
        log_message(f"Erreur inattendue lors de l'envoi du message de goal : {e}")

# Envoie un message aux utilisateurs pour informer d'un carton rouge lors du match en cours, y compris les informations sur le joueur et l'équipe.
async def send_red_card_message(chat_id, player, team, elapsed_time):
    log_message("send_red_card_message() appelée.")
    message = f"🟥 Carton rouge ! {elapsed_time}'\n{player['name']} ({team['name']})"
    log_message(f"Contenu du message de carton rouge : {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        log_message(f"Message de carton rouge envoyé au chat {chat_id}.")
    except BadRequest as e:
        log_message(f"Erreur lors de l'envoi du message de goal (BadRequest) : {e}")
    except ClientConnectorError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ClientConnectorError) : {e}")
    except NetworkError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (NetworkError) : {e}")
    except Exception as e:
        log_message(f"Erreur inattendue lors de l'envoi du message de goal : {e}")

# Envoie un message de fin de match aux utilisateurs avec le score final.
async def send_end_message(chat_id, home_team, away_team, home_score, away_score, match_statistics, events):
    log_message("send_end_message() appelée.")
    message = f"🏁 Fin du match !\n{home_team} {home_score} - {away_score} {away_team}\n\n"
    
    """
    # Ajoutez les statistiques ici
    message += f"Statistiques du match :\n"

    if len(match_statistics) >= 2:
        home_team_stats = match_statistics[0]['statistics']
        away_team_stats = match_statistics[1]['statistics']

        for home_stat, away_stat in zip(home_team_stats, away_team_stats):
            if 'type' in home_stat and 'value' in home_stat and 'type' in away_stat and 'value' in away_stat:
                message += f"{home_stat['type']}: {home_stat['value']} - {away_stat['value']}\n"
            else:
                log_message(f"Statistiques mal formées : {home_stat}, {away_stat}")
    else:
        message += "Statistiques de match non disponibles.\n"
    """
    # Appeler l'API ChatGPT et ajouter la réponse à la suite des statistiques du match
    chatgpt_analysis = await call_chatgpt_api(match_statistics, events)
    message += "🤖 Match analysé par l'IA :\n" + chatgpt_analysis

    log_message(f"Contenu du message de send_end_message : {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        log_message(f"Message de fin de match envoyé au chat {chat_id}.")
    except ChatNotFound as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ChatNotFound) : {e}")        
    except BadRequest as e:
        log_message(f"Erreur lors de l'envoi du message de goal (BadRequest) : {e}")
    except ClientConnectorError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (ClientConnectorError) : {e}")
    except NetworkError as e:
        log_message(f"Erreur lors de l'envoi du message de goal (NetworkError) : {e}")
    except Exception as e:
        log_message(f"Erreur inattendue lors de l'envoi du message de goal : {e}")


async def call_chatgpt_api(match_statistics, events):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Créez le message utilisateur en fonction des match_statistics et events
    user_message = f"\n\nVoici les événements du match :\n\n"
    for event in events:
        user_message += f"{event}\n"
    
    user_message += f"Voici les statistiques du match :\n\n"
    
    log_message(f"vérification de la longueur de la liste match_statistics et de la présence des clés statistics")
    # vous pouvez ajouter une vérification de la longueur de la liste match_statistics et de la présence des clés statistics avant de les utiliser (évite des erreurs si elles manquent)
    if len(match_statistics) >= 2 and 'statistics' in match_statistics[0] and 'statistics' in match_statistics[1]:
        for home_stat, away_stat in zip(match_statistics[0]['statistics'], match_statistics[1]['statistics']):
            if 'type' in home_stat and 'value' in home_stat and 'type' in away_stat and 'value' in away_stat:
                user_message += f"{home_stat['type']}: {home_stat['value']} - {away_stat['value']}\n"

    conversation_history = [
    {
        "role": "system",
        "content": (
            "Tu es un journaliste sportif spécialisé dans l'analyse de matchs de football. "
            "En utilisant les événements et statistiques de match fournis, donne une analyse détaillée de la prestation du Servette FC pendant le match."
        ),
    }
]
    data = {
        "model": "gpt-4",
        "messages": conversation_history + [{"role": "user", "content": user_message}],
        "max_tokens": 1000,
        "n": 1,
        "temperature": 0.5,
        "stop": None,
    }

    async with httpx.AsyncClient() as client:
        try:
            response_json = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=120.0)
            response_json.raise_for_status()

            message = response_json.json()["choices"][0]["message"]["content"].strip()
            log_message(f"Succès de la récupération de la réponse GPT-4 {message}")
            return message

        except httpx.HTTPError as e:
            log_message(f"Erreur lors de l'appel à l'API ChatGPT : {e}")
            return "Désolé, une erreur s'est produite. Je ne pourrais pas donner d'analyse pour ce match"
        except Exception as e:
            log_message(f"Erreur inattendue lors de l'appel à l'API ChatGPT : {e}")
            return "Désolé, une erreur inattendue s'est produite. Je ne pourrais pas donner d'analyse pour ce match"

# Fonction principale pour initialiser le bot, enregistrer les gestionnaires de messages et lancer la vérification périodique des matchs.
async def main():
    log_message("Bot démarré.")
    global bot
    bot = Bot(token=TOKEN_TELEGRAM)
    dp = Dispatcher(bot)
    initialize_chat_ids_file()
    dp.register_message_handler(on_start, commands=["start"])
    asyncio.create_task(check_match_periodically())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())