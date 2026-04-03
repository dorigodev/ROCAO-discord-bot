import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()


class RocaoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        for filename in os.listdir('cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')

        await self.tree.sync()


bot = RocaoBot()


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.command()
async def falar(ctx: commands.Context, *, frase: str):
    await ctx.send(frase)

bot.run(TOKEN)
