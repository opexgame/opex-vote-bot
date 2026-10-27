import os
import threading
from flask import Flask
import discord

# --- 1. Petit serveur Web pour satisfaire Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord actif !"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- 2. Logique du Bot Discord ---
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Indispensable pour chercher les membres par leur nom
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Bot connecté sous l'identité : {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    voter_name = None

    # Analyse du texte brut (ex: "Max vient de voter pour le server !")
    content = message.content
    if "vient de voter pour le server" in content:
        # On extrait le premier mot qui correspond au pseudo
        parts = content.split(" vient de voter")
        if parts:
            voter_name = parts[0].strip()

    # Si on a trouvé un pseudo, on cherche le membre correspondant sur le serveur
    if voter_name:
        guild = message.guild
        member = discord.utils.get(guild.members, name=voter_name)
        
        # Si on ne le trouve pas par son pseudo exact, on cherche par son pseudo affiché (display_name)
        if not member:
            for m in guild.members:
                if m.display_name.lower() == voter_name.lower() or m.name.lower() == voter_name.lower():
                    member = m
                    break

        if member:
            await message.channel.send(f"/add-money user:<@{member.id}> amount:1")
            print(f"[Succès] 1 point crédité à {member.name} (ID : {member.id})")
        else:
            print(f"[Erreur] Impossible de trouver le membre correspondant au nom : {voter_name}")

client.run(TOKEN)
