from datetime import datetime
import os
import threading
from zoneinfo import ZoneInfo
import aiohttp
import discord
from flask import Flask

# Serveur Flask pour maintenir le bot actif sur Render
app = Flask('')


@app.route('/')
def home():
  return "Bot Discord actif !"


def run_flask():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


threading.Thread(target=run_flask, daemon=True).start()

# Configurations
TOKEN = os.getenv('DISCORD_TOKEN')
UNBELIEVABOAT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxNTY0NzMzNDk1OTU4NDQwOTY5IiwiaWF0IjoxNzkzMTMxOTM2fQ.CnSGo8M2HTJXwhrZWS9iZJ9-VI3_C9t5HK-TVgVJUK8"

GUILD_ID = os.getenv('GUILD_ID', '1504495864503210006')
VOTE_CHANNEL_ID = int(os.getenv('VOTE_CHANNEL_ID', '1558847340738252810'))
WELCOME_CHANNEL_ID = 1504496160918732800

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)


def get_current_vote_reward() -> int:
  """Retourne 2 pièces du vendredi 19h au dimanche minuit (heure française), sinon 1 pièce."""
  now = datetime.now(ZoneInfo('Europe/Paris'))
  weekday = now.weekday()  # 4=Vendredi, 5=Samedi, 6=Dimanche

  if weekday == 4 and now.hour >= 19:
    return 2
  if weekday in (5, 6):
    return 2
  return 1


async def add_money_unbelievaboat(user_id: int, amount: int = 1):
  """Crédite le solde et récupère le nouveau solde cash."""
  url = f'https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}'
  headers = {
      'Authorization': UNBELIEVABOAT_TOKEN,
      'Content-Type': 'application/json',
  }
  payload = {'cash': amount}

  async with aiohttp.ClientSession() as session:
    async with session.patch(url, json=payload, headers=headers) as resp:
      if resp.status == 200:
        try:
          data = await resp.json()
          new_cash = data.get("cash", None)
          return True, new_cash, None
        except Exception:
          return True, None, None
      else:
        text = await resp.text()
        return False, None, text


@client.event
async def on_ready():
  print(f"Bot connecté et prêt : {client.user}")


@client.event
async def on_message(message):
  if message.author.id == client.user.id:
    return

  full_text = message.content.strip()
  if message.embeds:
    for embed in message.embeds:
      if embed.description:
        full_text += " " + embed.description
      if embed.title:
        full_text += " " + embed.title

  # ==========================================
  # 1. GESTION DES VOTES (Top-Serveurs)
  # ==========================================
  if message.channel.id == VOTE_CHANNEL_ID:
    if "vient de voter pour le serveur" in full_text.lower():
      parts = full_text.split(" vient de voter")
      if parts:
        voter_raw = parts[0].replace("@", "").strip()
        guild = message.guild
        member = None

        if message.mentions:
          member = message.mentions[0]

        if not member:
          for m in guild.members:
            if (
                m.name.lower() in voter_raw.lower()
                or m.display_name.lower() in voter_raw.lower()
            ):
              member = m
              break

        if member:
          reward_amount = get_current_vote_reward()
          success, new_balance, error_text = await add_money_unbelievaboat(
              member.id, reward_amount
          )

          if success:
            # Création d'un beau Embed stylisé
            embed = discord.Embed(
                title="🪙 Récompense de Vote Validée !",
                description=(
                    f"Merci {member.mention} d'avoir voté pour le"
                    f" serveur !\n\n✅ **+{reward_amount} coin(s)** ajoutés sur"
                    " ton compte."
                ),
                color=discord.Color.green(),
            )
            if new_balance is not None:
              embed.add_field(
                  name="💰 Nouveau Solde",
                  value=f"**{new_balance}** pièces",
                  inline=False,
              )
            embed.set_footer(text="Opex Wardogs & Squad • Système de Vote")

            await message.channel.send(embed=embed)
          else:
            await message.channel.send(
                f"⚠️ Erreur API Vote ({error_text}) pour {member.mention}."
            )
        else:
          print(f"[Erreur Vote] Membre non trouvé pour : {voter_raw}")

  # ==========================================
  # 2. GESTION DES INVITATIONS (Invite Tracker)
  # ==========================================
  if "has been invited by" in full_text.lower():
    try:
      part = full_text.split("has been invited by")[1]
      inviter_raw = part.split("and has now")[0].strip()

      guild = message.guild
      inviter_member = None

      if message.mentions:
        for mention in message.mentions:
          if (
              mention.name.lower() in inviter_raw.lower()
              or mention.display_name.lower() in inviter_raw.lower()
              or str(mention.id) in inviter_raw
          ):
            inviter_member = mention
            break

      if not inviter_member:
        clean_name = (
            inviter_raw.replace("<@", "")
            .replace(">", "")
            .replace("!", "")
            .replace("@", "")
            .strip()
        )
        for m in guild.members:
          if (
              m.name.lower() == clean_name.lower()
              or m.display_name.lower() == clean_name.lower()
          ):
            inviter_member = m
            break

      if inviter_member:
        invite_reward = 2
        success, new_balance, error_text = await add_money_unbelievaboat(
            inviter_member.id, invite_reward
        )

        cmd_channel = client.get_channel(VOTE_CHANNEL_ID)
        target_channel = cmd_channel if cmd_channel else message.channel

        if success:
          # Beau Embed stylisé pour l'invitation
          embed = discord.Embed(
              title="🎉 Nouveau Membre Invité !",
              description=(
                  f"Bien joué {inviter_member.mention} !\n\n✅ **+{invite_reward}"
                    " coin(s)** ajoutés pour l'invitation d'un nouveau"
                  " joueur."
              ),
              color=discord.Color.gold(),
          )
          if new_balance is not None:
            embed.add_field(
                name="💰 Nouveau Solde",
                value=f"**{new_balance}** pièces",
                inline=False,
            )
          embed.set_footer(
              text="Opex Wardogs & Squad • Système d'Invitation"
          )

          await target_channel.send(embed=embed)
        else:
          print(f"[Erreur API Invite] {error_text}")
      else:
        print(f"[Erreur Invite] Inviteur non trouvé : {inviter_raw}")

    except Exception as e:
      print(f"[Erreur Parsing Invite] {e}")


client.run(TOKEN)
