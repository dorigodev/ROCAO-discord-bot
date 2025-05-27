import discord
from discord import app_commands
from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command()
    async def aboutme(self, interact: discord.Interaction):
        embed = discord.Embed(
            title=f'Olá {interact.user.display_name}, eu sou o ROCÃO!',
            description='Posso ajudar você em assuntos internos relacionados a ROCAM'
        )
        embed.set_thumbnail(url='https://cdn.discordapp.com/attachments/1195135499455697068/1303085014321201162/logo_rocam.png?ex=6836c13d&is=68356fbd&hm=1f6c7f477464beff82dc8e2c3a1681ce200c04ebf3b1bc0dc9315bb45880cd79&')
        embed.set_footer(
            text='bot desenvolvido por dorigo.dev, para contato digite /suporte',
            icon_url='https://avatars.githubusercontent.com/u/98785845?v=4'
        )
        await interact.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
