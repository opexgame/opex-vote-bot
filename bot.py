from datetime import datetime
import os
import random
import threading
from zoneinfo import ZoneInfo
import aiohttp
import discord
from discord.ext import tasks
from discord.ui import Button, View
from flask import Flask

# Serveur Flask pour maintenir le bot actif sur Render
app = Flask("")


@app.route("/")
def home():
  return "Bot Discord actif !"


def run_flask():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_flask, daemon=True).start()

# Configurations
TOKEN = os.getenv("DISCORD_TOKEN")
UNBELIEVABOAT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxNTY0NzMzNDk1OTU4NDQwOTY5IiwiaWF0IjoxNzkzMTMxOTM2fQ.CnSGo8M2HTJXwhrZWS9iZJ9-VI3_C9t5HK-TVgVJUK8"

GUILD_ID = os.getenv("GUILD_ID", "1504495864503210006")
VOTE_CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))
WELCOME_CHANNEL_ID = 1504496160918732800

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

# Variables globales pour la loterie
lottery_tickets = {}  # { user_id: nombre_de_tickets }
TICKET_PRICE = 5
jackpot_pool = 0  # Cagnotte de départ

# Variables globales pour la Guerre des Équipes
team_members = {}  # { user_id: "Rouge" | "Vert" | "Bleu" }
team_votes = {"Rouge": 0, "Vert": 0, "Bleu": 0}

ROLE_ROUGE_NAME = "Équipe Rouge"
ROLE_VERT_NAME = "Équipe Verte"
ROLE_BLEU_NAME = "Équipe Bleue"


def get_current_vote_reward() -> int:
  now = datetime.now(ZoneInfo("Europe/Paris"))
  weekday = now.weekday()
  if weekday == 4 and now.hour >= 19:
    return 2
  if weekday in (5, 6):
    return 2
  return 1


async def add_money_unbelievaboat(user_id: int, amount: int = 1):
  url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
  headers = {
      "Authorization": UNBELIEVABOAT_TOKEN,
      "Content-Type": "application/json",
  }
  payload = {"cash": amount}

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


# Class pour la sélection de faction (Équipes)
class TeamSelectionView(View):

  def __init__(self, server_icon_url: str):
    super().__init__(timeout=None)
    self.server_icon_url = server_icon_url

  async def process_team_join(
      self, interaction: discord.Interaction, chosen_team: str
  ):
    global team_members
    # Répondre immédiatement en différé pour éviter l'erreur de délai Discord
    await interaction.response.defer(ephemeral=True)

    user = interaction.user
    guild = interaction.guild

    counts = {"Rouge": 0, "Vert": 0, "Bleu": 0}
    for t in team_members.values():
      if t in counts:
        counts[t] += 1

    current_user_team = team_members.get(user.id)

    if current_user_team == chosen_team:
      await interaction.followup.send(
          f"⚠️ Tu es déjà dans l'**Équipe {chosen_team}** !", ephemeral=True
      )
      return

    temp_counts = counts.copy()
    if current_user_team:
      temp_counts[current_user_team] -= 1
    temp_counts[chosen_team] += 1

    min_team_size = min(temp_counts.values())
    target_team_size = temp_counts[chosen_team]

    if target_team_size - min_team_size > 1:
      await interaction.followup.send(
          f"❌ L'**Équipe {chosen_team}** est complète pour le moment !\nMerci"
          " de choisir une autre équipe pour garder un nombre de participants"
          " équitable.",
          ephemeral=True,
      )
      return

    team_members[user.id] = chosen_team

    role_rouge = discord.utils.get(guild.roles, name=ROLE_ROUGE_NAME)
    role_vert = discord.utils.get(guild.roles, name=ROLE_VERT_NAME)
    role_bleu = discord.utils.get(guild.roles, name=ROLE_BLEU_NAME)

    roles_to_remove = [
        r for r in [role_rouge, role_vert, role_bleu] if r in user.roles
    ]
    if roles_to_remove:
      await user.remove_roles(*roles_to_remove)

    target_role = None
    if chosen_team == "Rouge":
      target_role = role_rouge
    elif chosen_team == "Vert":
      target_role = role_vert
    elif chosen_team == "Bleu":
      target_role = role_bleu

    if target_role:
      await user.add_roles(target_role)

    counts[chosen_team] += 1
    if current_user_team:
      counts[current_user_team] -= 1

    embed = discord.Embed(
        title="⚔️ GUERRE DES ÉQUIPES - Choisis ta Faction !",
        description=(
            "Rejoins une équipe pour participer au classement hebdomadaire"
            " !\nL'équipe avec le plus de points à la fin de la semaine se"
            " partagera la cagnotte.\n\n"
            f"🔴 **Équipe Rouge :** `{counts['Rouge']}` membre(s) | Points:"
            f" `{team_votes['Rouge']}`\n"
            f"🟢 **Équipe Verte :** `{counts['Vert']}` membre(s) | Points:"
            f" `{team_votes['Vert']}`\n"
            f"🔵 **Équipe Bleue :** `{counts['Bleu']}` membre(s) | Points:"
            f" `{team_votes['Bleu']}`"
        ),
        color=discord.Color.dark_theme(),
    )
    embed.set_footer(
        text="Opex Wardogs & Squad • Équilibrage Automatique",
        icon_url=self.server_icon_url,
    )

    await interaction.message.edit(embed=embed, view=self)
    await interaction.followup.send(
        f"✅ Tu as rejoint l'**Équipe {chosen_team}** avec succès !",
        ephemeral=True,
    )

  @discord.ui.button(
      label="Équipe Rouge 🔴",
      style=discord.ButtonStyle.danger,
      custom_id="join_team_rouge",
  )
  async def btn_rouge(self, interaction: discord.Interaction, button: Button):
    await self.process_team_join(interaction, "Rouge")

  @discord.ui.button(
      label="Équipe Verte 🟢",
      style=discord.ButtonStyle.success,
      custom_id="join_team_vert",
  )
  async def btn_vert(self, interaction: discord.Interaction, button: Button):
    await self.process_team_join(interaction, "Vert")

  @discord.ui.button(
      label="Équipe Bleue 🔵",
      style=discord.ButtonStyle.primary,
      custom_id="join_team_bleu",
  )
  async def btn_bleu(self, interaction: discord.Interaction, button: Button):
    await self.process_team_join(interaction, "Bleu")


# Class pour gérer le bouton d'Airdrop
class AirdropView(View):

  def __init__(
      self, reward_amount: int, server_icon_url: str, vote_channel_id: int
  ):
    super().__init__(timeout=300)
    self.reward_amount = reward_amount
    self.server_icon_url = server_icon_url
    self.vote_channel_id = vote_channel_id
    self.claimed = False

  @discord.ui.button(
      label="Ouvrir le coffre ! 🎁",
      style=discord.ButtonStyle.success,
      custom_id="claim_airdrop",
  )
  async def claim_button(
      self, interaction: discord.Interaction, button: Button
  ):
    if self.claimed:
      await interaction.response.send_message(
          "❌ Ce coffre a déjà été récupéré par quelqu'un d'autre !",
          ephemeral=True,
      )
      return

    self.claimed = True
    user = interaction.user

    success, new_balance, error_text = await add_money_unbelievaboat(
        user.id, self.reward_amount
    )

    button.disabled = True
    button.label = f"Récupéré par {user.display_name} !"
    button.style = discord.ButtonStyle.secondary
    await interaction.message.edit(view=self)

    if success:
      embed = discord.Embed(
          title="🎉 Coffre Ouvert !",
          description=(
              f"Félicitations {user.mention} !\n\nTu as été le plus rapide et"
              f" tu remportes **+{self.reward_amount} coin(s)** !"
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
          text="Opex Wardogs & Squad • Drop Mystère",
          icon_url=self.server_icon_url,
      )

      await interaction.response.send_message(
          "✅ Tu as ouvert le coffre avec succès ! L'annonce a été envoyée"
          " dans le salon vote.",
          ephemeral=True,
      )

      vote_channel = interaction.client.get_channel(self.vote_channel_id)
      if vote_channel:
        await vote_channel.send(embed=embed)
      else:
        await interaction.channel.send(embed=embed)
    else:
      await interaction.response.send_message(
          f"⚠️ Erreur lors du crédit des pièces : {error_text}", ephemeral=True
      )


# Class pour gérer la loterie
class LotteryView(View):

  def __init__(self, server_icon_url: str):
    super().__init__(timeout=None)
    self.server_icon_url = server_icon_url

  @discord.ui.button(
      label="🎟️ Acheter un ticket (5 pièces)",
      style=discord.ButtonStyle.primary,
      custom_id="buy_lottery_ticket",
  )
  async def buy_ticket(self, interaction: discord.Interaction, button: Button):
    global lottery_tickets, jackpot_pool
    user = interaction.user

    success, new_balance, error_text = await add_money_unbelievaboat(
        user.id, -TICKET_PRICE
    )

    if success:
      lottery_tickets[user.id] = lottery_tickets.get(user.id, 0) + 1
      jackpot_pool += TICKET_PRICE

      participants_text = ""
      for uid, count in lottery_tickets.items():
        participants_text += f"• <@{uid}> : **{count}** ticket(s)\n"

      if not participants_text:
        participants_text = "Aucun participant pour l'instant. Soyez le premier !"

      embed = discord.Embed(
          title="🎟️ LOTERIE HEBDOMADAIRE - Tente ta chance !",
          description=(
              "Clique sur le bouton ci-dessous pour acheter **1 ticket** pour"
              f" **{TICKET_PRICE} pièces** !\n\n💰 **Jackpot en jeu :**"
              f" `__{jackpot_pool}__` pièces\n\n👥 **Participants éligibles"
              f" :**\n{participants_text}"
          ),
          color=discord.Color.blurple(),
      )
      embed.set_footer(
          text="Opex Wardogs & Squad • Tirage Manuel",
          icon_url=self.server_icon_url,
      )

      await interaction.message.edit(embed=embed, view=self)
      await interaction.response.send_message(
          "✅ Achat réussi ! Ton ticket a bien été enregistré.", ephemeral=True
      )
    else:
      await interaction.response.send_message(
          "❌ Achat impossible : Tu n'as pas assez de pièces sur ton compte"
          " UnbelievaBoat !",
          ephemeral=True,
      )


@client.event
async def on_ready():
  print(f"Bot connecté et prêt : {client.user}")


@client.event
async def on_message(message):
  if message.author.id == client.user.id:
    return

  global jackpot_pool, lottery_tickets, team_members, team_votes

  full_text = message.content.strip()
  if message.embeds:
    for embed in message.embeds:
      if embed.description:
        full_text += " " + embed.description
      if embed.title:
        full_text += " " + embed.title

  guild = message.guild
  server_icon = guild.icon.url if guild and guild.icon else None

  # ==========================================
  # COMMANDE ADMIN : !lancerteams
  # ==========================================
  if full_text.lower() == "!lancerteams":
    if message.author.guild_permissions.manage_guild:
      counts = {"Rouge": 0, "Vert": 0, "Bleu": 0}
      for t in team_members.values():
        if t in counts:
          counts[t] += 1

      embed = discord.Embed(
          title="⚔️ GUERRE DES ÉQUIPES - Choisis ta Faction !",
          description=(
              "Rejoins une équipe pour participer au classement hebdomadaire"
              " !\nL'équipe avec le plus de points à la fin de la semaine se"
              " partagera la cagnotte.\n\n"
              f"🔴 **Équipe Rouge :** `{counts['Rouge']}` membre(s) | Points:"
              f" `{team_votes['Rouge']}`\n"
              f"🟢 **Équipe Verte :** `{counts['Vert']}` membre(s) | Points:"
              f" `{team_votes['Vert']}`\n"
              f"🔵 **Équipe Bleue :** `{counts['Bleu']}` membre(s) | Points:"
              f" `{team_votes['Bleu']}`"
          ),
          color=discord.Color.dark_theme(),
      )
      embed.set_footer(
          text="Opex Wardogs & Squad • Équilibrage Automatique",
          icon_url=server_icon,
      )

      view = TeamSelectionView(server_icon_url=server_icon)
      await message.channel.send(embed=embed, view=view)
      await message.delete()
    else:
      await message.channel.send(
          "❌ Tu n'as pas la permission d'utiliser cette commande.",
          delete_after=5,
      )
    return

  # ==========================================
  # COMMANDE ADMIN : !resetteams
  # Réinitialise les équipes, retire les rôles et remet les points à zéro
  # ==========================================
  if full_text.lower() == "!resetteams":
    if message.author.guild_permissions.manage_guild:
      role_rouge = discord.utils.get(guild.roles, name=ROLE_ROUGE_NAME)
      role_vert = discord.utils.get(guild.roles, name=ROLE_VERT_NAME)
      role_bleu = discord.utils.get(guild.roles, name=ROLE_BLEU_NAME)

      # Retirer les rôles d'équipe à tous les membres du serveur qui les ont
      for member in guild.members:
        roles_to_remove = [
            r
            for r in [role_rouge, role_vert, role_bleu]
            if r and r in member.roles
        ]
        if roles_to_remove:
          try:
            await member.remove_roles(*roles_to_remove)
          except Exception:
            pass

      # Vider les dictionnaires et compteurs
      team_members.clear()
      team_votes = {"Rouge": 0, "Vert": 0, "Bleu": 0}

      await message.channel.send(
          "🔄 **Réinitialisation des équipes réussie !** Tous les rôles ont été"
          " retirés et les points remis à zéro."
      )
    else:
      await message.channel.send(
          "❌ Tu n'as pas la permission d'utiliser cette commande.",
          delete_after=5,
      )
    return

  # ==========================================
  # COMMANDE ADMIN : !tirageloterie
  # ==========================================
  if full_text.lower() == "!tirageloterie":
    if message.author.guild_permissions.manage_guild:
      if not lottery_tickets:
        await message.channel.send(
            "⚠️ Aucun participant n'a encore acheté de ticket pour cette"
            " loterie !"
        )
        return

      pool_list = []
      for uid, count in lottery_tickets.items():
        pool_list.extend([uid] * count)

      winner_id = random.choice(pool_list)

      success, new_balance, error_text = await add_money_unbelievaboat(
          winner_id, jackpot_pool
      )

      winner_member = guild.get_member(winner_id)
      winner_mention = (
          winner_member.mention if winner_member else f"<@{winner_id}>"
      )

      if success:
        embed = discord.Embed(
            title="🎉 RÉSULTAT DE LA LOTERIE ! 🎟️",
            description=(
                f"Le tirage au sort vient d'avoir lieu !\n\n👑 Félicitations à"
                f" {winner_mention} qui remporte le jackpot de"
                f" **+{jackpot_pool} pièce(s)** !"
            ),
            color=discord.Color.gold(),
        )
        if new_balance is not None:
          embed.add_field(
              name="💰 Nouveau Solde du Gagnant",
              value=f"**{new_balance}** pièces",
              inline=False,
          )
        embed.set_footer(
            text="Opex Wardogs & Squad • Loterie du Serveur",
            icon_url=server_icon,
        )

        vote_channel = client.get_channel(VOTE_CHANNEL_ID)
        target_channel = vote_channel if vote_channel else message.channel

        await target_channel.send(embed=embed)

        if vote_channel and message.channel.id != VOTE_CHANNEL_ID:
          await message.channel.send(
              "✅ Tirage effectué ! Annonce envoyée dans le salon de vote."
          )

        lottery_tickets = {}
        jackpot_pool = 0
      else:
        await message.channel.send(
            f"⚠️ Erreur API lors du crédit du jackpot : {error_text}"
        )
    else:
      await message.channel.send(
          "❌ Tu n'as pas la permission d'utiliser cette commande.",
          delete_after=5,
      )
    return

  # ==========================================
  # COMMANDE ADMIN : !addcagnotte [montant]
  # ==========================================
  if full_text.lower().startswith("!addcagnotte"):
    if message.author.guild_permissions.manage_guild:
      parts = full_text.split()
      if len(parts) > 1 and parts[1].isdigit():
        added_amount = int(parts[1])
        jackpot_pool += added_amount

        await message.channel.send(
            f"✅ **+{added_amount} pièces** ont été ajoutées à la cagnotte par le"
            f" serveur !\n💰 **Nouveau Jackpot :** `{jackpot_pool}` pièces."
        )
      else:
        await message.channel.send(
            "⚠️ Utilisation correcte : `!addcagnotte 50`", delete_after=6
        )
    else:
      await message.channel.send(
          "❌ Tu n'as pas la permission d'utiliser cette commande.",
          delete_after=5,
      )
    return

  # ==========================================
  # COMMANDE ADMIN : !lancerloterie
  # ==========================================
  if full_text.lower() == "!lancerloterie":
    if message.author.guild_permissions.manage_guild:
      participants_text = (
          "Aucun participant pour l'instant. Soyez le premier !"
      )

      embed = discord.Embed(
          title="🎟️ LOTERIE HEBDOMADAIRE - Tente ta chance !",
          description=(
              "Clique sur le bouton ci-dessous pour acheter **1 ticket** pour"
              f" **{TICKET_PRICE} pièces** !\n\n💰 **Jackpot en jeu :**"
              f" `__{jackpot_pool}__` pièces\n\n👥 **Participants éligibles"
              f" :**\n{participants_text}"
          ),
          color=discord.Color.blurple(),
      )
      embed.set_footer(
          text="Opex Wardogs & Squad • Tirage Manuel", icon_url=server_icon
      )

      view = LotteryView(server_icon_url=server_icon)
      await message.channel.send(embed=embed, view=view)
      await message.delete()
    else:
      await message.channel.send(
          "❌ Tu n'as pas la permission d'utiliser cette commande.",
          delete_after=5,
      )
    return

  # ==========================================
  # COMMANDE DE TEST : !testdrop
  # ==========================================
  if full_text.lower() == "!testdrop":
    airdrop_embed = discord.Embed(
        title="📦 UN COFFRE MYSTÈRE EST APPARU ! [TEST]",
        description=(
            "Un parachutage de ravitaillement vient de tomber dans le chat"
            " !\n\nClique vite sur le bouton ci-dessous pour récupérer **5"
            " pièce(s)** !"
        ),
        color=discord.Color.purple(),
    )
    airdrop_embed.set_footer(
        text="Opex Wardogs & Squad • Drop Aléatoire", icon_url=server_icon
    )

    view = AirdropView(
        reward_amount=5,
        server_icon_url=server_icon,
        vote_channel_id=VOTE_CHANNEL_ID,
    )
    await message.channel.send(embed=airdrop_embed, view=view)
    return

  # ==========================================
  # 1. GESTION DES VOTES (Top-Serveurs)
  # ==========================================
  if message.channel.id == VOTE_CHANNEL_ID:
    if "vient de voter pour le serveur" in full_text.lower():
      parts = full_text.split(" vient de voter")
      if parts:
        voter_raw = parts[0].replace("@", "").strip()
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

          voter_team = team_members.get(member.id)
          team_msg = ""
          if voter_team:
            team_votes[voter_team] += 1
            team_msg = (
                f"\n⚔️ **+1 Point** ajouté pour l'**Équipe {voter_team}** !"
            )

          if success:
            embed = discord.Embed(
                title="🪙 Récompense de Vote Validée !",
                description=(
                    f"Merci {member.mention} d'avoir voté pour le"
                    f" serveur !\n\n✅ **+{reward_amount} coin(s)** ajoutés sur"
                    f" ton compte.{team_msg}"
                ),
                color=discord.Color.green(),
            )
            if new_balance is not None:
              embed.add_field(
                  name="💰 Nouveau Solde",
                  value=f"**{new_balance}** pièces",
                  inline=False,
              )
            embed.set_footer(
                text="Opex Wardogs & Squad • Système de Vote",
                icon_url=server_icon,
            )

            await message.channel.send(embed=embed)

  # ==========================================
  # 2. GESTION DES INVITATIONS (Invite Tracker)
  # ==========================================
  if "has been invited by" in full_text.lower():
    try:
      parts_split = full_text.split("has been invited by")
      left_part = parts_split[0].strip()
      right_part = parts_split[1].strip()
      inviter_raw = right_part.split("and has now")[0].strip()

      invited_member = None
      if message.mentions:
        invited_member = message.mentions[0]

      if not invited_member:
        clean_invited = (
            left_part.replace("<@", "")
            .replace(">", "")
            .replace("!", "")
            .replace("@", "")
            .strip()
        )
        for m in guild.members:
          if (
              m.name.lower() == clean_invited.lower()
              or m.display_name.lower() == clean_invited.lower()
          ):
            invited_member = m
            break

      inviter_member = None
      if len(message.mentions) > 1:
        for mention in message.mentions:
          if mention.id != (
              invited_member.id if invited_member else None
          ) and (
              mention.name.lower() in inviter_raw.lower()
              or mention.display_name.lower() in inviter_raw.lower()
              or str(mention.id) in inviter_raw
          ):
            inviter_member = mention
            break

      if not inviter_member:
        clean_inviter = (
            inviter_raw.replace("<@", "")
            .replace(">", "")
            .replace("!", "")
            .replace("@", "")
            .strip()
        )
        for m in guild.members:
          if (
              m.name.lower() == clean_inviter.lower()
              or m.display_name.lower() == clean_inviter.lower()
          ):
            inviter_member = m
            break

      if inviter_member:
        invite_reward = 2
        success, new_balance, error_text = await add_money_unbelievaboat(
            inviter_member.id, invite_reward
        )

        inviter_team = team_members.get(inviter_member.id)
        team_invite_msg = ""
        if inviter_team:
          team_votes[inviter_team] += 2
          team_invite_msg = (
              f"\n⚔️ **+2 Points** ajoutés à l'**Équipe {inviter_team}** !"
          )

        cmd_channel = client.get_channel(VOTE_CHANNEL_ID)
        target_channel = cmd_channel if cmd_channel else message.channel

        if success:
          invited_text = (
              invited_member.mention if invited_member else left_part
          )

          embed = discord.Embed(
              title="🎉 Nouveau Membre Invité !",
              description=(
                  f"Bien joué {inviter_member.mention} !\n\n✅ **+{invite_reward}"
                  f" coin(s)** ajoutés pour l'invitation de"
                  f" {invited_text}.{team_invite_msg}\n👋 Bienvenue à lui !"
              ),
              color=discord.Color.gold(),
          )
          if new_balance is not None:
            embed.add_field(
                name="💰 Nouveau Solde de l'inviteur",
                value=f"**{new_balance}** pièces",
                inline=False,
            )
          embed.set_footer(
              text="Opex Wardogs & Squad • Système d'Invitation",
              icon_url=server_icon,
          )

          await target_channel.send(embed=embed)

    except Exception as e:
      print(f"[Erreur Parsing Invite] {e}")

  # ==========================================
  # 3. SYSTEME D'AIRDROP ALEATOIRE (5% de chance)
  # ==========================================
  if message.channel.id != VOTE_CHANNEL_ID and not message.author.bot:
    if random.randint(1, 100) <= 5:
      airdrop_embed = discord.Embed(
          title="📦 UN COFFRE MYSTÈRE EST APPARU !",
          description=(
              "Un parachutage de ravitaillement vient de tomber dans le chat"
              " !\n\nClique vite sur le bouton ci-dessous pour récupérer **5"
              " pièce(s)** !"
          ),
          color=discord.Color.purple(),
      )
      airdrop_embed.set_footer(
          text="Opex Wardogs & Squad • Drop Aléatoire", icon_url=server_icon
      )

      view = AirdropView(
          reward_amount=5,
          server_icon_url=server_icon,
          vote_channel_id=VOTE_CHANNEL_ID,
      )
      await message.channel.send(embed=airdrop_embed, view=view)


client.run(TOKEN)
