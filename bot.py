import os
import re
import time
import asyncio
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database import Database


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

# Anti-Spam
SPAM_LIMIT = 5
SPAM_WINDOW = 5
TIMEOUT_MINUTES = 2

# Vrijeme zaključavanja korisnika nakon timeouta
TIMEOUT_LOCK_SECONDS = 3


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix="/",
    intents=intents
)


# =========================================================
# DATABASE
# =========================================================

database = Database()


# =========================================================
# ANTI-SPAM MEMORY
# =========================================================

# Vrijeme zadnjih poruka korisnika
message_history = defaultdict(deque)

# Korisnici koji su upravo dobili timeout
timeout_users = set()


# =========================================================
# LINK DETECTION
# =========================================================

URL_REGEX = re.compile(
    r"(https?://\S+|www\.\S+)",
    re.IGNORECASE
)


def contains_link(content: str) -> bool:
    """
    Provjerava sadrži li poruka link.
    """

    return bool(
        URL_REGEX.search(content)
    )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print("=" * 60)

    print(f"🛡️ BOT: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")

    print()

    print("🎮 Anti-Spam: AKTIVAN")
    print(f"📨 Limit: {SPAM_LIMIT} poruka")
    print(f"⏱️ Prozor: {SPAM_WINDOW} sekundi")
    print(f"🔇 Timeout: {TIMEOUT_MINUTES} minute")

    print()

    print("🔗 Link Block: AKTIVAN")

    print()

    print(f"🌐 Serveri: {len(bot.guilds)}")

    print("=" * 60)

    # -----------------------------------------------------
    # Registracija slash komandi
    # -----------------------------------------------------

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Registrirano {len(synced)} slash komandi."
        )

    except Exception as error:

        print(
            f"❌ Greška kod registracije komandi: {error}"
        )


# =========================================================
# SERVER JOIN
# =========================================================

@bot.event
async def on_guild_join(
    guild: discord.Guild
):

    print(
        f"➕ Bot je dodan na server: "
        f"{guild.name} ({guild.id})"
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

@bot.event
async def on_message(
    message: discord.Message
):

    # -----------------------------------------------------
    # Ignoriraj botove
    # -----------------------------------------------------

    if message.author.bot:
        return


    # -----------------------------------------------------
    # Ignoriraj privatne poruke
    # -----------------------------------------------------

    if message.guild is None:
        return


    member = message.author


    # -----------------------------------------------------
    # ADMIN / MODERATOR ZAŠTITA
    # -----------------------------------------------------

    if member.guild_permissions.administrator:
        return


    if member.guild_permissions.manage_messages:
        return


    if member.guild_permissions.moderate_members:
        return


    # =====================================================
    # LINK BLOCK
    # =====================================================

    if database.is_link_block_enabled(
        message.guild.id,
        message.channel.id
    ):

        if contains_link(
            message.content
        ):

            try:

                await message.delete()

                print(
                    f"[LINK-BLOCK] "
                    f"{member} ({member.id}) "
                    f"poslao link u "
                    f"#{message.channel.name}"
                )

            except discord.Forbidden:

                print(
                    "[GREŠKA] Bot nema dozvolu "
                    "za brisanje poruka."
                )

            except discord.HTTPException as error:

                print(
                    f"[DISCORD GREŠKA] {error}"
                )

            return


    # =====================================================
    # ANTI-SPAM
    # =====================================================

    user_id = member.id

    current_time = time.monotonic()

    messages = message_history[user_id]


    # -----------------------------------------------------
    # Dodaj novu poruku
    # -----------------------------------------------------

    messages.append(
        current_time
    )


    # -----------------------------------------------------
    # Obriši poruke starije od 5 sekundi
    # -----------------------------------------------------

    while messages:

        oldest_message = messages[0]

        if (
            current_time
            - oldest_message
            <= SPAM_WINDOW
        ):
            break

        messages.popleft()


    # -----------------------------------------------------
    # Provjera spama
    # -----------------------------------------------------

    if len(messages) >= SPAM_LIMIT:

        # -------------------------------------------------
        # Spriječi višestruke timeoutove
        # -------------------------------------------------

        if user_id in timeout_users:
            return


        timeout_users.add(
            user_id
        )


        # Reset brojača
        messages.clear()


        try:

            # ---------------------------------------------
            # TIMEOUT
            # ---------------------------------------------

            await member.timeout(

                timedelta(
                    minutes=TIMEOUT_MINUTES
                ),

                reason=(
                    "Anti-Spam: "
                    f"{SPAM_LIMIT} poruka u "
                    f"{SPAM_WINDOW} sekundi"
                )
            )


            # ---------------------------------------------
            # UPOZORENJE
            # ---------------------------------------------

            warning = await message.channel.send(

                f"⚠️ {member.mention}\n\n"

                f"Previše poruka u kratkom vremenu.\n\n"

                f"🔇 Timeout: "
                f"**{TIMEOUT_MINUTES} minute**\n\n"

                f"🛡️ Anti-Spam zaštita"

            )


            # ---------------------------------------------
            # Obriši upozorenje nakon 10 sekundi
            # ---------------------------------------------

            await warning.delete(
                delay=10
            )


            print(
                f"[ANTI-SPAM] "
                f"{member} ({member.id}) "
                f"dobio timeout od "
                f"{TIMEOUT_MINUTES} minute."
            )


        except discord.Forbidden:

            print(
                "[GREŠKA] Bot nema "
                "Moderate Members permission."
            )


        except discord.HTTPException as error:

            print(
                f"[DISCORD GREŠKA] {error}"
            )


        except Exception as error:

            print(
                f"[GREŠKA] {error}"
            )


        finally:

            await asyncio.sleep(
                TIMEOUT_LOCK_SECONDS
            )

            timeout_users.discard(
                user_id
            )


    # -----------------------------------------------------
    # Command event
    # -----------------------------------------------------

    await bot.process_commands(
        message
    )


# =========================================================
# /INFO
# =========================================================

@bot.tree.command(
    name="info",
    description="Informacije o botu i njegovim komandama."
)
async def info(
    interaction: discord.Interaction
):

    embed = discord.Embed(

        title="🛡️ Anti-Spam Bot",

        description=(
            "Bot automatski štiti server "
            "od spama i neželjenih linkova."
        ),

        color=discord.Color.blue()

    )


    # -----------------------------------------------------
    # Anti-Spam
    # -----------------------------------------------------

    embed.add_field(

        name="🎮 Anti-Spam",

        value=(

            f"📨 **{SPAM_LIMIT} poruka**\n"

            f"⏱️ unutar **{SPAM_WINDOW} sekundi**\n"

            f"🔇 timeout **{TIMEOUT_MINUTES} minute**"

        ),

        inline=False

    )


    # -----------------------------------------------------
    # Link Protection
    # -----------------------------------------------------

    embed.add_field(

        name="🔗 Link Protection",

        value=(

            "Administratori i moderatori mogu "
            "uključiti automatsko brisanje linkova "
            "u pojedinom kanalu."

        ),

        inline=False

    )


    # -----------------------------------------------------
    # Commands
    # -----------------------------------------------------

    embed.add_field(

        name="📋 Komande",

        value=(

            "`/info` — informacije o botu\n"

            "`/ping` — provjera pinga\n"

            "`/status` — status Anti-Spama\n"

            "`/linkblock on` — zabrani linkove\n"

            "`/linkblock off` — dozvoli linkove\n"

            "`/linkblock status` — status linkova"

        ),

        inline=False

    )


    # -----------------------------------------------------
    # Protection
    # -----------------------------------------------------

    embed.add_field(

        name="🛡️ Zaštita",

        value=(

            "• prati sve tekstualne kanale\n"

            "• ignorira botove\n"

            "• ignorira administratore\n"

            "• ignorira moderatore\n"

            "• automatski timeouta spamere\n"

            "• automatski briše linkove "
            "u zaštićenim kanalima"

        ),

        inline=False

    )


    embed.set_footer(
        text="Anti-Spam Protection"
    )


    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /PING
# =========================================================

@bot.tree.command(
    name="ping",
    description="Provjeri radi li bot."
)
async def ping(
    interaction: discord.Interaction
):

    latency = round(
        bot.latency * 1000
    )


    await interaction.response.send_message(

        f"🏓 **Pong!**\n\n"

        f"📡 Ping: **{latency} ms**\n"

        f"🟢 Bot radi."

    )


# =========================================================
# /STATUS
# =========================================================

@bot.tree.command(
    name="status",
    description="Prikaži Anti-Spam status."
)
async def status(
    interaction: discord.Interaction
):

    protected_channels = (
        database.get_link_block_channels(
            interaction.guild.id
        )
    )


    embed = discord.Embed(

        title="🛡️ Anti-Spam Status",

        color=discord.Color.green()

    )


    embed.add_field(

        name="Status",

        value="🟢 AKTIVAN",

        inline=True

    )


    embed.add_field(

        name="Spam limit",

        value=f"{SPAM_LIMIT} poruka",

        inline=True

    )


    embed.add_field(

        name="Vremenski prozor",

        value=f"{SPAM_WINDOW} sekundi",

        inline=True

    )


    embed.add_field(

        name="Timeout",

        value=f"{TIMEOUT_MINUTES} minute",

        inline=True

    )


    embed.add_field(

        name="Zaštićenih kanala",

        value=str(
            len(protected_channels)
        ),

        inline=True

    )


    embed.add_field(

        name="Serveri",

        value=str(
            len(bot.guilds)
        ),

        inline=True

    )


    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /LINKBLOCK
# =========================================================

@bot.tree.command(
    name="linkblock",
    description="Upravljaj zabranom linkova u ovom kanalu."
)
@app_commands.describe(

    action=(
        "on = zabrani linkove, "
        "off = dozvoli linkove, "
        "status = provjeri status"
    )

)
@app_commands.choices(

    action=[

        app_commands.Choice(
            name="on",
            value="on"
        ),

        app_commands.Choice(
            name="off",
            value="off"
        ),

        app_commands.Choice(
            name="status",
            value="status"
        )

    ]

)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def linkblock(

    interaction: discord.Interaction,

    action: app_commands.Choice[str]

):

    channel_id = (
        interaction.channel.id
    )

    guild_id = (
        interaction.guild.id
    )


    # =====================================================
    # ON
    # =====================================================

    if action.value == "on":

        database.enable_link_block(

            guild_id,

            channel_id

        )


        await interaction.response.send_message(

            f"🔗🚫 Zabrana linkova je "
            f"**UKLJUČENA** u "
            f"{interaction.channel.mention}.\n\n"

            f"Svaka poruka korisnika koja "
            f"sadrži link bit će automatski obrisana.\n\n"

            f"💾 Postavka je spremljena u SQLite bazu."

        )

        return


    # =====================================================
    # OFF
    # =====================================================

    if action.value == "off":

        database.disable_link_block(

            guild_id,

            channel_id

        )


        await interaction.response.send_message(

            f"🔗✅ Zabrana linkova je "
            f"**ISKLJUČENA** u "
            f"{interaction.channel.mention}.\n\n"

            f"💾 Postavka je spremljena u SQLite bazu."

        )

        return


    # =====================================================
    # STATUS
    # =====================================================

    if action.value == "status":

        enabled = (
            database.is_link_block_enabled(

                guild_id,

                channel_id

            )
        )


        if enabled:

            status_text = (
                "🟢 UKLJUČENA"
            )

        else:

            status_text = (
                "🔴 ISKLJUČENA"
            )


        await interaction.response.send_message(

            f"🔗 **Link Block**\n\n"

            f"Kanal: "
            f"{interaction.channel.mention}\n"

            f"Status: "
            f"{status_text}",

            ephemeral=True

        )

        return


# =========================================================
# SLASH COMMAND ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(

    interaction: discord.Interaction,

    error: app_commands.AppCommandError

):

    if isinstance(
        error,
        app_commands.MissingPermissions
    ):

        message = (
            "❌ Nemaš potrebne moderatorske "
            "dozvole za ovu komandu."
        )

    else:

        print(
            f"[COMMAND ERROR] {error}"
        )

        message = (
            "❌ Došlo je do greške "
            "pri izvršavanju komande."
        )


    if interaction.response.is_done():

        await interaction.followup.send(

            message,

            ephemeral=True

        )

    else:

        await interaction.response.send_message(

            message,

            ephemeral=True

        )


# =========================================================
# START BOT
# =========================================================

if not TOKEN:

    raise RuntimeError(

        "DISCORD_TOKEN nije postavljen "
        "u .env datoteci."

    )


bot.run(TOKEN)