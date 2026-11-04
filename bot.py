from datetime import datetime
import os
import threading
from zoneinfo import ZoneInfo
import aiohttp
import discord
from flask import Flask

app = Flask('')


@app.route('/')
def home():
  return "Bot Discord actif !"


def run_flask():
  port = int(os.environ.get("PORT", 10000))
  app.run(host='0.0.0.0', port=port)


threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.getenv("DISCORD_TOKEN")
UNBELIEVABOAT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxNTY0NzMzNDk1OTU4NDQwOTY5IiwiaWF0IjoxNzkzMTMxOTM2fQ.CnSGo8M2HTJXwhrZWS9iZJ9-VI3_C9t5HK-TVgVJUK8"

# Configurations des salons et du serveur
GUILD_ID = os.getenv("GUILD_ID", "1504495864503210006")
VOTE_CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))
WELCOME_CHANNEL_ID = 1504496160918732800  # Ton salon Bienvenue / Invite Tracker

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)


def get_current_vote_reward() -> int:
  """Retourne 2 pièces du vendredi 19h au dimanche minuit (heure française), sinon 1 pièce."""
  now = datetime.now(ZoneInfo("Europe/Paris"))
  weekday = now.weekday()  # 4=Vendredi, 5=Samedi, 6=Dimanche

  if weekday == 4 and now.hour >= 19:
    return 2
  if weekday in (5, 6):
    return 2
  return 1


async def add_money_unbelievaboat(user_id: int, amount: int = 1):
  """Crédite les pièces sur le compte UnbelievaBoat du membre."""
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
  print(f"Bot connecté et opérationnel : {client.user}")


@client.event
async def on_message(message):
  # Empêcher le bot de se répondre à lui-même
  if message.author == client.user:
    return

  content = message.content.strip()

  # ==========================================
  # 1. SALON DES VOTES (Top-Serveurs)
  # ==========================================
  if message.channel.id == VOTE_CHANNEL_ID:
    if "vient de voter pour le serveur" in content.lower():
      parts = content.split(" vient de voter")
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
          reward_amount = get_current_vote_reward()
          success, error_text = await add_money_unbelievaboat(
              member.id, reward_amount
          )
          if success:
            await message.channel.send(
                f"✅ {reward_amount} coin(s) ajouté(s) sur le shop"
                f" UnbelievaBoat pour {member.mention} (Vote) !"
            )
          else:
            await message.channel.send(
                f"⚠️ Erreur API Vote ({error_text}) pour {member.mention}."
            )
        else:
          print(f"[Erreur] Membre vote non trouvé : {voter_name}")

  # ==========================================
  # 2. SALON DE BIENVENUE (Invite Tracker)
  # ==========================================
  elif message.channel.id == WELCOME_CHANNEL_ID:
    if "has been invited by" in content.lower():
      try:
        # Extrait le nom du membre qui a invité
        part = content.split("has been invited by")[1]
        inviter_name = part.split("and has now")[0].strip()
        inviter_name = inviter_name.replace("*", "").replace("@", "").strip()

        guild = message.guild
        inviter_member = None

        for m in guild.members:
          if (
              m.name.lower() == inviter_name.lower()
              or m.display_name.lower() == inviter_name.lower()
          ):
            inviter_member = m
            break

        if inviter_member:
          invite_reward = 2  # 2 pièces par invitation
          success, error_text = await add_money_unbelievaboat(
              inviter_member.id, invite_reward
          )

          # Récupère le salon des votes/commandes pour envoyer la confirmation là-bas
          cmd_channel = client.get_channel(VOTE_CHANNEL_ID)
          target_channel = cmd_channel if cmd_channel else message.channel

          if success:
            await target_channel.send(
                f"🎉 {invite_reward} coin(s) ajoutés sur le shop UnbelievaBoat"
                f" pour {inviter_member.mention} (Invitation d'un nouveau"
                " membre) !"
            )
          else:
            print(f"[Erreur API Invite] {error_text}")
        else:
          print(f"[Erreur] Inviteur non trouvé : {inviter_name}")
      except Exception as e:
        print(f"[Erreur Parsing Invite] {e}")


client.run(TOKEN)
