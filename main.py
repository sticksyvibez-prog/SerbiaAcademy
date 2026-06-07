import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
import random
import string
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ── Configuration ─────────────────────────────────────────────────────────────
STAFF_ROLE_ID = 1500972974155632762  # Role ID required for admin commands
LOG_CHANNEL_NAME = "bot-logs"        # Channel where actions are logged

# ── Database initialisation ───────────────────────────────────────────────────
DB_PATH = "norse_academy.db"


def init_db() -> None:
    """Create all required tables if they do not already exist."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT NOT NULL,
            joined_at   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            training_id TEXT PRIMARY KEY,
            host_id     INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            cancelled   INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id TEXT NOT NULL,
            user_id     INTEGER NOT NULL,
            join_time   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            examiner_id INTEGER NOT NULL,
            result      TEXT NOT NULL,
            notes       TEXT,
            logged_at   TEXT NOT NULL
        )
    """)

    con.commit()
    con.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_training_id(length: int = 8) -> str:
    """Return a random alphanumeric training ID."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def is_staff(member: discord.Member) -> bool:
    """Return True if the member holds the staff role (checked by role ID)."""
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


async def send_log(guild: discord.Guild, message: str) -> None:
    """Post *message* to the designated log channel, if it exists."""
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if channel:
        await channel.send(message)


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready() -> None:
    init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as exc:
        print(f"Failed to sync commands: {exc}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


# ── Slash commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="register", description="Register yourself with the Norse Academy.")
async def register(interaction: discord.Interaction) -> None:
    user = interaction.user
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT user_id FROM registrations WHERE user_id = ?", (user.id,))
    if cur.fetchone():
        await interaction.response.send_message("You are already registered.", ephemeral=True)
        con.close()
        return

    cur.execute(
        "INSERT INTO registrations (user_id, username, joined_at) VALUES (?, ?, ?)",
        (user.id, str(user), now_iso()),
    )
    con.commit()
    con.close()

    await interaction.response.send_message(
        f"Welcome to the Norse Academy, {user.mention}! You have been registered.", ephemeral=False
    )
    await send_log(interaction.guild, f"📋 **Register** — {user} (`{user.id}`) registered.")


@bot.tree.command(name="progress", description="Check your training and exam progress.")
async def progress(interaction: discord.Interaction) -> None:
    user = interaction.user
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT joined_at FROM registrations WHERE user_id = ?", (user.id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            "You are not registered. Use `/register` first.", ephemeral=True
        )
        con.close()
        return

    joined_at = row[0]

    cur.execute("SELECT COUNT(*) FROM training_logs WHERE user_id = ?", (user.id,))
    training_count = cur.fetchone()[0]

    cur.execute(
        "SELECT result, logged_at FROM exam_logs WHERE user_id = ? ORDER BY logged_at DESC LIMIT 1",
        (user.id,),
    )
    exam_row = cur.fetchone()
    con.close()

    embed = discord.Embed(title="Norse Academy — Your Progress", colour=discord.Colour.gold())
    embed.add_field(name="Registered", value=joined_at[:10], inline=True)
    embed.add_field(name="Trainings Attended", value=str(training_count), inline=True)
    if exam_row:
        embed.add_field(name="Last Exam Result", value=f"{exam_row[0]} ({exam_row[1][:10]})", inline=True)
    else:
        embed.add_field(name="Last Exam Result", value="No exam taken yet", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="createtraining", description="[Staff] Create a new training session.")
@app_commands.describe(topic="The topic or subject of the training session.")
async def createtraining(interaction: discord.Interaction, topic: str) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    training_id = generate_training_id()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO trainings (training_id, host_id, topic, created_at) VALUES (?, ?, ?, ?)",
        (training_id, interaction.user.id, topic, now_iso()),
    )
    con.commit()
    con.close()

    await interaction.response.send_message(
        f"✅ Training session created!\n**ID:** `{training_id}`\n**Topic:** {topic}"
    )
    await send_log(
        interaction.guild,
        f"🏋️ **CreateTraining** — {interaction.user} created training `{training_id}` on topic: *{topic}*.",
    )


@bot.tree.command(name="jointime", description="[Staff] Record a member's join time for a training session.")
@app_commands.describe(
    training_id="The training session ID.",
    member="The member who joined the training.",
)
async def jointime(
    interaction: discord.Interaction,
    training_id: str,
    member: discord.Member,
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(f"Training `{training_id}` not found.", ephemeral=True)
        con.close()
        return
    if row[0]:
        await interaction.response.send_message(f"Training `{training_id}` has been cancelled.", ephemeral=True)
        con.close()
        return

    join_time = now_iso()
    cur.execute(
        "INSERT INTO training_logs (training_id, user_id, join_time) VALUES (?, ?, ?)",
        (training_id, member.id, join_time),
    )
    con.commit()
    con.close()

    await interaction.response.send_message(
        f"✅ Recorded join time for {member.mention} in training `{training_id}`."
    )
    await send_log(
        interaction.guild,
        f"⏱️ **JoinTime** — {member} joined training `{training_id}` at {join_time}.",
    )


@bot.tree.command(name="logtraining", description="[Staff] Mark a training session as completed.")
@app_commands.describe(training_id="The training session ID to finalise.")
async def logtraining(interaction: discord.Interaction, training_id: str) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(f"Training `{training_id}` not found.", ephemeral=True)
        con.close()
        return
    if row[1]:
        await interaction.response.send_message(f"Training `{training_id}` has been cancelled.", ephemeral=True)
        con.close()
        return

    cur.execute("SELECT COUNT(*) FROM training_logs WHERE training_id = ?", (training_id,))
    attendee_count = cur.fetchone()[0]
    con.close()

    await interaction.response.send_message(
        f"📝 Training `{training_id}` (*{row[0]}*) logged with **{attendee_count}** attendee(s)."
    )
    await send_log(
        interaction.guild,
        f"📝 **LogTraining** — Training `{training_id}` (*{row[0]}*) finalised by {interaction.user} "
        f"with {attendee_count} attendee(s).",
    )


@bot.tree.command(name="logexam", description="[Staff] Log an exam result for a member.")
@app_commands.describe(
    member="The member who took the exam.",
    result="Pass or Fail.",
    notes="Optional notes about the exam.",
)
@app_commands.choices(result=[
    app_commands.Choice(name="Pass", value="Pass"),
    app_commands.Choice(name="Fail", value="Fail"),
])
async def logexam(
    interaction: discord.Interaction,
    member: discord.Member,
    result: str,
    notes: str = "",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    logged_at = now_iso()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO exam_logs (user_id, examiner_id, result, notes, logged_at) VALUES (?, ?, ?, ?, ?)",
        (member.id, interaction.user.id, result, notes or None, logged_at),
    )
    con.commit()
    con.close()

    await interaction.response.send_message(
        f"✅ Exam result **{result}** logged for {member.mention}."
    )
    await send_log(
        interaction.guild,
        f"📊 **LogExam** — {interaction.user} logged **{result}** for {member} at {logged_at}."
        + (f" Notes: *{notes}*" if notes else ""),
    )


@bot.tree.command(name="result", description="[Staff] Send an exam result DM and optionally kick on failure.")
@app_commands.describe(
    member="The member to notify.",
    result="Pass or Fail.",
    kick_on_fail="Kick the member from the server if they failed (default: False).",
    notes="Optional notes to include in the DM.",
)
@app_commands.choices(result=[
    app_commands.Choice(name="Pass", value="Pass"),
    app_commands.Choice(name="Fail", value="Fail"),
])
async def result(
    interaction: discord.Interaction,
    member: discord.Member,
    result: str,
    kick_on_fail: bool = False,
    notes: str = "",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Build DM message
    if result == "Pass":
        dm_message = (
            f"🎉 Congratulations! You have **passed** your Norse Academy exam.\n"
            + (f"Notes from your examiner: *{notes}*" if notes else "")
        )
    else:
        dm_message = (
            f"❌ Unfortunately, you have **failed** your Norse Academy exam.\n"
            + (f"Notes from your examiner: *{notes}*\n" if notes else "")
            + "You are welcome to re-apply after reviewing the material."
        )

    # Attempt to DM the member
    dm_sent = True
    try:
        await member.send(dm_message)
    except discord.Forbidden:
        dm_sent = False

    # Kick on failure if requested
    kicked = False
    if result == "Fail" and kick_on_fail:
        try:
            await member.kick(reason="Failed Norse Academy exam.")
            kicked = True
        except discord.Forbidden:
            pass

    status_parts = []
    status_parts.append("DM sent ✅" if dm_sent else "DM failed (user has DMs disabled) ⚠️")
    if kick_on_fail:
        status_parts.append("Member kicked ✅" if kicked else "Kick failed (missing permissions) ⚠️")

    await interaction.response.send_message(
        f"Result **{result}** processed for {member.mention}. " + " | ".join(status_parts),
        ephemeral=True,
    )
    await send_log(
        interaction.guild,
        f"📬 **Result** — {interaction.user} sent **{result}** result to {member}."
        + (" Kicked." if kicked else "")
        + (f" Notes: *{notes}*" if notes else ""),
    )


@bot.tree.command(name="dm", description="[Staff] Send a direct message to a member.")
@app_commands.describe(
    member="The member to message.",
    message="The message content to send.",
)
async def dm(
    interaction: discord.Interaction,
    member: discord.Member,
    message: str,
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    sent = True
    try:
        await member.send(f"📨 **Message from Norse Academy Staff:**\n{message}")
    except discord.Forbidden:
        sent = False

    if sent:
        await interaction.response.send_message(f"✅ Message sent to {member.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"⚠️ Could not send a DM to {member.mention} (they may have DMs disabled).", ephemeral=True
        )

    await send_log(
        interaction.guild,
        f"📨 **DM** — {interaction.user} sent a DM to {member}: *{message}*",
    )


@bot.tree.command(name="canceltraining", description="[Staff] Cancel an existing training session.")
@app_commands.describe(training_id="The training session ID to cancel.")
async def canceltraining(interaction: discord.Interaction, training_id: str) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(f"Training `{training_id}` not found.", ephemeral=True)
        con.close()
        return
    if row[1]:
        await interaction.response.send_message(
            f"Training `{training_id}` is already cancelled.", ephemeral=True
        )
        con.close()
        return

    cur.execute("UPDATE trainings SET cancelled = 1 WHERE training_id = ?", (training_id,))
    con.commit()
    con.close()

    await interaction.response.send_message(
        f"🚫 Training `{training_id}` (*{row[0]}*) has been cancelled."
    )
    await send_log(
        interaction.guild,
        f"🚫 **CancelTraining** — {interaction.user} cancelled training `{training_id}` (*{row[0]}*).",
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")
    bot.run(TOKEN)
