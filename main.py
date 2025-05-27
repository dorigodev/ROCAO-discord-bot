import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='!',intents=intents)

async def load_cogs():
 for filename in os.listdir('cogs'):
  if filename.endswith('.py'):
    await bot.load_extension(f'cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    await load_cogs()
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')

@bot.command()
async def falar(ctx: commands.Context, *, frase: str):
    await ctx.send(frase)

bot.run(TOKEN)
