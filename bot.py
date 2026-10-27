import os
import threading
from flask import Flask
import discord

app = Flask('')

@app.route('/')
def home():
    return "Bot Discord actif !"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Bot connecté sous l'identité : {client.user}")

@client.event
async def on_message(message):
    # CECI S'AFFICHERA QUEL QUE SOIT LE SALON
    print(f"[TEST GLOBAL] Message de {message.author} dans le salon {message.channel.id} : {message.content}")

    if message.author == client.user or message.channel.id != CHANNEL_ID:
        return

    content = message.content.strip()
    voter_name = None

    if "vient de voter pour le serveur" in content.lower():
        parts = content.split(" vient de voter")
        if parts:
            voter_name = parts[0].strip()

    if voter_name:
        guild = message.guild
        member = None
        for m in guild.members:
            if m.name.lower() == voter_name.lower() or m.display_name.lower() == voter_name.lower():
                member = m
                break

        if member:
            await message.channel.send(f"/add-money user:<@{member.id}> amount:1")
            print(f"[Succès] 1 point crédité à {member.name}")
        else:
            print(f"[Erreur] Membre non trouvé pour : {voter_name}")

client.run(TOKEN)
