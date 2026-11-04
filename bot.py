from datetime import datetime
import os
import threading
import aiohttp
from flask import Flask
import discord
from zoneinfo import ZoneInfo

app = Flask('')


@app.route('/')
def home():
  return "Bot Discord actif !"


def run_flask():
  port = int(os.environ.get("PORT", 10000))
  app.run(host='0.0.0.0', port=port)


threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.getenv("DISCORD_TOKEN")
# Jeton UnbelievaBoat d'API
UNBELIEVABOAT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxNTY0NzMzNDk1OTU4NDQwOTY5IiwiaWF0IjoxNzkzMTMxOTM2fQ.CnSGo8M2HTJXwhrZWS9iZJ9-VI3_C9t5HK-TVgVJUK8"

# ID de ton serveur Discord OPEX Wardogs & Squad
GUILD_ID = os.getenv("GUILD_ID", "1504495864503210006")
CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)


def get_current_reward() -> int:
  """MODIFICATION TEMPORAIRE POUR TESTER LES 2 PIÈCES"""
  return 2  # On force le bot à donner 2 pièces pour ton test

  # Le reste de la fonction est mis en pause tant que le return 2 est ici
  now = datetime.now(ZoneInfo("Europe/Paris"))
  weekday = now.weekday()
  if weekday == 4 and now.hour >= 19:
    return 2
  if weekday == 5:
    return 2
  if weekday == 6:
    return 2
  return 1


async def add_money_unbelievaboat(user_id: int, amount: int = 1):
  """Ajoute de l'argent cash via l'API officielle d'UnbelievaBoat"""
  url = f'https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}'
  headers = {
      'Authorization': UNBELIEVABOAT_TOKEN,
      'Content-Type': 'application/json',
  }
  payload = {'cash': amount}

  async with aiohttp.ClientSession() as session:
    async with session.patch(url, json=payload, headers=headers) as resp:
      text = await resp.text()
      print(f'[API Response] Status: {resp.status} | Body: {text}')
      return resp.status == 200, text


@client.event
async def on_ready():
  print(f"Bot connecté sous l'identité : {client.user}")


@client.event
async def on_message(message):
  if message.author == client.user or message.channel.id != CHANNEL_ID:
    return

  content = message.content.strip()

  # Détection du message de vote Top-Serveurs
  if 'vient de voter pour le serveur' in content.lower():
    parts = content.split(' vient de voter')
    if parts:
      voter_name = parts[0].strip()
      guild = message.guild
      member = None

      for m in guild.members:
        if (
            m.name.lower() == voter_name.lower()
            or m.display_name.lower() == voter_name.lower()
        ):
          member = m
          break

      if member:
        # Calcul dynamique de la récompense (2 pièces le week-end, 1 le reste du temps)
        reward_amount = get_current_reward()

        success, error_text = await add_money_unbelievaboat(
            member.id, reward_amount
        )
        if success:
          await message.channel.send(
              f'✅ {reward_amount} coin(s) ajouté(s) sur le shop'
              f' UnbelievaBoat pour {member.mention} !'
          )
        else:
          await message.channel.send(
              f'⚠️ Erreur API ({error_text}) pour {member.mention}.'
          )
      else:
        print(f'[Erreur] Membre non trouvé pour : {voter_name}')


client.run(TOKEN)
