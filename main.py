import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
import random
import string
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ── Configuration ─────────────────────────────────────────────────────────────
STAFF_ROLE_ID   = 1500972974155632762   # Role ID required for staff commands
LOG_CHANNEL_ID  = 1513062138254594069   # Channel ID where actions are logged

# ── Custom emoji constants ────────────────────────────────────────────────────
TAIL     = "<:na_tail:1234567890000000001>"
INFO     = "<:na_info:1234567890000000002>"
ACTION   = "<:na_action:1234567890000000003>"
SCHEDULE = "<:na_schedule:1234567890000000004>"
TICK     = "<:na_tick:1234567890000000005>"
ROBLOX   = "<:na_roblox:1234567890000000006>"
LOGO     = "<:na_logo:1234567890000000007>"

# ── Department choices ────────────────────────────────────────────────────────
DEPARTMENT_CHOICES = [
    app_commands.Choice(name="General",          value="General"),
    app_commands.Choice(name="Security",         value="Security"),
    app_commands.Choice(name="Medical",          value="Medical"),
    app_commands.Choice(name="Engineering",      value="Engineering"),
    app_commands.Choice(name="Command",          value="Command"),
    app_commands.Choice(name="Intelligence",     value="Intelligence"),
    app_commands.Choice(name="Logistics",        value="Logistics"),
    app_commands.Choice(name="Communications",   value="Communications"),
]

# ── Exam choices ──────────────────────────────────────────────────────────────
EXAM_NAME_CHOICES = [
    app_commands.Choice(name="Basic Training Exam",       value="Basic Training Exam"),
    app_commands.Choice(name="Advanced Training Exam",    value="Advanced Training Exam"),
    app_commands.Choice(name="Leadership Exam",           value="Leadership Exam"),
    app_commands.Choice(name="Security Clearance Exam",   value="Security Clearance Exam"),
    app_commands.Choice(name="Medical Certification",     value="Medical Certification"),
    app_commands.Choice(name="Engineering Assessment",    value="Engineering Assessment"),
]

EXAM_OUTCOME_CHOICES = [
    app_commands.Choice(name="PASSED",  value="PASSED"),
    app_commands.Choice(name="FAILED",  value="FAILED"),
]

# ── Training log status choices ───────────────────────────────────────────────
TRAINING_STATUS_CHOICES = [
    app_commands.Choice(name="ATTENDED", value="ATTENDED"),
    app_commands.Choice(name="ABSENT",   value="ABSENT"),
    app_commands.Choice(name="FAILED",   value="FAILED"),
]

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
            department  TEXT NOT NULL,
            joined_at   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            training_id TEXT PRIMARY KEY,
            host_id     INTEGER NOT NULL,
            department  TEXT NOT NULL,
            topic       TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            cancelled   INTEGER NOT NULL DEFAULT 0,
            cancel_reason TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id TEXT NOT NULL,
            user_id     INTEGER NOT NULL,
            status      TEXT NOT NULL,
            join_time   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            examiner_id INTEGER NOT NULL,
            exam_name   TEXT NOT NULL,
            outcome     TEXT NOT NULL,
            notes       TEXT,
            logged_at   TEXT NOT NULL
        )
    """)

    con.commit()
    con.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_training_id() -> str:
    """Return a random NTA-prefixed training ID (e.g. NTA-A3F9K2)."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"NTA-{suffix}"


def is_staff(member: discord.Member) -> bool:
    """Return True if the member holds the staff role (checked by role ID)."""
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


async def send_log(guild: discord.Guild, embed: discord.Embed) -> None:
    """Post an embed to the designated log channel, if it exists."""
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def now_ts() -> int:
    """Return the current UTC time as a Unix timestamp (for Discord timestamps)."""
    return int(datetime.now(timezone.utc).timestamp())


def log_embed(title: str, actor: discord.Member, colour: discord.Colour, **fields) -> discord.Embed:
    """Build a standardised log embed."""
    embed = discord.Embed(
        title=f"{LOGO} {title}",
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"Actor: {actor} ({actor.id})", icon_url=actor.display_avatar.url)
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=True)
    return embed


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

# /register ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="register", description="Register yourself with the Norse Academy.")
@app_commands.describe(department="The department you are joining.")
@app_commands.choices(department=DEPARTMENT_CHOICES)
async def register(interaction: discord.Interaction, department: str) -> None:
    user = interaction.user
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT user_id FROM registrations WHERE user_id = ?", (user.id,))
    if cur.fetchone():
        await interaction.response.send_message(
            f"{INFO} You are already registered with the Norse Academy.", ephemeral=True
        )
        con.close()
        return

    joined_at = now_iso()
    cur.execute(
        "INSERT INTO registrations (user_id, username, department, joined_at) VALUES (?, ?, ?, ?)",
        (user.id, str(user), department, joined_at),
    )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Registration",
        description=(
            f"{TICK} Welcome to the Norse Academy, {user.mention}!\n"
            f"You have been successfully registered under the **{department}** department."
        ),
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name=f"{INFO} Department", value=department, inline=True)
    embed.add_field(name=f"{SCHEDULE} Registered At", value=f"<t:{now_ts()}:F>", inline=True)

    await interaction.response.send_message(embed=embed)
    await send_log(
        interaction.guild,
        log_embed(
            "New Registration",
            user,
            discord.Colour.green(),
            Member=user.mention,
            Department=department,
            Registered=f"<t:{now_ts()}:F>",
        ),
    )


# /progress ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="progress", description="Check your training and exam progress.")
async def progress(interaction: discord.Interaction) -> None:
    user = interaction.user
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT department, joined_at FROM registrations WHERE user_id = ?", (user.id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{INFO} You are not registered. Use `/register` first.", ephemeral=True
        )
        con.close()
        return

    department, joined_at = row

    cur.execute(
        "SELECT COUNT(*) FROM training_logs WHERE user_id = ? AND status = 'ATTENDED'",
        (user.id,),
    )
    attended = cur.fetchone()[0]

    cur.execute(
        "SELECT exam_name, outcome, logged_at FROM exam_logs WHERE user_id = ? ORDER BY logged_at DESC LIMIT 1",
        (user.id,),
    )
    exam_row = cur.fetchone()
    con.close()

    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Progress Report",
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name=f"{INFO} Member",     value=user.mention,  inline=True)
    embed.add_field(name=f"{INFO} Department", value=department,     inline=True)
    embed.add_field(name=f"{SCHEDULE} Registered", value=joined_at[:10], inline=True)
    embed.add_field(name=f"{TICK} Trainings Attended", value=str(attended), inline=True)

    if exam_row:
        embed.add_field(
            name=f"{ACTION} Last Exam",
            value=f"{exam_row[0]} — **{exam_row[1]}** ({exam_row[2][:10]})",
            inline=True,
        )
    else:
        embed.add_field(name=f"{ACTION} Last Exam", value="No exam taken yet", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# /createtraining ─────────────────────────────────────────────────────────────

@bot.tree.command(name="createtraining", description="[Staff] Create a new training session.")
@app_commands.describe(
    department="The department this training is for.",
    topic="The topic or subject of the training session.",
)
@app_commands.choices(department=DEPARTMENT_CHOICES)
async def createtraining(
    interaction: discord.Interaction,
    department: str,
    topic: str,
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    training_id = generate_training_id()
    created_at  = now_iso()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO trainings (training_id, host_id, department, topic, created_at) VALUES (?, ?, ?, ?, ?)",
        (training_id, interaction.user.id, department, topic, created_at),
    )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Training Created",
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=f"{INFO} Training ID",  value=f"`{training_id}`", inline=True)
    embed.add_field(name=f"{INFO} Department",   value=department,          inline=True)
    embed.add_field(name=f"{ACTION} Topic",      value=topic,               inline=False)
    embed.add_field(name=f"{SCHEDULE} Host",     value=interaction.user.mention, inline=True)
    embed.add_field(name=f"{SCHEDULE} Created",  value=f"<t:{now_ts()}:F>", inline=True)

    await interaction.response.send_message(embed=embed)
    await send_log(
        interaction.guild,
        log_embed(
            "Training Created",
            interaction.user,
            discord.Colour.blue(),
            **{"Training ID": f"`{training_id}`", "Department": department, "Topic": topic},
        ),
    )


# /jointime ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="jointime", description="[Staff] Record a member's join time for a training session.")
@app_commands.describe(
    training_id="The NTA training session ID.",
    member="The member who joined the training.",
)
async def jointime(
    interaction: discord.Interaction,
    training_id: str,
    member: discord.Member,
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{INFO} Training `{training_id}` not found.", ephemeral=True
        )
        con.close()
        return
    if row[0]:
        await interaction.response.send_message(
            f"{INFO} Training `{training_id}` has been cancelled.", ephemeral=True
        )
        con.close()
        return

    join_time = now_iso()
    cur.execute(
        "INSERT INTO training_logs (training_id, user_id, status, join_time) VALUES (?, ?, ?, ?)",
        (training_id, member.id, "ATTENDED", join_time),
    )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Join Time Recorded",
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=f"{INFO} Training ID", value=f"`{training_id}`",   inline=True)
    embed.add_field(name=f"{INFO} Member",       value=member.mention,       inline=True)
    embed.add_field(name=f"{SCHEDULE} Join Time", value=f"<t:{now_ts()}:F>", inline=True)

    await interaction.response.send_message(embed=embed)
    await send_log(
        interaction.guild,
        log_embed(
            "Join Time Recorded",
            interaction.user,
            discord.Colour.blue(),
            **{"Training ID": f"`{training_id}`", "Member": member.mention, "Join Time": f"<t:{now_ts()}:F>"},
        ),
    )


# /logtraining ────────────────────────────────────────────────────────────────

@bot.tree.command(name="logtraining", description="[Staff] Log a member's attendance status for a training session.")
@app_commands.describe(
    training_id="The NTA training session ID.",
    member="The member to log.",
    status="Attendance status.",
)
@app_commands.choices(status=TRAINING_STATUS_CHOICES)
async def logtraining(
    interaction: discord.Interaction,
    training_id: str,
    member: discord.Member,
    status: str,
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{INFO} Training `{training_id}` not found.", ephemeral=True
        )
        con.close()
        return
    if row[1]:
        await interaction.response.send_message(
            f"{INFO} Training `{training_id}` has been cancelled.", ephemeral=True
        )
        con.close()
        return

    topic = row[0]
    logged_at = now_iso()

    # Upsert: update existing log entry if one already exists for this member/training
    cur.execute(
        "SELECT id FROM training_logs WHERE training_id = ? AND user_id = ?",
        (training_id, member.id),
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE training_logs SET status = ?, join_time = ? WHERE id = ?",
            (status, logged_at, existing[0]),
        )
    else:
        cur.execute(
            "INSERT INTO training_logs (training_id, user_id, status, join_time) VALUES (?, ?, ?, ?)",
            (training_id, member.id, status, logged_at),
        )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Training Log",
        colour=discord.Colour.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=f"{INFO} Training ID", value=f"`{training_id}`", inline=True)
    embed.add_field(name=f"{ACTION} Topic",     value=topic,               inline=True)
    embed.add_field(name=f"{INFO} Member",       value=member.mention,     inline=True)
    embed.add_field(name=f"{TICK} Status",       value=f"**{status}**",    inline=True)

    await interaction.response.send_message(embed=embed)
    await send_log(
        interaction.guild,
        log_embed(
            "Training Logged",
            interaction.user,
            discord.Colour.orange(),
            **{"Training ID": f"`{training_id}`", "Topic": topic, "Member": member.mention, "Status": f"**{status}**"},
        ),
    )


# /logexam ────────────────────────────────────────────────────────────────────

@bot.tree.command(name="logexam", description="[Staff] Log an exam result for a member.")
@app_commands.describe(
    member="The member who took the exam.",
    exam_name="The name of the exam.",
    outcome="The exam outcome.",
    notes="Optional notes about the exam.",
)
@app_commands.choices(exam_name=EXAM_NAME_CHOICES, outcome=EXAM_OUTCOME_CHOICES)
async def logexam(
    interaction: discord.Interaction,
    member: discord.Member,
    exam_name: str,
    outcome: str,
    notes: str = "",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    logged_at = now_iso()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO exam_logs (user_id, examiner_id, exam_name, outcome, notes, logged_at) VALUES (?, ?, ?, ?, ?, ?)",
        (member.id, interaction.user.id, exam_name, outcome, notes or None, logged_at),
    )
    con.commit()
    con.close()

    colour = discord.Colour.green() if outcome == "PASSED" else discord.Colour.red()
    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Exam Log",
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=f"{INFO} Member",       value=member.mention,      inline=True)
    embed.add_field(name=f"{ACTION} Exam",       value=exam_name,           inline=True)
    embed.add_field(name=f"{TICK} Outcome",      value=f"**{outcome}**",    inline=True)
    embed.add_field(name=f"{INFO} Examiner",     value=interaction.user.mention, inline=True)
    if notes:
        embed.add_field(name=f"{INFO} Notes",    value=notes,               inline=False)

    await interaction.response.send_message(embed=embed)
    await send_log(
        interaction.guild,
        log_embed(
            "Exam Logged",
            interaction.user,
            colour,
            Member=member.mention,
            Exam=exam_name,
            Outcome=f"**{outcome}**",
            **({"Notes": notes} if notes else {}),
        ),
    )


# /result ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="result", description="[Staff] Send an exam result DM and optionally kick on failure.")
@app_commands.describe(
    member="The member to notify.",
    exam_name="The name of the exam.",
    outcome="The exam outcome.",
    kick_on_fail="Kick the member from the server if they failed (default: False).",
    notes="Optional notes to include in the DM.",
)
@app_commands.choices(exam_name=EXAM_NAME_CHOICES, outcome=EXAM_OUTCOME_CHOICES)
async def result(
    interaction: discord.Interaction,
    member: discord.Member,
    exam_name: str,
    outcome: str,
    kick_on_fail: bool = False,
    notes: str = "",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    # Build DM embed
    dm_colour = discord.Colour.green() if outcome == "PASSED" else discord.Colour.red()
    dm_embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Exam Result",
        colour=dm_colour,
        timestamp=datetime.now(timezone.utc),
    )
    if outcome == "PASSED":
        dm_embed.description = (
            f"{TICK} Congratulations! You have **PASSED** the **{exam_name}**.\n"
            "Well done on your achievement — keep up the great work!"
        )
    else:
        dm_embed.description = (
            f"Unfortunately, you have **FAILED** the **{exam_name}**.\n"
            "You are welcome to review the material and re-apply when ready."
        )
    if notes:
        dm_embed.add_field(name=f"{INFO} Examiner Notes", value=notes, inline=False)
    dm_embed.set_footer(text="Norse Academy")

    # Attempt to DM the member
    dm_sent = True
    try:
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        dm_sent = False

    # Kick on failure if requested
    kicked = False
    if outcome == "FAILED" and kick_on_fail:
        try:
            await member.kick(reason=f"Failed Norse Academy exam: {exam_name}.")
            kicked = True
        except discord.Forbidden:
            pass

    status_parts = ["DM sent ✅" if dm_sent else "DM failed (DMs disabled) ⚠️"]
    if kick_on_fail:
        status_parts.append("Member kicked ✅" if kicked else "Kick failed (missing permissions) ⚠️")

    response_embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Result Sent",
        description=f"Result **{outcome}** processed for {member.mention}.\n" + " | ".join(status_parts),
        colour=dm_colour,
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=response_embed, ephemeral=True)
    await send_log(
        interaction.guild,
        log_embed(
            "Exam Result Sent",
            interaction.user,
            dm_colour,
            Member=member.mention,
            Exam=exam_name,
            Outcome=f"**{outcome}**",
            Kicked="Yes" if kicked else "No",
            **({"Notes": notes} if notes else {}),
        ),
    )


# /dm ─────────────────────────────────────────────────────────────────────────

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
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    dm_embed = discord.Embed(
        title=f"{LOGO} Message from Norse Academy Staff",
        description=message,
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    dm_embed.set_footer(text="Norse Academy")

    sent = True
    try:
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        sent = False

    if sent:
        await interaction.response.send_message(
            f"{TICK} Message sent to {member.mention}.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"⚠️ Could not send a DM to {member.mention} (they may have DMs disabled).", ephemeral=True
        )

    await send_log(
        interaction.guild,
        log_embed(
            "Staff DM Sent",
            interaction.user,
            discord.Colour.gold(),
            Recipient=member.mention,
            Message=message,
            Delivered="Yes" if sent else "No",
        ),
    )


# /canceltraining ─────────────────────────────────────────────────────────────

@bot.tree.command(name="canceltraining", description="[Staff] Cancel an existing training session.")
@app_commands.describe(
    training_id="The NTA training session ID to cancel.",
    reason="The reason for cancelling the training.",
)
async def canceltraining(
    interaction: discord.Interaction,
    training_id: str,
    reason: str = "No reason provided.",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{INFO} Training `{training_id}` not found.", ephemeral=True
        )
        con.close()
        return
    if row[1]:
        await interaction.response.send_message(
            f"{INFO} Training `{training_id}` is already cancelled.", ephemeral=True
        )
        con.close()
        return

    topic = row[0]
    cur.execute(
        "UPDATE trainings SET cancelled = 1, cancel_reason = ? WHERE training_id = ?",
        (reason, training_id),
    )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{LOGO} Norse Academy — Training Cancelled",
        colour=discord.Colour.red(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=f"{INFO} Training ID", value=f"`{training_id}`", inline=True)
    embed.add_field(name=f"{ACTION} Topic",     value=topic,               inline=True)
    embed.add_field(name=f"{INFO} Reason",      value=reason,              inline=False)

    await interaction.response.send_message(embed=embed)
    await send_log(
        interaction.guild,
        log_embed(
            "Training Cancelled",
            interaction.user,
            discord.Colour.red(),
            **{"Training ID": f"`{training_id}`", "Topic": topic, "Reason": reason},
        ),
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")
    bot.run(TOKEN)

