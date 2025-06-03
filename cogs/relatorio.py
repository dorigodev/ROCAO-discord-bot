import asyncio
import datetime
import discord
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import pytz
import json
import re

load_dotenv()

sao_paulo_now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone('America/Sao_Paulo'))

ID_CATEGORY_RELATORIOS = int(os.getenv('ID_CATEGORY_RELATORIOS'))
ID_CHANNEL_LOG_RELATORIOS = int(os.getenv('ID_CHANNEL_LOG_RELATORIOS'))
ID_CHANNEL_LOG_ERROR = int(os.getenv('ID_CHANNEL_LOG_ERROR'))

try:
    with open('questions.json', 'r', encoding='utf-8') as f:
        QUESTIONS = json.load(f)
    print("Perguntas carregadas com sucesso de questions.json")
except FileNotFoundError:
    print("Erro: O arquivo questions.json não foi encontrado. Certifique-se de que ele está na mesma pasta do bot.")
    QUESTIONS = [] # lista vazia para evitar erros
except json.JSONDecodeError:
    print("Erro: O arquivo questions.json está mal formatado. Verifique a sintaxe JSON.")
    QUESTIONS = [] # lista vazia para evitar erros

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
    @app_commands.describe(member="O membro para o qual você deseja criar o relatório.",
    piloto="Um nome personalizado para o relatório, se o membro não for do Discord (opcional).")
    async def criar_relatorio(self, interaction: discord.Interaction, member: discord.Member = None, piloto: str = None ):

        if member:
            target_name = member.display_name
        elif piloto:
            target_name = piloto
        else:
            await interaction.followup.send(
                "Você deve especificar um `member` ou um `piloto` para criar o relatório.",
                ephemeral=True
            )
            return

        if interaction.user.id in self.active_reports:
            current_channel_id = self.active_reports[interaction.user.id]
            current_channel = interaction.guild.get_channel(current_channel_id)
            if current_channel:
                await interaction.response.send_message(
                    f"Você já tem um relatório em andamento no canal {current_channel.mention}. Por favor, aguarde a conclusão do atual.",
                    ephemeral=True
                )
            else:
                del self.active_reports[interaction.user.id]
                await interaction.response.send_message(
                    "Um relatório anterior não foi encontrado. Iniciando um novo...",
                    ephemeral=True
                )
                await self._create_and_start_report(interaction, target_name)
            return

        await self._create_and_start_report(interaction, target_name)

    async def _create_and_start_report(self, interaction: discord.Interaction, target_name: str):
        try:
            relatorio_category = discord.utils.get(interaction.guild.categories, id=ID_CATEGORY_RELATORIOS)
            if not relatorio_category:
                await interaction.response.send_message("A categoria de relatórios não foi encontrada. Verifique o ID configurado.", ephemeral=True)
                return

            relatorio_channel = await interaction.guild.create_text_channel(
                name=f"relatorio-{target_name.lower().replace(' ', '-')}-{sao_paulo_now.strftime('%Y%m%d%H%M%S')}",
                category=relatorio_category,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    self.bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True)
                }
            )
        except discord.Forbidden:
            await interaction.response.send_message("Não tenho permissão para criar canais. Verifique minhas permissões no servidor e na categoria de relatórios.", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao criar o canal do relatório: {e}", ephemeral=True)
            print(f"Erro ao criar o canal do relatório: {e}")
            return

        self.active_reports[interaction.user.id] = relatorio_channel.id

        await interaction.response.send_message(f"Canal de relatório criado: {relatorio_channel.mention}", ephemeral=True)
        await self.start_questions(relatorio_channel, target_name, interaction)

    async def start_questions(self, channel: discord.TextChannel, target_name: str, interaction: discord.Interaction):
        channel_error_log = discord.utils.get(channel.guild.channels, id=ID_CHANNEL_LOG_ERROR)

        responses = {}

        await channel.send(f"Olá {interaction.user.mention}! Este é o canal do seu relatório sobre **{target_name}**. Por favor, responda às perguntas abaixo.")

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
                        option_index = int(view.response.split('_')[1])
                        selected_option = q_data["options"][option_index]
                        responses[f"Q{i+1}"] = selected_option
                        await channel.send(f"✅ Sua resposta: **{selected_option}** foi registrada!")
                else:
                    responses[f"Q{i+1}"] = "Nenhuma resposta fornecida (botão não clicado)."

            elif q_data["type"] == "descriptive":
                def check(m):
                    return m.author == interaction.user and m.channel == channel
                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=600.0)
                    responses[f"Q{i+1}"] = msg.content
                    await channel.send("✅ Sua resposta foi registrada!", delete_after=5)
                    await channel.purge(limit=10)
                except asyncio.TimeoutError:
                    responses[f"Q{i+1}"] = "Tempo esgotado para esta pergunta descritiva."
                    await channel.send("Tempo esgotado para esta pergunta.", delete_after=5)

            await asyncio.sleep(0.5)

        try:
            await channel.purge(limit=100)
        except discord.Forbidden:
            print(f"Não pude limpar o chat final. Verifique as permissões.")
        except Exception as e:
            await channel_error_log.send(f"Erro no: {channel.name}, Data: {sao_paulo_now}: {e}")
            print(f"Erro ao limpar o chat final: {e}")
        await channel.send("Todas as perguntas foram respondidas. Compilando o relatório...", delete_after=5)


        embed = discord.Embed(
            title=f"📋 Relatório de Avaliação do Piloto",
            description=f"**Piloto Avaliado:** {target_name}\n"
                        f"**Relatório Feito Por:** {interaction.user.display_name}\n"
                        f"**Data/Hora:** {sao_paulo_now.strftime('%d/%m/%Y %H:%M:%S')}",
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
                await channel_error_log.send(f"Error no: {channel.name} Não tenho permissão para enviar mensagens no canal de log. O relatório foi concluído, mas não salvo no log.")
                print(f"Não tenho permissão para enviar mensagens no canal de log ({ID_CHANNEL_LOG_RELATORIOS}).")
            except Exception as e:
                await channel.send(f"Ocorreu um erro ao enviar o relatório para o canal de log: {e}, por favor, aguarde", delete_after=15)
                await channel_error_log.send(f"Erro no: {channel.name}, Data: {sao_paulo_now}: Ocorreu um erro ao enviar o relatório para o canal de log: {e}")
                filename = ""
                try:
                    sanitized_target_name = re.sub(r'[^\w\s-]', '', target_name).replace(' ', '_')
                    filename = f"{sanitized_target_name}_{datetime.date.today().strftime('%Y%m%d')}.txt"
                    with open(filename, "w", encoding='utf-8') as file:
                        file.write("📋 Relatório de Avaliação do Piloto \n")
                        file.write(f"Piloto Avaliado:{target_name}  \n")
                        file.write(f"Relatório Feito Por: {interaction.user.display_name}  \n")
                        for i, q_data in enumerate(QUESTIONS):
                            try:
                                question_text = q_data.get('question', 'Pergunta Desconhecida')
                                answer_text = responses.get(f'Q{i+1}', 'N/A')
                                file.write(f"Pergunta: {question_text}\n")
                                file.write(f"Resposta: {answer_text}\n\n")
                            except Exception as loop_e:
                                print(f"Erro ao processar a pergunta {i+1} para o arquivo TXT: {loop_e}. Dados da pergunta: {q_data}")
                                file.write(f" ERRO: Não foi possível processar a Pergunta {i+1} devido a: {loop_e}\n\n")
                    await channel.send("Enviando arquivo em txt para canal de Log!")
                    if channel_log:
                        await channel_log.send(f"Relatorio de {target_name} feito por {interaction.user.display_name} apresentou erro, enviando em formato TXT.")
                        await channel_log.send(file=discord.File(filename))
                    elif channel_error_log:
                        await channel_error_log.send(f"Relatorio de {target_name} feito por {interaction.user.display_name} apresentou erro, enviando em formato TXT (via canal de erro).", file=discord.File(filename))
                    else:
                        print("Erro: Nenhum canal de log disponível para enviar o arquivo TXT de fallback.")
                except Exception as file_process_error:
                    await channel_error_log.send(f"Ocorreu um erro CRÍTICO ao tentar salvar/enviar o relatório em arquivo: {file_process_error}")
                    print(f"Erro CRÍTICO ao salvar/enviar relatório em arquivo: {file_process_error}")
                finally:
                    if os.path.exists(filename):
                        os.remove(filename)
        else:
            await channel.send("O canal de log de relatórios não foi encontrado. O relatório foi concluído, mas não salvo no log.")
            await channel_error_log.send(f"Erro no: {channel.name}, Data: {sao_paulo_now}: O canal de log de relatórios não foi encontrado. O relatório foi concluído, mas não salvo no log.")
            print(f"Canal de log de relatórios não encontrado com ID: {ID_CHANNEL_LOG_RELATORIOS}")


        await channel.send("🎉 Relatório concluído! Este canal será excluído em breve.")
        if interaction.user.id in self.active_reports:
            del self.active_reports[interaction.user.id]

        await asyncio.sleep(10) # Espera 10 segundos antes de deletar o canal
        try:
            await channel.delete()
        except discord.Forbidden:
            print(f"Não tenho permissão para deletar o canal {channel.name}. Deletar manualmente.")
            await channel_error_log.send(f"Não tenho permissão para deletar o canal {channel.name}. Deletar manualmente.")
        except Exception as e:
            await channel_error_log.send(f"Error ao deletar o canal: {channel.name}: {e}.")
            print(f"Erro ao deletar o canal {channel.name}: {e}")

    @app_commands.command(name="remove_active_reports", description="Remove id dos relatorios ativos.")
    @app_commands.describe(member="id do discord da pessoa")
    async def remove_active_report(self, interaction: discord.Interaction, member: int):
        await interaction.response.defer()
        if interaction.user.guild_permissions.administrator:
            if member in self.active_reports:
                del self.active_reports[member]
                await interaction.followup.send("Nome removido dos relatorios ativos.")
            else:
                await interaction.followup.send("Nenhum relatorio ativo.")
        else:
            await interaction.followup.send("Somente uma Administrador pode retirar você dos relatórios ativos.")

async def setup(bot):
    await bot.add_cog(Relatorio(bot))
    try:
        await bot.tree.sync()
        print(f"Comandos de barra sincronizados para o cog {Relatorio.__name__}.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos de barra: {e}")