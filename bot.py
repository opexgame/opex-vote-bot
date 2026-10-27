import os
import re
import discord

# Récupération sécurisée des paramètres
TOKEN = os.getenv("DISCORD_TOKEN")
# Remplace 123456789012345678 par l'ID réel de ton salon #vote-serveur
CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "1558847340738252810"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Bot connecté sous l'identité : {client.user}")

@client.event
async def on_message(message):
    # On filtre : salon spécifique uniquement + ignorer les messages du bot lui-même
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    user_id = None

    # 1. Recherche d'une mention dans le texte brut du message (<@12345678>)
    match = re.search(r"<@!?(\d+)>", message.content)
    if match:
        user_id = match.group(1)

    # 2. Si pas de mention dans le texte, recherche dans les Embeds (notifications de Webhook)
    if not user_id and message.embeds:
        for embed in message.embeds:
            search_text = f"{embed.title or ''} {embed.description or ''}"
            for field in embed.fields:
                search_text += f" {field.name} {field.value}"
            
            match = re.search(r"<@!?(\d+)>", search_text)
            if match:
                user_id = match.group(1)
                break

    # 3. Exécution de la commande d'ajout de point via UnbelievaBoat
    if user_id:
        await message.channel.send(f"/add-money user:<@{user_id}> amount:1")
        print(f"[Succès] 1 point crédité à l'utilisateur ID : {user_id}")

client.run(TOKEN)