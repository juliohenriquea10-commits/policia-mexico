import asyncio
import re

import discord
from discord.ext import commands

TOKEN = "COLOQUE_O_TOKEN_AQUI"
PREFIX = "!"

# ============================================================
# 📌 CANAIS FIXOS DA CENTRAL DA POLÍCIA
# ============================================================

CATEGORIA_LOGS_ID = 1547844380038271078

# 📊 Logs normais
CANAL_LOGS_NORMAIS_ID = 1547856984001355786

# 🔐 Logs de segurança
CANAL_LOGS_SEGURANCA_ID = 1547857646692868118

# 👤 Registro automático de entrada e saída
CANAL_MEMBROS_ENTRARAM_ID = 1547682921509298266
CANAL_MEMBROS_SAIRAM_ID = 1547843850427441193

# 📋 Registro de advertências
CANAL_ADVERTENCIAS_ID = 1547682940870201446

# 🎙️ Call em que o bot deve permanecer enquanto estiver online.
CANAL_VOZ_FIXO_ID = 1553671143192264745

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


async def conectar_call_fixa():
    """Conecta o bot à call configurada assim que ele fica online."""
    canal = bot.get_channel(CANAL_VOZ_FIXO_ID)

    if not isinstance(canal, (discord.VoiceChannel, discord.StageChannel)):
        print(f"❌ Call fixa não encontrada ou não é um canal de voz: {CANAL_VOZ_FIXO_ID}")
        return

    try:
        voice_client = canal.guild.voice_client
        if voice_client and voice_client.is_connected():
            if voice_client.channel and voice_client.channel.id == CANAL_VOZ_FIXO_ID:
                return
            await voice_client.move_to(canal)
        else:
            if voice_client:
                await voice_client.disconnect(force=True)
            await canal.connect(reconnect=True, self_deaf=True)
        print(f"🎙️ Bot conectado à call fixa: {canal.name}")
    except (discord.ClientException, discord.Forbidden, discord.HTTPException, OSError) as erro:
        print(f"❌ Não consegui entrar na call fixa ({CANAL_VOZ_FIXO_ID}): {erro}")


@bot.event
async def on_connect():
    await bot.wait_until_ready()
    await conectar_call_fixa()


def pode_criar_embed(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or member.guild_permissions.manage_messages


async def apagar_paineis_antigos(canal: discord.TextChannel, titulo: str, limite: int = 100):
    if bot.user is None:
        return
    try:
        async for mensagem in canal.history(limit=limite):
            if mensagem.author.id != bot.user.id:
                continue
            if any(embed.title == titulo for embed in mensagem.embeds):
                try:
                    await mensagem.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
    except (discord.Forbidden, discord.HTTPException):
        pass


def obter_canal(guild: discord.Guild, canal_id: int):
    canal = guild.get_channel(canal_id)
    return canal if isinstance(canal, discord.TextChannel) else None


def texto_usuario(usuario) -> str:
    return f"{usuario.mention} (`{usuario.id}`)"


def avatar_url(usuario):
    try:
        return usuario.display_avatar.url
    except Exception:
        return None


async def enviar_embed(canal: discord.TextChannel, embed: discord.Embed):
    if canal is None:
        return
    try:
        await canal.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def buscar_executor(guild: discord.Guild, action, target_id=None):
    """Busca no Registro de Auditoria quem executou uma ação administrativa."""
    try:
        await asyncio.sleep(0.8)
        async for entry in guild.audit_logs(limit=8, action=action):
            if target_id is None:
                return entry.user
            alvo = getattr(entry.target, "id", None)
            if alvo == target_id:
                return entry.user
    except (discord.Forbidden, discord.HTTPException):
        return None
    return None


def executor_texto(executor) -> str:
    if isinstance(executor, discord.Member):
        return executor.mention
    return str(executor) if executor else "Não identificado"


async def enviar_log_normal(guild: discord.Guild, titulo: str, descricao: str,
                            cor=discord.Color.blurple(), campos=None, usuario=None):
    canal = obter_canal(guild, CANAL_LOGS_NORMAIS_ID)
    if canal is None:
        return

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=discord.utils.utcnow()
    )
    if campos:
        for nome, valor, inline in campos:
            embed.add_field(name=nome, value=valor, inline=inline)
    if usuario:
        url = avatar_url(usuario)
        if url:
            embed.set_thumbnail(url=url)
    embed.set_footer(text="Central da Polícia • Logs")
    await enviar_embed(canal, embed)


async def enviar_log_seguranca(guild: discord.Guild, titulo: str, descricao: str,
                               cor=discord.Color.red(), campos=None, usuario=None):
    canal = obter_canal(guild, CANAL_LOGS_SEGURANCA_ID)
    if canal is None:
        return

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=discord.utils.utcnow()
    )
    if campos:
        for nome, valor, inline in campos:
            embed.add_field(name=nome, value=valor, inline=inline)
    if usuario:
        url = avatar_url(usuario)
        if url:
            embed.set_thumbnail(url=url)
    embed.set_footer(text="Central da Polícia • Logs de Segurança")
    await enviar_embed(canal, embed)


async def registrar_entrada(member: discord.Member):
    canal = obter_canal(member.guild, CANAL_MEMBROS_ENTRARAM_ID)
    if canal is None:
        return

    agora = discord.utils.utcnow()
    total = member.guild.member_count or len(member.guild.members)

    embed = discord.Embed(
        title="🟢 Novo membro entrou!",
        description=(
            f"**Nome do membro:**\n"
            f"{member.mention}\n"
            f"`{member.id}`\n\n"
            f"**Total de membros:** `{total}`"
        ),
        color=discord.Color.green(),
        timestamp=agora
    )
    url = avatar_url(member)
    if url:
        embed.set_thumbnail(url=url)
    embed.set_footer(
        text=f"🇲🇽 • Central da Polícia | Hoje às {agora.astimezone().strftime('%H:%M')}"
    )
    await enviar_embed(canal, embed)


async def registrar_saida(member: discord.Member):
    canal = obter_canal(member.guild, CANAL_MEMBROS_SAIRAM_ID)
    if canal is None:
        return

    agora = discord.utils.utcnow()
    total = member.guild.member_count or max(len(member.guild.members) - 1, 0)

    embed = discord.Embed(
        title="🔴 Membro saiu!",
        description=(
            f"**Nome do membro:**\n"
            f"{member.mention}\n"
            f"`{member.id}`\n\n"
            f"**Total de membros:** `{total}`"
        ),
        color=discord.Color.red(),
        timestamp=agora
    )
    url = avatar_url(member)
    if url:
        embed.set_thumbnail(url=url)
    embed.set_footer(
        text=f"🇲🇽 • Central da Polícia | Hoje às {agora.astimezone().strftime('%H:%M')}"
    )
    await enviar_embed(canal, embed)


# ============================================================
# 🧩 CRIADOR DE EMBEDS
# ============================================================

class CriarEmbedModal(discord.ui.Modal, title="🧩 Criar Embed"):
    titulo = discord.ui.TextInput(
        label="Título",
        placeholder="Ex.: 📜 Regras da Polícia",
        required=False,
        max_length=256
    )
    descricao = discord.ui.TextInput(
        label="Descrição",
        placeholder="Digite o conteúdo...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )
    cor = discord.ui.TextInput(
        label="Cor (hexadecimal)",
        placeholder="Ex.: #1E90FF",
        required=False,
        max_length=7
    )
    rodape = discord.ui.TextInput(
        label="Rodapé",
        placeholder="Ex.: Central de Polícia",
        required=False,
        max_length=2048
    )
    imagem = discord.ui.TextInput(
        label="URL da imagem",
        placeholder="Cole a URL da imagem",
        required=False,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        cor_texto = self.cor.value.strip().replace("#", "")
        if cor_texto:
            try:
                if len(cor_texto) != 6:
                    raise ValueError
                cor_embed = discord.Color(int(cor_texto, 16))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Use a cor no formato `#RRGGBB`.", ephemeral=True
                )
                return
        else:
            cor_embed = discord.Color.blurple()

        embed = discord.Embed(
            title=self.titulo.value.strip() or None,
            description=self.descricao.value,
            color=cor_embed
        )

        if self.rodape.value.strip():
            embed.set_footer(text=self.rodape.value.strip())

        if self.imagem.value.strip():
            embed.set_image(url=self.imagem.value.strip())

        await interaction.response.send_message(
            "👀 **Pré-visualização:**",
            embed=embed,
            ephemeral=True,
            view=PublicarEmbedView(embed)
        )


class PublicarEmbedView(discord.ui.View):
    def __init__(self, embed):
        super().__init__(timeout=300)
        self.embed = embed

    @discord.ui.button(label="Publicar Embed", emoji="📤", style=discord.ButtonStyle.success)
    async def publicar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not pode_criar_embed(interaction.user):
            await interaction.response.send_message(
                "❌ Sem permissão para publicar Embeds.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📢 **Escolha o canal:**",
            ephemeral=True,
            view=EscolherCanalView(self.embed)
        )


class CanalSelect(discord.ui.ChannelSelect):
    def __init__(self, embed):
        self.embed = embed
        super().__init__(
            placeholder="📢 Selecione o canal",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selecionado = self.values[0]
        canal = interaction.guild.get_channel(selecionado.id) if interaction.guild else None

        if canal is None and interaction.guild:
            try:
                canal = await interaction.guild.fetch_channel(selecionado.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                canal = None

        if canal is None or getattr(canal, "type", None) != discord.ChannelType.text:
            await interaction.response.send_message(
                "❌ Não foi possível identificar esse canal como canal de texto. Tente selecionar novamente.",
                ephemeral=True
            )
            return

        try:
            await canal.send(embed=self.embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Não consigo enviar mensagens em {canal.mention}. Verifique as permissões do bot.",
                ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ O Discord recusou o envio.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Embed publicado em {canal.mention}!", ephemeral=True
        )


class EscolherCanalView(discord.ui.View):
    def __init__(self, embed):
        super().__init__(timeout=120)
        self.add_item(CanalSelect(embed))


class PainelEmbedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)

    @discord.ui.button(label="Criar Embed", emoji="🧩", style=discord.ButtonStyle.primary)
    async def criar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not pode_criar_embed(interaction.user):
            await interaction.response.send_message(
                "❌ Você precisa de **Administrador** ou **Gerenciar Mensagens**.",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(CriarEmbedModal())


@bot.command(name="embed")
@commands.guild_only()
async def embed_command(ctx):
    if not isinstance(ctx.author, discord.Member) or not pode_criar_embed(ctx.author):
        await ctx.reply("❌ Você não tem permissão para usar este comando.", mention_author=False)
        return

    # Apaga qualquer painel antigo do mesmo sistema neste canal antes de enviar o novo.
    await apagar_paineis_antigos(ctx.channel, "🧩 Criador de Embeds")

    embed = discord.Embed(
        title="🧩 Criador de Embeds",
        description="Clique no botão abaixo para criar um Embed personalizado.",
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Central de Polícia • Sistema de Embeds")
    await ctx.send(embed=embed, view=PainelEmbedView())
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


# ============================================================
# 📊 + 🔐 LOGS AUTOMÁTICOS
# ============================================================

# ============================================================
# 🛡️ ANTI-NUKE / PROTEÇÃO DA CENTRAL
# ============================================================
# Qualquer ação administrativa protegida feita por um membro
# (cargo/canal/permissão/nome/bot/ban/kick) faz o bot remover
# os cargos que ele conseguir remover do responsável.
#
# IMPORTANTE:
# - O próprio bot é ignorado para não se punir.
# - O Discord não permite que um bot remova @everyone, cargos
#   gerenciados por integrações ou cargos que estejam acima do
#   cargo mais alto do bot.
# - O bot precisa de "Ver Registro de Auditoria" e "Gerenciar Cargos".
# ============================================================

ANTI_NUKE_ATIVO = True
ANTI_NUKE_REMOVER_CARGOS = True

async def remover_todos_os_cargos(executor: discord.abc.User, guild: discord.Guild, motivo: str):
    """Remove do executor todos os cargos que o bot tem autoridade para remover."""
    if not ANTI_NUKE_ATIVO or not ANTI_NUKE_REMOVER_CARGOS:
        return False

    if executor is None or not isinstance(executor, discord.Member):
        return False

    # Nunca punir o próprio bot.
    if bot.user and executor.id == bot.user.id:
        return False

    # O bot precisa conseguir gerenciar cargos.
    me = guild.me
    if me is None or not me.guild_permissions.manage_roles:
        await enviar_log_seguranca(
            guild,
            "⚠️ Anti-Nuke sem permissão",
            "Detectei uma ação protegida, mas não consigo remover os cargos do responsável.",
            cor=discord.Color.dark_red(),
            campos=[
                ("👤 Responsável", executor_texto(executor), True),
                ("📋 Motivo", motivo[:1024], False),
                ("❗ Necessário", "Permissão **Gerenciar Cargos** e cargo do bot acima dos cargos a remover.", False),
            ],
            usuario=executor,
        )
        return False

    removidos = []
    impossiveis = []

    for role in list(executor.roles):
        if role.is_default() or role.managed:
            continue

        # O bot só pode mexer em cargos abaixo do seu cargo mais alto.
        if role >= me.top_role:
            impossiveis.append(role.name)
            continue

        try:
            await executor.remove_roles(
                role,
                reason=f"🛡️ Anti-Nuke: {motivo}"
            )
            removidos.append(role.name)
        except (discord.Forbidden, discord.HTTPException):
            impossiveis.append(role.name)

    campos = [
        ("👤 Responsável", executor_texto(executor), True),
        ("📋 Ação detectada", motivo[:1024], False),
        ("❌ Cargos removidos", str(len(removidos)), True),
    ]

    if removidos:
        lista = "\n".join(f"• `{nome}`" for nome in removidos)
        campos.append(("🧹 Cargos", lista[:1024], False))

    if impossiveis:
        lista = "\n".join(f"• `{nome}`" for nome in impossiveis)
        campos.append(("⚠️ Não foi possível remover", lista[:1024], False))

    await enviar_log_seguranca(
        guild,
        "🚨 ANTI-NUKE ATIVADO",
        f"{executor.mention} realizou uma ação protegida. Os cargos removíveis foram retirados.",
        cor=discord.Color.dark_red(),
        campos=campos,
        usuario=executor,
    )
    return bool(removidos)


async def punir_executor_por_acao(guild: discord.Guild, action, target_id: int, motivo: str):
    """Localiza o executor no Audit Log e aplica a punição Anti-Nuke."""
    executor = await buscar_executor(guild, action, target_id)

    if executor is None:
        await enviar_log_seguranca(
            guild,
            "⚠️ Ação protegida sem executor identificado",
            motivo,
            cor=discord.Color.orange(),
        )
        return None

    await remover_todos_os_cargos(executor, guild, motivo)
    return executor


async def buscar_executor_por_alvo_e_acoes(guild: discord.Guild, target_id: int, nomes_acoes: set, limite: int = 20):
    """Busca ações recentes do Audit Log quando a biblioteca não expõe uma ação específica."""
    try:
        await asyncio.sleep(0.8)
        async for entry in guild.audit_logs(limit=limite):
            alvo = getattr(entry.target, "id", None)
            nome_acao = getattr(getattr(entry, "action", None), "name", "")
            if alvo == target_id and nome_acao in nomes_acoes:
                return entry.user, nome_acao
    except (discord.Forbidden, discord.HTTPException):
        return None, None
    return None, None


# Não existe mais comando de configuração. Os canais acima são fixos.
# Assim que o bot fica online, os eventos já começam a ser registrados.

# Evita registros duplicados quando o Discord entrega o mesmo evento mais de uma vez
# ou quando há uma reinicialização muito rápida do bot.
_ULTIMOS_EVENTOS_MEMBROS = {}


def evento_membro_novo(guild_id: int, member_id: int, tipo: str, janela: float = 15.0) -> bool:
    agora = asyncio.get_running_loop().time()
    chave = (guild_id, member_id, tipo)
    ultimo = _ULTIMOS_EVENTOS_MEMBROS.get(chave, 0.0)
    if agora - ultimo < janela:
        return False
    _ULTIMOS_EVENTOS_MEMBROS[chave] = agora

    # Limpeza simples do cache para não crescer indefinidamente.
    if len(_ULTIMOS_EVENTOS_MEMBROS) > 1000:
        limite = agora - 60.0
        for k, v in list(_ULTIMOS_EVENTOS_MEMBROS.items()):
            if v < limite:
                _ULTIMOS_EVENTOS_MEMBROS.pop(k, None)
    return True


@bot.event
async def on_member_join(member: discord.Member):
    # Bot adicionado ao servidor: ação protegida.
    if member.bot:
        executor, nome_acao = await buscar_executor_por_alvo_e_acoes(
            member.guild,
            member.id,
            {"bot_add"}
        )
        if executor:
            await remover_todos_os_cargos(
                executor,
                member.guild,
                f"🤖 Adição do bot {member} (`{member.id}`)."
            )
            await enviar_log_seguranca(
                member.guild,
                "🤖 Bot adicionado",
                "Um bot foi adicionado ao servidor.",
                cor=discord.Color.red(),
                campos=[
                    ("🤖 Bot", f"{member.mention} (`{member.id}`)", True),
                    ("🛡️ Responsável", executor_texto(executor), True),
                ],
                usuario=member,
            )

    # Entrada é registrada UMA única vez e somente no canal de entradas.
    if not evento_membro_novo(member.guild.id, member.id, "entrada"):
        return
    await registrar_entrada(member)


@bot.event
async def on_member_remove(member: discord.Member):
    # Bot removido do servidor: ação protegida.
    if member.bot:
        executor, nome_acao = await buscar_executor_por_alvo_e_acoes(
            member.guild,
            member.id,
            {"bot_remove", "member_kick"}
        )
        if executor:
            await remover_todos_os_cargos(
                executor,
                member.guild,
                f"🤖 Remoção do bot {member} (`{member.id}`)."
            )
            await enviar_log_seguranca(
                member.guild,
                "🤖 Bot removido",
                "Um bot foi removido do servidor.",
                cor=discord.Color.red(),
                campos=[
                    ("🤖 Bot", f"{member} (`{member.id}`)", True),
                    ("🛡️ Responsável", executor_texto(executor), True),
                ],
                usuario=member,
            )

    # Evita duplicação de saída.
    if not evento_membro_novo(member.guild.id, member.id, "saida"):
        return

    # Primeiro verifica se a saída foi causada por expulsão.
    executor = await buscar_executor(member.guild, discord.AuditLogAction.kick, member.id)

    if executor:
        await remover_todos_os_cargos(
            executor,
            member.guild,
            f"🚫 Kick do membro {member} (`{member.id}`)."
        )
        await enviar_log_seguranca(
            member.guild,
            "👢 Membro expulso",
            f"{texto_usuario(member)} foi expulso do servidor.",
            cor=discord.Color.orange(),
            campos=[
                ("👤 Usuário", f"{member} (`{member.id}`)", True),
                ("🛡️ Responsável", executor_texto(executor), True),
            ],
            usuario=member,
        )
        return

    # Saída normal vai exclusivamente para o canal de membros que saíram.
    await registrar_saida(member)


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    executor = await punir_executor_por_acao(
        guild,
        discord.AuditLogAction.ban,
        user.id,
        f"🚫 Banimento do membro {user} (`{user.id}`)."
    )
    await enviar_log_seguranca(
        guild,
        "🔨 Membro banido",
        "Um membro foi banido do servidor.",
        cor=discord.Color.red(),
        campos=[
            ("👤 Usuário", f"{user.mention} (`{user.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ],
        usuario=user,
    )


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    executor = await buscar_executor(guild, discord.AuditLogAction.unban, user.id)
    await enviar_log_seguranca(
        guild,
        "♻️ Banimento removido",
        "O banimento de um usuário foi removido.",
        cor=discord.Color.green(),
        campos=[
            ("👤 Usuário", f"{user.mention} (`{user.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ],
        usuario=user,
    )


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles != after.roles:
        executor = await buscar_executor(
            after.guild, discord.AuditLogAction.member_role_update, after.id
        )
        adicionados = [r.mention for r in after.roles if r not in before.roles and r != after.guild.default_role]
        removidos = [r.mention for r in before.roles if r not in after.roles and r != before.guild.default_role]
        campos = [
            ("👤 Membro", f"{after.mention} (`{after.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ]
        if adicionados:
            campos.append(("➕ Cargos adicionados", " ".join(adicionados)[:1024], False))
        if removidos:
            campos.append(("➖ Cargos removidos", " ".join(removidos)[:1024], False))

        await enviar_log_seguranca(
            after.guild,
            "🏷️ Alteração de cargos",
            "Os cargos de um membro foram alterados.",
            cor=discord.Color.blue(),
            campos=campos,
            usuario=after,
        )

    if before.nick != after.nick:
        executor = await buscar_executor(
            after.guild, discord.AuditLogAction.member_update, after.id
        )
        await enviar_log_seguranca(
            after.guild,
            "✏️ Apelido alterado",
            "O apelido de um membro foi alterado.",
            cor=discord.Color.gold(),
            campos=[
                ("👤 Membro", f"{after.mention} (`{after.id}`)", True),
                ("🛡️ Responsável", executor_texto(executor), True),
                ("Antes", before.nick or "Sem apelido", True),
                ("Depois", after.nick or "Sem apelido", True),
            ],
            usuario=after,
        )

    # Timeout aplicado/removido.
    if before.timed_out_until != after.timed_out_until:
        executor = await buscar_executor(
            after.guild, discord.AuditLogAction.member_update, after.id
        )
        if after.timed_out_until:
            situacao = f"até {discord.utils.format_dt(after.timed_out_until, style='F')}"
            titulo = "⏱️ Timeout aplicado"
            cor = discord.Color.orange()
        else:
            situacao = "removido"
            titulo = "♻️ Timeout removido"
            cor = discord.Color.green()

        await enviar_log_seguranca(
            after.guild,
            titulo,
            f"O timeout de {after.mention} foi {situacao}.",
            cor=cor,
            campos=[
                ("👤 Membro", f"{after.mention} (`{after.id}`)", True),
                ("🛡️ Responsável", executor_texto(executor), True),
            ],
            usuario=after,
        )


@bot.event
async def on_message_delete(message: discord.Message):
    if message.guild is None or message.author.bot:
        return

    conteudo = message.content or "[sem texto]"
    if len(conteudo) > 1000:
        conteudo = conteudo[:997] + "..."

    await enviar_log_normal(
        message.guild,
        "🗑️ Mensagem excluída",
        f"Uma mensagem enviada por {message.author.mention} foi excluída.",
        cor=discord.Color.red(),
        campos=[
            ("👤 Autor", f"{message.author} (`{message.author.id}`)", True),
            ("📍 Canal", message.channel.mention, True),
            ("💬 Conteúdo", f"```{conteudo}```", False),
        ],
        usuario=message.author,
    )


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.guild is None or before.author.bot or before.content == after.content:
        return

    antes = before.content or "[sem texto]"
    depois = after.content or "[sem texto]"
    antes = (antes[:500] + "...") if len(antes) > 500 else antes
    depois = (depois[:500] + "...") if len(depois) > 500 else depois

    await enviar_log_normal(
        before.guild,
        "✏️ Mensagem editada",
        f"Uma mensagem de {before.author.mention} foi editada em {before.channel.mention}.",
        cor=discord.Color.gold(),
        campos=[
            ("👤 Autor", f"{before.author} (`{before.author.id}`)", True),
            ("📍 Canal", before.channel.mention, True),
            ("Antes", antes, False),
            ("Depois", depois, False),
        ],
        usuario=before.author,
    )


@bot.event
async def on_guild_role_create(role: discord.Role):
    executor = await buscar_executor(role.guild, discord.AuditLogAction.role_create, role.id)
    await enviar_log_seguranca(
        role.guild, "🆕 Cargo criado", "Um novo cargo foi criado no servidor.",
        cor=discord.Color.green(),
        campos=[
            ("🏷️ Cargo", f"{role.mention} (`{role.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ]
    )


@bot.event
async def on_guild_role_delete(role: discord.Role):
    executor = await punir_executor_por_acao(
        role.guild,
        discord.AuditLogAction.role_delete,
        role.id,
        f"🗑️ Exclusão do cargo `{role.name}` (`{role.id}`)."
    )
    await enviar_log_seguranca(
        role.guild, "🗑️ Cargo excluído", f"O cargo `{role.name}` foi excluído.",
        cor=discord.Color.red(),
        campos=[
            ("🆔 ID", f"`{role.id}`", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ]
    )


@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    mudancas = []
    if before.name != after.name:
        mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
    if before.permissions != after.permissions:
        mudancas.append("**Permissões:** alteradas")
    if before.position != after.position:
        mudancas.append("**Posição:** alterada")
    if before.color != after.color:
        mudancas.append("**Cor:** alterada")
    if not mudancas:
        return

    executor = await punir_executor_por_acao(
        after.guild,
        discord.AuditLogAction.role_update,
        after.id,
        f"✏️ Alteração do cargo `{after.name}` (`{after.id}`): " + ", ".join(mudancas)
    )
    await enviar_log_seguranca(
        after.guild, "⚙️ Cargo alterado", "Um cargo teve suas configurações modificadas.",
        cor=discord.Color.orange(),
        campos=[
            ("🏷️ Cargo", f"{after.mention} (`{after.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
            ("📋 Alterações", "\n".join(mudancas)[:1024], False),
        ]
    )


@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    executor = await buscar_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
    await enviar_log_seguranca(
        channel.guild, "🆕 Canal criado", "Um novo canal foi criado.",
        cor=discord.Color.green(),
        campos=[
            ("📌 Canal", f"{channel.mention} (`{channel.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ]
    )


@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    executor = await punir_executor_por_acao(
        channel.guild,
        discord.AuditLogAction.channel_delete,
        channel.id,
        f"🗑️ Exclusão do canal `{channel.name}` (`{channel.id}`)."
    )
    await enviar_log_seguranca(
        channel.guild, "🗑️ Canal excluído", f"O canal `{channel.name}` foi excluído.",
        cor=discord.Color.red(),
        campos=[
            ("🆔 ID", f"`{channel.id}`", True),
            ("🛡️ Responsável", executor_texto(executor), True),
        ]
    )


@bot.event
async def on_guild_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    mudancas = []
    if before.name != after.name:
        mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
    if getattr(before, "position", None) != getattr(after, "position", None):
        mudancas.append("**Posição:** alterada")
    if getattr(before, "overwrites", None) != getattr(after, "overwrites", None):
        mudancas.append("**Permissões:** alteradas")
    if hasattr(before, "topic") and before.topic != after.topic:
        mudancas.append("**Tópico:** alterado")
    if not mudancas:
        return

    executor = await punir_executor_por_acao(
        after.guild,
        discord.AuditLogAction.channel_update,
        after.id,
        f"⚙️ Alteração do canal `{after.name}` (`{after.id}`): " + ", ".join(mudancas)
    )
    await enviar_log_seguranca(
        after.guild, "⚙️ Canal alterado", "As configurações de um canal foram modificadas.",
        cor=discord.Color.orange(),
        campos=[
            ("📌 Canal", f"{after.mention} (`{after.id}`)", True),
            ("🛡️ Responsável", executor_texto(executor), True),
            ("📋 Alterações", "\n".join(mudancas)[:1024], False),
        ]
    )


@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    mudancas = []
    if before.name != after.name:
        mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
    if before.icon != after.icon:
        mudancas.append("**Ícone:** alterado")
    if before.banner != after.banner:
        mudancas.append("**Banner:** alterado")
    if not mudancas:
        return

    executor = await buscar_executor(after, discord.AuditLogAction.guild_update, after.id)
    await enviar_log_seguranca(
        after, "⚙️ Servidor alterado", "As configurações principais do servidor foram modificadas.",
        cor=discord.Color.orange(),
        campos=[
            ("🛡️ Responsável", executor_texto(executor), True),
            ("📋 Alterações", "\n".join(mudancas)[:1024], False),
        ]
    )



# ============================================================
# 🎫 SISTEMA DE TICKETS
# ============================================================
# Tudo fica configurado diretamente no código.
# Não é necessário usar !config ou qualquer comando para iniciar.

CANAL_ABRIR_TICKETS_ID = 1547683105387847774

# Cargo que pode assumir, gerenciar e finalizar tickets
CARGO_TICKET_NOME = "ticket"
CANAL_LOGS_TICKETS_ID = 1547683108692820040

# Categorias de tickets
CATEGORIA_DENUNCIA_ID = 1547861936538919043
CATEGORIA_CORREGEDORIA_ID = 1547682626511577088
CATEGORIA_SUPORTE_ID = 1547682630689095791
CATEGORIA_PROMOCAO_ID = 1547682635457761352
CATEGORIA_TRANSFERENCIA_ID = 1547682643083268116
CATEGORIA_EXONERACAO_ID = 1547682647470514317

# Emojis exatamente no padrão informado pelo usuário.
TIPOS_TICKET = {
    "denuncia": {
        "nome": "Denúncia",
        "emoji": "🚔",
        "categoria_id": CATEGORIA_DENUNCIA_ID,
        "cor": discord.Color.red(),
    },
    "corregedoria": {
        "nome": "Corregedoria",
        "emoji": "⏳",
        "categoria_id": CATEGORIA_CORREGEDORIA_ID,
        "cor": discord.Color.orange(),
    },
    "suporte": {
        "nome": "Suporte",
        "emoji": "🚨",
        "categoria_id": CATEGORIA_SUPORTE_ID,
        "cor": discord.Color.blue(),
    },
    "promocao": {
        "nome": "Promoção",
        "emoji": "🛩️",
        "categoria_id": CATEGORIA_PROMOCAO_ID,
        "cor": discord.Color.gold(),
    },
    "transferencia": {
        "nome": "Transferência",
        "emoji": "🚓",
        "categoria_id": CATEGORIA_TRANSFERENCIA_ID,
        "cor": discord.Color.blurple(),
    },
    "exoneracao": {
        "nome": "Exoneração",
        "emoji": "💀",
        "categoria_id": CATEGORIA_EXONERACAO_ID,
        "cor": discord.Color.dark_red(),
    },
}

TICKET_PREFIX = "ticket-"
PAINEL_TICKETS_TITULO = "📑 Central de Atendimento"
TICKET_MARKER = "ticket_owner="


def pode_gerenciar_ticket(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True

    cargo_ticket = discord.utils.find(
        lambda role: role.name.lower() == CARGO_TICKET_NOME.lower(),
        member.roles
    )
    return cargo_ticket is not None


def extrair_dono_ticket(canal: discord.TextChannel):
    topic = canal.topic or ""
    if TICKET_MARKER not in topic:
        return None
    try:
        parte = topic.split(TICKET_MARKER, 1)[1].split("|", 1)[0]
        return int(parte)
    except (ValueError, TypeError):
        return None


def encontrar_ticket_do_usuario(guild: discord.Guild, user_id: int):
    for canal in guild.text_channels:
        if extrair_dono_ticket(canal) == user_id:
            return canal
    return None


def categoria_ticket(guild: discord.Guild, categoria_id: int):
    categoria = guild.get_channel(categoria_id)
    return categoria if isinstance(categoria, discord.CategoryChannel) else None


async def apagar_painel_tickets_antigo(canal: discord.TextChannel):
    if bot.user is None:
        return
    try:
        async for mensagem in canal.history(limit=100):
            if mensagem.author.id != bot.user.id:
                continue
            if any(embed.title == PAINEL_TICKETS_TITULO for embed in mensagem.embeds):
                try:
                    await mensagem.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
    except (discord.Forbidden, discord.HTTPException):
        pass


async def enviar_log_ticket_fechado(guild: discord.Guild, canal: discord.TextChannel,
                                    tipo: dict, dono_id: int, fechador: discord.Member,
                                    consideracoes: str, transcript_texto: str):
    logs = obter_canal(guild, CANAL_LOGS_TICKETS_ID)
    if logs is None:
        return

    dono = guild.get_member(dono_id)
    dono_texto = dono.mention if dono else f"<@{dono_id}>"

    embed = discord.Embed(
        title="🔒 Ticket finalizado",
        description=(
            f"{tipo['emoji']} **{tipo['nome']}**\n\n"
            f"🎫 **Ticket:** `{canal.name}`\n"
            f"👤 **Solicitante:** {dono_texto}\n"
            f"🛡️ **Finalizado por:** {fechador.mention}\n\n"
            f"📝 **Considerações finais:**\n{consideracoes}"
        ),
        color=tipo["cor"],
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Central da Polícia • Logs de Tickets")

    arquivo = discord.File(
        fp=__import__("io").BytesIO(transcript_texto.encode("utf-8")),
        filename=f"{canal.name}-transcript.txt"
    )
    try:
        await logs.send(embed=embed, file=arquivo)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def gerar_transcript_ticket(canal: discord.TextChannel) -> str:
    linhas = [
        "=" * 70,
        "CENTRAL DA POLÍCIA • TRANSCRIPT DO TICKET",
        "=" * 70,
        f"Servidor: {canal.guild.name}",
        f"Canal: #{canal.name}",
        f"ID do canal: {canal.id}",
        f"Gerado em: {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M:%S UTC')}",
        "",
    ]

    try:
        async for mensagem in canal.history(limit=None, oldest_first=True):
            data = mensagem.created_at.strftime("%d/%m/%Y %H:%M:%S")
            linhas.append(f"[{data}] {mensagem.author} (ID: {mensagem.author.id})")
            linhas.append(mensagem.content or "[sem texto]")

            if mensagem.attachments:
                for anexo in mensagem.attachments:
                    linhas.append(f"📎 Anexo: {anexo.url}")

            if mensagem.embeds:
                for embed in mensagem.embeds:
                    if embed.title:
                        linhas.append(f"📋 Embed: {embed.title}")
                    if embed.description:
                        linhas.append(embed.description)

            linhas.append("-" * 70)
    except (discord.Forbidden, discord.HTTPException):
        linhas.append("[Não foi possível ler todas as mensagens do ticket.]")

    return "\n".join(linhas)


class FinalizarTicketModal(discord.ui.Modal, title="🔒 Finalizar Ticket"):
    consideracoes = discord.ui.TextInput(
        label="Considerações finais",
        placeholder="Ex.: Resolvido, inatividade, orientação realizada...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel) or extrair_dono_ticket(canal) is None:
            await interaction.response.send_message(
                "❌ Este canal não é um ticket válido.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member) or not pode_gerenciar_ticket(interaction.user):
            await interaction.response.send_message(
                "❌ Apenas a equipe autorizada pode finalizar o ticket.",
                ephemeral=True
            )
            return

        tipo = next(
            (item for item in TIPOS_TICKET.values()
             if item["categoria_id"] == getattr(canal.category, "id", None)),
            None
        )
        if tipo is None:
            tipo = {
                "nome": "Atendimento",
                "emoji": "🎫",
                "cor": discord.Color.blurple()
            }

        await interaction.response.defer(ephemeral=True)

        transcript = await gerar_transcript_ticket(canal)
        dono_id = extrair_dono_ticket(canal)

        await enviar_log_ticket_fechado(
            canal.guild,
            canal,
            tipo,
            dono_id,
            interaction.user,
            self.consideracoes.value.strip(),
            transcript
        )

        await interaction.followup.send(
            "✅ Ticket finalizado. O registro foi enviado para os logs.",
            ephemeral=True
        )

        try:
            await canal.delete(reason=f"Ticket finalizado por {interaction.user}")
        except (discord.Forbidden, discord.HTTPException):
            pass


class AdicionarMembroSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="👤 Selecione o membro para adicionar",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            return

        if not isinstance(interaction.user, discord.Member) or not pode_gerenciar_ticket(interaction.user):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return

        membro = self.values[0]
        try:
            await canal.set_permissions(
                membro,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            await interaction.response.send_message(
                f"✅ {membro.mention} foi adicionado ao ticket.",
                ephemeral=True
            )
            await canal.send(f"👤 {membro.mention} foi adicionado ao atendimento por {interaction.user.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não consegui adicionar esse membro.", ephemeral=True)


class RemoverMembroSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="❌ Selecione o membro para remover",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            return

        if not isinstance(interaction.user, discord.Member) or not pode_gerenciar_ticket(interaction.user):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return

        membro = self.values[0]
        dono_id = extrair_dono_ticket(canal)

        if membro.id == dono_id:
            await interaction.response.send_message(
                "❌ O solicitante não pode ser removido do próprio ticket.",
                ephemeral=True
            )
            return

        try:
            await canal.set_permissions(membro, overwrite=None)
            await interaction.response.send_message(
                f"✅ {membro.mention} foi removido do ticket.",
                ephemeral=True
            )
            await canal.send(f"❌ {membro.mention} foi removido do atendimento por {interaction.user.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não consegui remover esse membro.", ephemeral=True)


class RenomearTicketModal(discord.ui.Modal, title="✏️ Renomear Ticket"):
    nome = discord.ui.TextInput(
        label="Novo nome",
        placeholder="Ex.: denuncia-julio",
        required=True,
        max_length=90
    )

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not pode_gerenciar_ticket(interaction.user):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return

        novo_nome = self.nome.value.strip().lower().replace(" ", "-")
        caracteres = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        novo_nome = "".join(c for c in novo_nome if c in caracteres)[:90]

        if not novo_nome:
            await interaction.response.send_message("❌ Nome inválido.", ephemeral=True)
            return

        try:
            await canal.edit(name=novo_nome, reason=f"Ticket renomeado por {interaction.user}")
            await interaction.response.send_message(
                f"✅ Ticket renomeado para `{novo_nome}`.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não consegui renomear o ticket.", ephemeral=True)


class AdicionarMembroView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(AdicionarMembroSelect())


class RemoverMembroView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(RemoverMembroSelect())


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def autorizado(self, interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and pode_gerenciar_ticket(interaction.user)

    @discord.ui.button(label="Assumir Admin", emoji="🛡️", style=discord.ButtonStyle.danger, custom_id="ticket:assumir")
    async def assumir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode assumir o ticket.", ephemeral=True)
            return

        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            return

        dono_id = extrair_dono_ticket(canal)
        dono = canal.guild.get_member(dono_id) if dono_id else None

        await canal.edit(
            topic=f"{TICKET_MARKER}{dono_id}|tipo={next((k for k, v in TIPOS_TICKET.items() if v['categoria_id'] == getattr(canal.category, 'id', None)), 'atendimento')}|assumido_por={interaction.user.id}",
            reason=f"Ticket assumido por {interaction.user}"
        )

        embed = discord.Embed(
            title="🛡️ Atendimento assumido",
            description=f"{interaction.user.mention} assumiu a responsabilidade por este atendimento.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Saudar Atendimento", emoji="👋", style=discord.ButtonStyle.primary, custom_id="ticket:saudar")
    async def saudar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode usar este botão.", ephemeral=True)
            return
        dono_id = extrair_dono_ticket(interaction.channel)
        dono = interaction.guild.get_member(dono_id) if dono_id else None
        if dono:
            await interaction.response.send_message(
                f"👋 Olá, {dono.mention}! Seja bem-vindo(a) ao seu atendimento. "
                "Em breve nossa equipe dará continuidade à sua solicitação."
            )
        else:
            await interaction.response.send_message("👋 Olá! Sua solicitação está sendo atendida.")

    @discord.ui.button(label="Finalizar Ticket", emoji="✔️", style=discord.ButtonStyle.success, custom_id="ticket:finalizar")
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode finalizar.", ephemeral=True)
            return
        await interaction.response.send_modal(FinalizarTicketModal())

    @discord.ui.button(label="Chamar Membro", emoji="📣", style=discord.ButtonStyle.secondary, custom_id="ticket:chamar")
    async def chamar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode chamar o membro.", ephemeral=True)
            return
        dono_id = extrair_dono_ticket(interaction.channel)
        dono = interaction.guild.get_member(dono_id) if dono_id else None
        if not dono:
            await interaction.response.send_message("❌ Não encontrei o solicitante.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"🔔 {dono.mention}, seu atendimento foi chamado por {interaction.user.mention}."
        )

    @discord.ui.button(label="Adicionar Membro", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="ticket:adicionar")
    async def adicionar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode adicionar membros.", ephemeral=True)
            return
        await interaction.response.send_message(
            "👤 **Selecione o membro que deseja adicionar:**",
            ephemeral=True,
            view=AdicionarMembroView()
        )

    @discord.ui.button(label="Remover Membro", emoji="❌", style=discord.ButtonStyle.secondary, custom_id="ticket:remover")
    async def remover(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode remover membros.", ephemeral=True)
            return
        await interaction.response.send_message(
            "❌ **Selecione o membro que deseja remover:**",
            ephemeral=True,
            view=RemoverMembroView()
        )

    @discord.ui.button(label="Renomear Ticket", emoji="🖊️", style=discord.ButtonStyle.secondary, custom_id="ticket:renomear")
    async def renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.autorizado(interaction):
            await interaction.response.send_message("❌ Apenas a equipe autorizada pode renomear.", ephemeral=True)
            return
        await interaction.response.send_modal(RenomearTicketModal())


class AbrirTicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Denúncia",
                value="denuncia",
                emoji="🚔",
                description="Registre uma denúncia."
            ),
            discord.SelectOption(
                label="Corregedoria",
                value="corregedoria",
                emoji="⏳",
                description="Assuntos da Corregedoria."
            ),
            discord.SelectOption(
                label="Suporte",
                value="suporte",
                emoji="🚨",
                description="Solicite suporte."
            ),
            discord.SelectOption(
                label="Promoção",
                value="promocao",
                emoji="🛩️",
                description="Solicite análise de promoção."
            ),
            discord.SelectOption(
                label="Transferência",
                value="transferencia",
                emoji="🚓",
                description="Solicite transferência."
            ),
            discord.SelectOption(
                label="Exoneração",
                value="exoneracao",
                emoji="💀",
                description="Solicite exoneração."
            ),
        ]
        super().__init__(
            placeholder="📩 Selecione o tipo de atendimento",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket:abrir"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Este sistema só funciona dentro do servidor.", ephemeral=True)
            return

        chave = self.values[0]
        tipo = TIPOS_TICKET.get(chave)
        if not tipo:
            await interaction.response.send_message("❌ Tipo de atendimento inválido.", ephemeral=True)
            return

        existente = encontrar_ticket_do_usuario(interaction.guild, interaction.user.id)
        if existente:
            await interaction.response.send_message(
                f"❌ Você já possui um ticket aberto: {existente.mention}",
                ephemeral=True
            )
            return

        categoria = categoria_ticket(interaction.guild, tipo["categoria_id"])
        if categoria is None:
            await interaction.response.send_message(
                f"❌ A categoria de **{tipo['nome']}** não foi encontrada. Verifique o ID no código.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        bot_member = interaction.guild.me
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
        }

        # Cargo TICKET: equipe autorizada a visualizar e administrar o atendimento.
        cargo_ticket = discord.utils.find(
            lambda role: role.name.lower() == CARGO_TICKET_NOME.lower(),
            interaction.guild.roles
        )
        if cargo_ticket:
            overwrites[cargo_ticket] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True,
                attach_files=True,
                embed_links=True
            )

        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True,
                attach_files=True,
                embed_links=True
            )

        canal = await interaction.guild.create_text_channel(
            name=f"{TICKET_PREFIX}{chave}-{interaction.user.name}".lower()[:100],
            category=categoria,
            overwrites=overwrites,
            topic=f"{TICKET_MARKER}{interaction.user.id}|tipo={chave}",
            reason=f"Ticket {tipo['nome']} aberto por {interaction.user}"
        )

        embed = discord.Embed(
            title=f"{tipo['emoji']} {tipo['nome']}",
            description=(
                f"Olá, {interaction.user.mention}! 👋\n\n"
                f"Seu atendimento de **{tipo['nome']}** foi aberto com sucesso.\n\n"
                "📌 **Descreva o motivo do contato com o máximo de detalhes.**\n"
                "🕐 Aguarde um membro da equipe assumir o atendimento.\n\n"
                "⚠️ **Evite mensagens diretas para a equipe.**\n"
                "Os botões de gerenciamento são exclusivos da equipe autorizada."
            ),
            color=tipo["cor"],
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="👤 Solicitante",
            value=f"{interaction.user.mention}\n`{interaction.user.id}`",
            inline=True
        )
        embed.add_field(
            name="📂 Atendimento",
            value=f"{tipo['emoji']} {tipo['nome']}",
            inline=True
        )
        embed.add_field(
            name="🛡️ Responsável",
            value="Aguardando alguém assumir",
            inline=False
        )
        embed.set_thumbnail(url=avatar_url(interaction.user))
        embed.set_footer(text="Central da Polícia • Atendimento")

        await canal.send(embed=embed, view=TicketView())
        await canal.send(
            f"{interaction.user.mention} seu ticket foi aberto. "
            "Explique aqui sua solicitação para a equipe."
        )

        await interaction.followup.send(
            f"✅ Seu atendimento foi aberto: {canal.mention}",
            ephemeral=True
        )


class PainelTicketsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AbrirTicketSelect())


async def publicar_painel_tickets():
    for guild in bot.guilds:
        canal = obter_canal(guild, CANAL_ABRIR_TICKETS_ID)
        if canal is None:
            print(f"❌ Canal de abertura de tickets não encontrado: {CANAL_ABRIR_TICKETS_ID}")
            continue

        await apagar_painel_tickets_antigo(canal)

        embed = discord.Embed(
            title=PAINEL_TICKETS_TITULO,
            description=(
                "**Central de Atendimento da Polícia**\n\n"
                "Selecione abaixo o motivo do seu atendimento para abrir um ticket.\n\n"
                "🚔 **Denúncia** — registre uma denúncia.\n"
                "⏳ **Corregedoria** — assuntos da Corregedoria.\n"
                "🚨 **Suporte** — solicite suporte.\n"
                "🛩️ **Promoção** — solicite análise de promoção.\n"
                "🚓 **Transferência** — solicite transferência.\n"
                "💀 **Exoneração** — solicite exoneração.\n\n"
                "🔒 Seu atendimento será privado."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Central da Polícia • Sistema de Tickets")

        try:
            await canal.send(embed=embed, view=PainelTicketsView())
            print(f"🎫 Painel de tickets publicado em #{canal.name}.")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"❌ Não consegui publicar o painel de tickets: {e}")




# ============================================================
# 🎭 SISTEMA DE PEDIR SET / APROVAÇÃO
# ============================================================
# Fluxo:
# PEDIR SET -> envia a solicitação para APROVAR SET
# APROVAR -> somente quem possui 1 dos cargos autorizados
# RELATÓRIO -> registra aprovação ou recusa.
#
# Os 15 IDs abaixo são CARGOS DE AUTORIZAÇÃO, não cargos
# que serão entregues automaticamente ao recrutado.
# ============================================================

CARGO_SET_APROVADO_ID = 1547682455048294510

CARGOS_APROVADORES_IDS = {
    1547682361880084592,
    1547682357824454756,
    1550014293192474624,
    1547681871100387460,
    1547681867015135232,
    1547681858995749049,
    1547681854671421440,
    1547681850749747220,
    1547681841794912307,
    1547681838032617472,
    1547681834576379916,
    1547681830331879465,
    1547681816637345854,
    1547681812807946331,
    1547681806373888121,
}

SET_CANAIS = {
    1547682802927935508: {
        "nome": "POLICE",
        "aprovar_id": 1550018720246800455,
        "relatorio_id": 1547682806656663612,
    },
    1547682819780771840: {
        "nome": "INVESTIGATIVE / DEA",
        "aprovar_id": 1550018948534112326,
        "relatorio_id": 1547682823958438019,
    },
    1547682832317415514: {
        "nome": "BOP",
        "aprovar_id": 1550019071754371133,
        "relatorio_id": 1547682837585461389,
    },
    1547682850105466931: {
        "nome": "SHERIFF-S",
        "aprovar_id": 1550019206479609858,
        "relatorio_id": 1547682858875756704,
    },
    1547682870783512587: {
        "nome": "FIB",
        "aprovar_id": 1550019275996012554,
        "relatorio_id": 1547682878186463232,
    },
    1547682886487113778: {
        "nome": "EXÉRCITO",
        "aprovar_id": 1550019378035163187,
        "relatorio_id": 1547682892681842729,
    },
}

def pode_aprovar_set(member: discord.Member) -> bool:
    return any(role.id in CARGOS_APROVADORES_IDS for role in member.roles)

def obter_fluxo_set_por_canal(canal_id: int):
    return SET_CANAIS.get(canal_id)

def obter_canal_texto_por_id(guild: discord.Guild, canal_id: int):
    canal = guild.get_channel(canal_id)
    return canal if isinstance(canal, discord.TextChannel) else None

def campo_embed(embed: discord.Embed, nome: str, padrao="Não informado"):
    for field in embed.fields:
        if field.name.strip().lower() == nome.strip().lower():
            return field.value.replace("`", "").strip()
    return padrao

class PedirSetModal(discord.ui.Modal, title="📋 Solicitação de SET"):
    nome = discord.ui.TextInput(
        label="Nome",
        placeholder="Digite seu nome",
        required=True,
        max_length=80
    )
    id_cidade = discord.ui.TextInput(
        label="ID",
        placeholder="Digite seu ID",
        required=True,
        max_length=30
    )
    recrutador = discord.ui.TextInput(
        label="Recrutador",
        placeholder="Digite o nome ou ID do recrutador",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Este sistema só funciona dentro do servidor.", ephemeral=True
            )
            return

        fluxo = obter_fluxo_set_por_canal(interaction.channel.id)
        if not fluxo:
            await interaction.response.send_message(
                "❌ Este canal não está configurado para solicitar SET.", ephemeral=True
            )
            return

        canal_aprovar = obter_canal_texto_por_id(interaction.guild, fluxo["aprovar_id"])
        if canal_aprovar is None:
            await interaction.response.send_message(
                "❌ O canal de aprovação deste departamento não foi encontrado.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📋 NOVA SOLICITAÇÃO DE SET • {fluxo['nome']}",
            description=(
                "Uma nova solicitação foi enviada e aguarda análise da equipe autorizada.\n\n"
                "Use os botões abaixo para **aprovar ou recusar**."
            ),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Nome", value=f"`{self.nome.value.strip()}`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{self.id_cidade.value.strip()}`", inline=True)
        embed.add_field(name="👤 Discord", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="👮 Recrutador", value=f"`{self.recrutador.value.strip()}`", inline=False)
        embed.add_field(name="📍 Departamento", value=f"`{fluxo['nome']}`", inline=True)
        embed.add_field(name="📌 Canal de origem", value=f"<#{interaction.channel.id}>", inline=True)
        embed.add_field(name="🔄 Status", value="🟡 Aguardando aprovação", inline=False)
        embed.set_footer(text="Central da Polícia • Sistema de Recrutamento")

        try:
            await canal_aprovar.send(embed=embed, view=AprovacaoSetView())
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                "❌ Não consegui enviar a solicitação para o canal de aprovação. Verifique as permissões do bot.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Sua solicitação de SET para **{fluxo['nome']}** foi enviada para análise.",
            ephemeral=True
        )

class PedirSetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Pedir SET",
        emoji="📋",
        style=discord.ButtonStyle.primary,
        custom_id="set:pedir"
    )
    async def pedir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Este sistema só funciona dentro do servidor.", ephemeral=True
            )
            return
        if not obter_fluxo_set_por_canal(interaction.channel.id):
            await interaction.response.send_message(
                "❌ Este canal não está configurado para solicitar SET.", ephemeral=True
            )
            return
        await interaction.response.send_modal(PedirSetModal())

class AprovacaoSetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Aprovar",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="set:aprovar"
    )
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Ação inválida.", ephemeral=True
            )
            return

        if not pode_aprovar_set(interaction.user):
            await interaction.response.send_message(
                "❌ **Você não possui um dos cargos autorizados para aprovar solicitações.**",
                ephemeral=True
            )
            return

        embed_original = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed_original is None:
            await interaction.response.send_message(
                "❌ Não consegui ler os dados desta solicitação.", ephemeral=True
            )
            return

        nome = campo_embed(embed_original, "👤 Nome")
        id_cidade = campo_embed(embed_original, "🆔 ID")
        recrutador = campo_embed(embed_original, "👮 Recrutador")
        departamento = campo_embed(embed_original, "📍 Departamento")
        discord_id_texto = campo_embed(embed_original, "👤 Discord")

        membro = None
        try:
            match = re.search(r"(\d{15,22})", discord_id_texto)
            if match:
                membro = interaction.guild.get_member(int(match.group(1)))
        except (ValueError, TypeError):
            membro = None

        alteracao_nome = "Não realizado."
        cargo_aplicado = "❌ Não foi possível aplicar o cargo."

        if membro:
            cargo = interaction.guild.get_role(CARGO_SET_APROVADO_ID)
            if cargo is not None:
                try:
                    if cargo not in membro.roles:
                        await membro.add_roles(cargo, reason=f"SET aprovado por {interaction.user}")
                    cargo_aplicado = f"{cargo.mention} (`{cargo.id}`)"
                except (discord.Forbidden, discord.HTTPException):
                    cargo_aplicado = "❌ Não foi possível aplicar o cargo (hierarquia/permissão)."
            else:
                cargo_aplicado = f"❌ Cargo `{CARGO_SET_APROVADO_ID}` não encontrado no servidor."

            novo_nome = f"{nome} | {id_cidade}"[:32]
            try:
                await membro.edit(nick=novo_nome, reason=f"SET aprovado por {interaction.user}")
                alteracao_nome = f"Apelido alterado para `{novo_nome}`"
            except (discord.Forbidden, discord.HTTPException):
                alteracao_nome = "❌ Não foi possível alterar o apelido (permissão/hierarquia)."
        else:
            cargo_aplicado = "❌ Membro do Discord da solicitação não foi encontrado."

        canal_relatorio = None
        fluxo = None
        for dados in SET_CANAIS.values():
            if dados["aprovar_id"] == interaction.channel.id:
                fluxo = dados
                canal_relatorio = obter_canal_texto_por_id(interaction.guild, dados["relatorio_id"])
                break

        if canal_relatorio:
            relatorio = discord.Embed(
                title="✅ APROVAÇÃO DE SET REALIZADA",
                description="Uma solicitação de SET foi aprovada com sucesso.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            relatorio.add_field(name="👤 Recrutado", value=f"`{nome}`", inline=True)
            relatorio.add_field(name="🆔 ID", value=f"`{id_cidade}`", inline=True)
            relatorio.add_field(name="👮 Recrutador", value=f"`{recrutador}`", inline=False)
            relatorio.add_field(name="📍 Departamento", value=f"`{departamento}`", inline=True)
            relatorio.add_field(name="🛡️ Aprovado por", value=interaction.user.mention, inline=True)
            relatorio.add_field(name="✏️ Alteração", value=alteracao_nome, inline=False)
            relatorio.add_field(
                name="🎭 Cargo aplicado",
                value=cargo_aplicado,
                inline=False
            )
            relatorio.set_footer(text="Central da Polícia • Relatório de Aprovações")
            await enviar_embed(canal_relatorio, relatorio)

        try:
            await interaction.message.edit(
                embed=discord.Embed(
                    title=f"✅ SOLICITAÇÃO APROVADA • {departamento}",
                    description="Esta solicitação já foi processada.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                ),
                view=None
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await interaction.response.send_message(
            f"✅ Solicitação aprovada por {interaction.user.mention}.", ephemeral=True
        )

    @discord.ui.button(
        label="Recusar",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="set:recusar"
    )
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Ação inválida.", ephemeral=True)
            return

        if not pode_aprovar_set(interaction.user):
            await interaction.response.send_message(
                "❌ **Você não possui um dos cargos autorizados para recusar solicitações.**",
                ephemeral=True
            )
            return

        embed_original = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed_original is None:
            await interaction.response.send_message(
                "❌ Não consegui ler os dados desta solicitação.", ephemeral=True
            )
            return

        nome = campo_embed(embed_original, "👤 Nome")
        id_cidade = campo_embed(embed_original, "🆔 ID")
        recrutador = campo_embed(embed_original, "👮 Recrutador")
        departamento = campo_embed(embed_original, "📍 Departamento")

        canal_relatorio = None
        for dados in SET_CANAIS.values():
            if dados["aprovar_id"] == interaction.channel.id:
                canal_relatorio = obter_canal_texto_por_id(interaction.guild, dados["relatorio_id"])
                break

        if canal_relatorio:
            relatorio = discord.Embed(
                title="❌ SOLICITAÇÃO DE SET RECUSADA",
                description="Uma solicitação de SET foi recusada.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            relatorio.add_field(name="👤 Solicitante", value=f"`{nome}`", inline=True)
            relatorio.add_field(name="🆔 ID", value=f"`{id_cidade}`", inline=True)
            relatorio.add_field(name="👮 Recrutador", value=f"`{recrutador}`", inline=False)
            relatorio.add_field(name="📍 Departamento", value=f"`{departamento}`", inline=True)
            relatorio.add_field(name="🛡️ Recusado por", value=interaction.user.mention, inline=True)
            relatorio.add_field(name="📌 Status", value="❌ Recusado", inline=False)
            relatorio.set_footer(text="Central da Polícia • Relatório de Aprovações")
            await enviar_embed(canal_relatorio, relatorio)

        try:
            await interaction.message.edit(
                embed=discord.Embed(
                    title=f"❌ SOLICITAÇÃO RECUSADA • {departamento}",
                    description="Esta solicitação foi recusada.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                ),
                view=None
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await interaction.response.send_message(
            f"❌ Solicitação recusada por {interaction.user.mention}.", ephemeral=True
        )

async def publicar_paineis_pedir_set():
    """Publica/atualiza o painel de pedido de SET nos 6 canais configurados."""
    for guild in bot.guilds:
        for canal_id, fluxo in SET_CANAIS.items():
            canal = obter_canal_texto_por_id(guild, canal_id)
            if canal is None:
                print(f"⚠️ Canal PEDIR SET não encontrado: {canal_id} ({fluxo['nome']})")
                continue

            embed = discord.Embed(
                title="📋 PEDIR SET",
                description=(
                    "**🇲🇽 Bem-vindo à Central de Polícia México Roleplay!**\n\n"
                    "Aqui você poderá solicitar o **SET para a sua guarnição desejada**.\n\n"
                    f"📍 **Guarnição identificada automaticamente:** `{fluxo['nome']}`\n\n"
                    "Clique no botão abaixo e informe apenas:\n"
                    "👤 **Nome**\n"
                    "🆔 **ID**\n"
                    "👮 **Recrutador**\n\n"
                    "⚠️ Confira os dados antes de enviar. Sua solicitação será encaminhada "
                    "ao canal de aprovação correspondente."
                ),
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Central da Polícia • Sistema de SET")

            # Evita duplicar o painel do bot.
            try:
                mensagens = [m async for m in canal.history(limit=50)]
                for mensagem in mensagens:
                    if mensagem.author.id == bot.user.id and mensagem.embeds:
                        if mensagem.embeds[0].title == "📋 PEDIR SET":
                            await mensagem.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

            try:
                await canal.send(embed=embed, view=PedirSetView())
                print(f"🎭 Painel PEDIR SET publicado: {fluxo['nome']}")
            except (discord.Forbidden, discord.HTTPException) as e:
                print(f"❌ Não consegui publicar PEDIR SET em {canal_id}: {e}")


# ============================================================
# 🤖 EVENTOS DO BOT
# ============================================================

@bot.event
async def on_ready():
    print("=" * 60)
    print("🚔 CENTRAL DA POLÍCIA — BOT ONLINE")
    print(f"🤖 {bot.user}")
    print(f"🆔 {bot.user.id}")
    print("📊 Logs normais: ATIVOS")
    print("🔐 Logs de segurança: ATIVOS")
    print("👤 Entradas e saídas: ATIVOS")
    print("🎫 Sistema de tickets: ATIVO")
    print(f"🛡️ Cargo de atendimento: {CARGO_TICKET_NOME}")
    print("🚨 Anti-Nuke: ATIVO (remove cargos do responsável por ações protegidas)")

    # Views permanentes: os botões continuam funcionando após reinício.
    if not getattr(bot, "_ticket_views_registradas", False):
        bot.add_view(PainelTicketsView())
        bot.add_view(TicketView())
        bot.add_view(PedirSetView())
        bot.add_view(AprovacaoSetView())
        bot._ticket_views_registradas = True

    for nome, canal_id in [
        ("📊 Logs normais", CANAL_LOGS_NORMAIS_ID),
        ("🔐 Logs de segurança", CANAL_LOGS_SEGURANCA_ID),
        ("📥 Membros que entraram", CANAL_MEMBROS_ENTRARAM_ID),
        ("📤 Membros que saíram", CANAL_MEMBROS_SAIRAM_ID),
        ("📋 Advertências", CANAL_ADVERTENCIAS_ID),
        ("🎫 Abrir tickets", CANAL_ABRIR_TICKETS_ID),
        ("📑 Logs de tickets", CANAL_LOGS_TICKETS_ID),
    ]:
        canal = discord.utils.find(lambda c: c.id == canal_id, bot.get_all_channels())
        print(f"   {nome}: {'OK' if canal else 'NÃO ENCONTRADO'} ({canal_id})")

    for nome, categoria_id in [
        ("🚔 Denúncia", CATEGORIA_DENUNCIA_ID),
        ("⏳ Corregedoria", CATEGORIA_CORREGEDORIA_ID),
        ("🚨 Suporte", CATEGORIA_SUPORTE_ID),
        ("🛩️ Promoção", CATEGORIA_PROMOCAO_ID),
        ("🚓 Transferência", CATEGORIA_TRANSFERENCIA_ID),
        ("💀 Exoneração", CATEGORIA_EXONERACAO_ID),
    ]:
        categoria = discord.utils.find(lambda c: c.id == categoria_id, bot.get_all_channels())
        print(f"   {nome}: {'OK' if categoria else 'NÃO ENCONTRADA'} ({categoria_id})")

    await publicar_painel_tickets()
    await publicar_paineis_pedir_set()
    print("=" * 60)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"❌ Erro: {error}")


if __name__ == "__main__":
    if TOKEN == "COLOQUE_O_TOKEN_AQUI":
        print("❌ Coloque o TOKEN do novo bot no arquivo.")
    else:
        bot.run(TOKEN)
