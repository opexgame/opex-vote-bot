import os
import re
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

# Lancement du serveur Web dans un thread séparé
threading.Thread(target=run_flask, daemon=True).start()

# --- 2. Logique du Bot Discord ---
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Bot connecté sous l'identité : {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    user_id = None

    # Recherche d'une mention dans le texte brut
    match = re.search(r"<@!?(\d+)>", message.content)
    if match:
        user_id = match.group(1)

    # Recherche dans les Embeds (webhook)
    if not user_id and message.embeds:
        for embed in message.embeds:
            search_text = f"{embed.title or ''} {embed.description or ''}"
            for field in embed.fields:
                search_text += f" {field.name} {field.value}"
            
            match = re.search(r"<@!?(\d+)>", search_text)
            if match:
                user_id = match.group(1)
                break

    # Exécution de la commande UnbelievaBoat
    if user_id:
        await message.channel.send(f"/add-money user:<@{user_id}> amount:1")
        print(f"[Succès] 1 point crédité à l'utilisateur ID : {user_id}")

client.run(TOKEN)
