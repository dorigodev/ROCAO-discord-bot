import asyncio
import datetime
import discord
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

ID_CATEGORY_RELATORIOS = int(os.getenv('ID_CATEGORY_RELATORIOS'))
ID_CHANNEL_LOG_RELATORIOS = int(os.getenv('ID_CHANNEL_LOG_RELATORIOS'))

QUESTIONS = [
    {
        "type": "multiple_choice",
        "question": "De uma nota para o Dirigibilidade",
        "options": ["Péssimo ", "Ruim ", "Mediano ", "Bom", "Excelente"]
    },

    {
        "type": "descriptive",
        "question": "Descreva o motivo da nota para a Dirigibilidade."
    },
    {
        "type": "multiple_choice",
        "question": "De uma nota para o Modulação",
        "options": ["Péssimo ", "Ruim ", "Mediano ", "Bom", "Excelente"]
    },

    {
        "type": "descriptive",
        "question": "Descreva o motivo da nota para a Modulação."
    },


]

class QuestionView(discord.ui.View):
    def __init__(self, question_data, reporter_id, timeout=180):
        super().__init__(timeout=timeout)
        self.question_data = question_data
        self.reporter_id = reporter_id
        self.question_message = question_data["question"]
        self.response = None

        for i, option in enumerate(question_data["options"]):
            button = discord.ui.Button(label=option, custom_id=f"option_{i}")
            button.callback = self.button_callback
            self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.reporter_id:
            await interaction.response.send_message("Apenas quem iniciou o relatório pode responder a esta pergunta.", ephemeral=True)
            return

        self.response = interaction.data["custom_id"]
        await interaction.response.send_message("Sua resposta foi registrada!", ephemeral=True, delete_after=5)
        self.stop()

    async def on_timeout(self):
        self.response = "TIMEOUT"
        self.stop()


class Relatorio(commands.Cog,):
    def __init__(self, bot):
        self.bot = bot
        self.active_reports = {}

    @app_commands.command(name="criar_relatorio", description="Cria um relatorio de um membro especifico da ROCAM")
    @app_commands.describe(member="O membro para o qual você deseja criar o relatório.")
    async def criar_relatorio(self, interaction: discord.Interaction, member: discord.Member):
            relatorio_category = discord.utils.get(interaction.guild.categories,
                                                   id=ID_CATEGORY_RELATORIOS)
            relatorio_channel = await interaction.guild.create_text_channel(name=f"relatorio {member.nick} - {datetime.datetime.now()}",
                                                                            category=relatorio_category,
                                                                            overwrites={
                                                                                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                                                                                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                                                            })

            if interaction.user.id in self.active_reports:
                await interaction.response.send_message(f"Já existe um relatório em andamento para {interaction.user.display_name}. Por favor, aguarde a conclusão do atual.", ephemeral=True)
                return

            await interaction.response.send_message(relatorio_channel.mention,
                                                    ephemeral = True)
            await self.start_questions(relatorio_channel, member, interaction=interaction)

    async def start_questions(self, channel: discord.TextChannel, member: discord.Member, interaction: discord.Interaction):
        responses = {}

        self.active_reports[member.id] = channel.id

        await channel.send(f"Olá {interaction.user.mention}! Este é o canal do seu relatório sobre o Piloto {member.nick}. Por favor, responda às perguntas abaixo.")

        for i, q_data in enumerate(QUESTIONS):
            question_text = f"**Pergunta:** {q_data['question']}"
            question_message = await channel.send(question_text)

            if q_data["type"] == "multiple_choice":
                view = QuestionView(q_data, reporter_id=interaction.user.id)
                await question_message.edit(view=view)
                await view.wait()

                if view.response:
                    if view.response == "TIMEOUT":
                        responses[f"Q{i+1}"] = "Tempo esgotado para esta pergunta."
                        await channel.send("Tempo esgotado para esta pergunta.", delete_after=5)
                    else:
                        await channel.send("Resposta registrada com sucesso!", delete_after=5)
                        option_index = int(view.response.split('_')[1])
                        selected_option = q_data["options"][option_index]
                        responses[f"Q{i+1}"] = selected_option
                else:
                    responses[f"Q{i+1}"] = "Nenhuma resposta fornecida (botão não clicado)."

            elif q_data["type"] == "descriptive":
                def check(m):
                    return m.author == interaction.user and m.channel == channel
                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=600.0)
                    responses[f"Q{i+1}"] = msg.content
                    await channel.send("Resposta registrada com sucesso!", delete_after=5)
                    await channel.purge(limit=100)
                except asyncio.TimeoutError:
                    responses[f"Q{i+1}"] = "Tempo esgotado para esta pergunta descritiva."
                    await channel.send("Tempo esgotado para esta pergunta.", delete_after=5)

            await asyncio.sleep(0.5)

        try:
            await channel.purge(limit=100)
        except discord.Forbidden:
            print(f"Não pude limpar o chat final. Verifique as permissões.")
        except Exception as e:
            print(f"Erro ao limpar o chat final: {e}")
        await channel.send("Todas as perguntas foram respondidas. Compilando o relatório...", delete_after=5)


        embed = discord.Embed(
            title=f"📋 Relatório de Avaliação do Piloto",
            description=f"**Piloto Avaliado:**{member.display_name}\n"
                        f"**Relatório Feito Por:** {interaction.user.display_name}\n"
                        f"**Data/Hora:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            color=discord.Color.blue()
        )

        for i, q_data in enumerate(QUESTIONS):
            question_text = q_data['question']
            answer_text = responses.get(f'Q{i+1}', 'N/A')
            embed.add_field(name=f"❓ Pergunta:"
                                 f" {question_text}" ,
                            value=f"✅ Resposta: {answer_text}", inline=False)



        channel_log = discord.utils.get(channel.guild.channels, id=ID_CHANNEL_LOG_RELATORIOS)
        if channel_log:
            try:
                await channel_log.send(embed=embed)
            except discord.Forbidden:
                await channel.send("Não tenho permissão para enviar mensagens no canal de log. O relatório foi concluído, mas não salvo no log.", delete_after=15)
                print(f"Não tenho permissão para enviar mensagens no canal de log ({ID_CHANNEL_LOG_RELATORIOS}).")
            except Exception as e:
                await channel.send(f"Ocorreu um erro ao enviar o relatório para o canal de log: {e}", delete_after=15)
                print(f"Erro ao enviar o relatório para o canal de log: {e}")
        else:
            await channel.send("O canal de log de relatórios não foi encontrado. O relatório foi concluído, mas não salvo no log.", delete_after=15)
            print(f"Canal de log de relatórios não encontrado com ID: {ID_CHANNEL_LOG_RELATORIOS}")


        await channel.send("🎉 Relatório concluído! Este canal será excluído em breve.")
        if interaction.user.id in self.active_reports:
            del self.active_reports[interaction.user.id]

        await asyncio.sleep(10) # Espera 10 segundos antes de deletar o canal
        try:
            await channel.delete()
        except discord.Forbidden:
            print(f"Não tenho permissão para deletar o canal {channel.name}. Deletar manualmente.")
        except Exception as e:
            print(f"Erro ao deletar o canal {channel.name}: {e}")


async def setup(bot):
    await bot.add_cog(Relatorio(bot))
    try:
        await bot.tree.sync()
        print(f"Comandos de barra sincronizados para o cog {Relatorio.__name__}.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos de barra: {e}")