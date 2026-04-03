import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

ROLE_ID_REGISTRO = int(os.getenv("ROLE_ID_REGISTRO", "1446978721822150706"))


class RegistroModal(discord.ui.Modal, title="Registro de Membro"):
    nome = discord.ui.TextInput(
        label="Nome",
        placeholder="Digite seu nome",
        style=discord.TextStyle.short,
        required=True,
    )
    user_id = discord.ui.TextInput(
        label="ID",
        placeholder="Digite seu ID",
        style=discord.TextStyle.short,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        novo_nick = f"「 {self.user_id.value} 」 {self.nome.value}"
        cargo = interaction.guild.get_role(ROLE_ID_REGISTRO) if interaction.guild else None

        try:
            await interaction.user.edit(nick=novo_nick)

            if cargo is not None:
                await interaction.user.add_roles(cargo, reason="Registro concluido pelo painel")

            await interaction.response.send_message(
                f"Registro concluido! Seu nome foi alterado para **{novo_nick}**.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Nao consegui concluir o registro. Verifique minhas permissoes para alterar apelidos e cargos.",
                ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "Ocorreu um erro ao aplicar seu registro. Tente novamente em instantes.",
                ephemeral=True,
            )


class RegistroView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Registrar",
        style=discord.ButtonStyle.primary,
        custom_id="btn_registrar_unico",
    )
    async def registrar_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(RegistroModal())


class Registro(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.view = RegistroView()

    async def cog_load(self) -> None:
        self.bot.add_view(self.view)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def painel(self, ctx: commands.Context) -> None:
        embed = discord.Embed(
            title="Painel de Registro",
            description="Clique no botao abaixo para concluir seu registro.",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed, view=self.view)
        await ctx.message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Registro(bot))
