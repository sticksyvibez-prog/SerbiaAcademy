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
STAFF_ROLE_ID  = 1500972974155632762   # Role ID required for staff commands
LOG_CHANNEL_ID = 1513062138254594069   # Channel ID where actions are logged

# ── Custom emoji constants ────────────────────────────────────────────────────
EMOJI_TAIL     = "<:tail:1318259959239766046>"
EMOJI_INFO     = "<:info:1318259957512437871>"
EMOJI_ACTION   = "<:action:1318259955357638768>"
EMOJI_SCHEDULE = "<:schedule:1318259953102041218>"
EMOJI_TICK     = "<:tick:1318259950756560967>"
EMOJI_ROBLOX   = "<:roblox:1318259948316758106>"
EMOJI_LOGO     = "<:logo:1318259945876574330>"

# ── Database initialisation ───────────────────────────────────────────────────
DB_PATH = "norse_academy.db"


def init_db() -> None:
    """Create all required tables if they do not already exist."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT    NOT NULL,
            department    TEXT    NOT NULL DEFAULT 'General',
            phase         INTEGER NOT NULL DEFAULT 1,
            registered_at TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            training_id TEXT    PRIMARY KEY,
            host_id     INTEGER NOT NULL,
            department  TEXT    NOT NULL DEFAULT 'General',
            topic       TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            cancelled   INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id TEXT    NOT NULL,
            user_id     INTEGER NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'ATTENDED',
            logged_at   TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            examiner_id INTEGER NOT NULL,
            exam_name   TEXT    NOT NULL DEFAULT 'General Exam',
            outcome     TEXT    NOT NULL,
            notes       TEXT,
            logged_at   TEXT    NOT NULL
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


async def send_log(guild: discord.Guild, embed: discord.Embed) -> None:
    """Post an embed to the designated log channel by ID, if it exists."""
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def format_dt(iso: str) -> str:
    """Return a short YYYY-MM-DD date string from an ISO-8601 timestamp."""
    return iso[:10]


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
@app_commands.choices(department=[
    app_commands.Choice(name="General",          value="General"),
    app_commands.Choice(name="Security",         value="Security"),
    app_commands.Choice(name="Medical",          value="Medical"),
    app_commands.Choice(name="Engineering",      value="Engineering"),
    app_commands.Choice(name="Command",          value="Command"),
])
async def register(interaction: discord.Interaction, department: str = "General") -> None:
    user = interaction.user
    con  = sqlite3.connect(DB_PATH)
    cur  = con.cursor()

    cur.execute("SELECT user_id FROM registrations WHERE user_id = ?", (user.id,))
    if cur.fetchone():
        await interaction.response.send_message(
            f"{EMOJI_INFO} You are already registered with the Norse Academy.", ephemeral=True
        )
        con.close()
        return

    ts = now_iso()
    cur.execute(
        "INSERT INTO registrations (user_id, username, department, phase, registered_at) VALUES (?, ?, ?, ?, ?)",
        (user.id, str(user), department, 1, ts),
    )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{EMOJI_LOGO} Norse Academy — Registration",
        description=(
            f"{EMOJI_TICK} Welcome, {user.mention}! You have been successfully registered.\n\n"
            f"{EMOJI_INFO} **Department:** {department}\n"
            f"{EMOJI_SCHEDULE} **Phase:** 1\n"
            f"{EMOJI_SCHEDULE} **Registered:** {format_dt(ts)}"
        ),
        colour=discord.Colour.gold(),
    )
    await interaction.response.send_message(embed=embed)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} Register",
        description=f"{user.mention} (`{user.id}`) registered for **{department}**.",
        colour=discord.Colour.green(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(user))
    await send_log(interaction.guild, log_embed)


# /progress ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="progress", description="Check your training and exam progress.")
@app_commands.describe(member="Member to look up (defaults to yourself).")
async def progress(
    interaction: discord.Interaction,
    member: discord.Member = None,
) -> None:
    target = member or interaction.user
    con    = sqlite3.connect(DB_PATH)
    cur    = con.cursor()

    cur.execute(
        "SELECT username, department, phase, registered_at FROM registrations WHERE user_id = ?",
        (target.id,),
    )
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{EMOJI_INFO} {'You are' if target == interaction.user else f'{target.mention} is'} "
            f"not registered. Use `/register` first.",
            ephemeral=True,
        )
        con.close()
        return

    username, department, phase, registered_at = row

    cur.execute(
        "SELECT training_id, status, logged_at FROM training_logs WHERE user_id = ? ORDER BY logged_at DESC",
        (target.id,),
    )
    training_rows = cur.fetchall()

    cur.execute(
        "SELECT exam_name, outcome, logged_at FROM exam_logs WHERE user_id = ? ORDER BY logged_at DESC",
        (target.id,),
    )
    exam_rows = cur.fetchall()
    con.close()

    embed = discord.Embed(
        title=f"{EMOJI_LOGO} Norse Academy — Progress",
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=str(target), icon_url=target.display_avatar.url)
    embed.add_field(name=f"{EMOJI_INFO} Department",   value=department,        inline=True)
    embed.add_field(name=f"{EMOJI_INFO} Phase",        value=str(phase),        inline=True)
    embed.add_field(name=f"{EMOJI_SCHEDULE} Registered", value=format_dt(registered_at), inline=True)

    if training_rows:
        lines = [
            f"`{i}.` `{r[0]}` — **{r[1]}** ({format_dt(r[2])})"
            for i, r in enumerate(training_rows, start=1)
        ]
        embed.add_field(
            name=f"{EMOJI_ACTION} Training Records ({len(training_rows)})",
            value="\n".join(lines[:10]) + ("\n…and more" if len(lines) > 10 else ""),
            inline=False,
        )
    else:
        embed.add_field(name=f"{EMOJI_ACTION} Training Records", value="No training records yet.", inline=False)

    if exam_rows:
        lines = [
            f"`{i}.` **{r[0]}** — {r[1]} ({format_dt(r[2])})"
            for i, r in enumerate(exam_rows, start=1)
        ]
        embed.add_field(
            name=f"{EMOJI_ROBLOX} Exam Records ({len(exam_rows)})",
            value="\n".join(lines[:10]) + ("\n…and more" if len(lines) > 10 else ""),
            inline=False,
        )
    else:
        embed.add_field(name=f"{EMOJI_ROBLOX} Exam Records", value="No exam records yet.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# /createtraining ─────────────────────────────────────────────────────────────

@bot.tree.command(name="createtraining", description="[Staff] Create a new training session.")
@app_commands.describe(
    topic="The topic or subject of the training session.",
    department="The department this training is for.",
)
@app_commands.choices(department=[
    app_commands.Choice(name="General",     value="General"),
    app_commands.Choice(name="Security",    value="Security"),
    app_commands.Choice(name="Medical",     value="Medical"),
    app_commands.Choice(name="Engineering", value="Engineering"),
    app_commands.Choice(name="Command",     value="Command"),
])
async def createtraining(
    interaction: discord.Interaction,
    topic: str,
    department: str = "General",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    training_id = generate_training_id()
    ts = now_iso()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO trainings (training_id, host_id, department, topic, created_at) VALUES (?, ?, ?, ?, ?)",
        (training_id, interaction.user.id, department, topic, ts),
    )
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{EMOJI_SCHEDULE} Training Session Created",
        description=(
            f"{EMOJI_TICK} A new training session has been scheduled.\n\n"
            f"{EMOJI_INFO} **Training ID:** `{training_id}`\n"
            f"{EMOJI_ACTION} **Topic:** {topic}\n"
            f"{EMOJI_LOGO} **Department:** {department}\n"
            f"{EMOJI_SCHEDULE} **Created:** {format_dt(ts)}\n"
            f"{EMOJI_TAIL} **Host:** {interaction.user.mention}"
        ),
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=embed)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} CreateTraining",
        description=(
            f"{interaction.user.mention} created training `{training_id}`.\n"
            f"**Topic:** {topic} | **Department:** {department}"
        ),
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(interaction.user))
    await send_log(interaction.guild, log_embed)


# /jointime ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="jointime", description="[Staff] Record a member's join time for a training session.")
@app_commands.describe(
    training_id="The training session ID.",
    member="The member who joined the training.",
    channel="The voice channel the member joined (optional).",
    role="A role to temporarily assign the member (optional).",
)
async def jointime(
    interaction: discord.Interaction,
    training_id: str,
    member: discord.Member,
    channel: discord.VoiceChannel = None,
    role: discord.Role = None,
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Training `{training_id}` not found.", ephemeral=True
        )
        con.close()
        return
    if row[1]:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Training `{training_id}` has been cancelled.", ephemeral=True
        )
        con.close()
        return

    ts = now_iso()
    cur.execute(
        "INSERT INTO training_logs (training_id, user_id, status, logged_at) VALUES (?, ?, ?, ?)",
        (training_id, member.id, "ATTENDED", ts),
    )
    con.commit()
    con.close()

    # Optionally assign role
    role_note = ""
    if role:
        try:
            await member.add_roles(role, reason=f"Training {training_id} join")
            role_note = f"\n{EMOJI_TICK} Assigned role **{role.name}**."
        except discord.Forbidden:
            role_note = f"\n{EMOJI_INFO} Could not assign role **{role.name}** (missing permissions)."

    channel_note = f"\n{EMOJI_SCHEDULE} Channel: {channel.mention}" if channel else ""

    embed = discord.Embed(
        title=f"{EMOJI_TICK} Join Time Recorded",
        description=(
            f"{member.mention} has been recorded for training `{training_id}`.\n"
            f"{EMOJI_INFO} **Topic:** {row[0]}\n"
            f"{EMOJI_SCHEDULE} **Time:** {format_dt(ts)}"
            f"{channel_note}{role_note}"
        ),
        colour=discord.Colour.green(),
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=embed)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} JoinTime",
        description=(
            f"{member.mention} joined training `{training_id}` at {ts}."
            + (f" | Channel: {channel.mention}" if channel else "")
            + (f" | Role: **{role.name}**" if role else "")
        ),
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=f"Recorded by {interaction.user}")
    await send_log(interaction.guild, log_embed)


# /logtraining ────────────────────────────────────────────────────────────────

@bot.tree.command(name="logtraining", description="[Staff] Log a training attendance record for a member.")
@app_commands.describe(
    training_id="The training session ID.",
    member="The member to log.",
    status="Attendance status for this member.",
)
@app_commands.choices(status=[
    app_commands.Choice(name="Attended", value="ATTENDED"),
    app_commands.Choice(name="Absent",   value="ABSENT"),
    app_commands.Choice(name="Failed",   value="FAILED"),
])
async def logtraining(
    interaction: discord.Interaction,
    training_id: str,
    member: discord.Member,
    status: str = "ATTENDED",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Training `{training_id}` not found.", ephemeral=True
        )
        con.close()
        return
    if row[1]:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Training `{training_id}` has been cancelled.", ephemeral=True
        )
        con.close()
        return

    ts = now_iso()
    cur.execute(
        "INSERT INTO training_logs (training_id, user_id, status, logged_at) VALUES (?, ?, ?, ?)",
        (training_id, member.id, status, ts),
    )
    con.commit()

    cur.execute("SELECT COUNT(*) FROM training_logs WHERE training_id = ?", (training_id,))
    total = cur.fetchone()[0]
    con.close()

    status_emoji = {
        "ATTENDED": EMOJI_TICK,
        "ABSENT":   EMOJI_INFO,
        "FAILED":   EMOJI_ACTION,
    }.get(status, EMOJI_INFO)

    embed = discord.Embed(
        title=f"{EMOJI_ACTION} Training Logged",
        description=(
            f"{status_emoji} **{member.mention}** logged as **{status}** for training `{training_id}`.\n"
            f"{EMOJI_INFO} **Topic:** {row[0]}\n"
            f"{EMOJI_SCHEDULE} **Total records for this session:** {total}"
        ),
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=embed)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} LogTraining",
        description=(
            f"{interaction.user.mention} logged {member.mention} as **{status}** "
            f"for training `{training_id}` (*{row[0]}*)."
        ),
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(interaction.user))
    await send_log(interaction.guild, log_embed)


# /logexam ────────────────────────────────────────────────────────────────────

@bot.tree.command(name="logexam", description="[Staff] Log an exam result for a member.")
@app_commands.describe(
    member="The member who took the exam.",
    exam_name="The name or type of the exam.",
    outcome="The exam outcome.",
    notes="Optional notes about the exam.",
)
@app_commands.choices(
    exam_name=[
        app_commands.Choice(name="Phase 1 Exam",   value="Phase 1 Exam"),
        app_commands.Choice(name="Phase 2 Exam",   value="Phase 2 Exam"),
        app_commands.Choice(name="Phase 3 Exam",   value="Phase 3 Exam"),
        app_commands.Choice(name="Final Exam",     value="Final Exam"),
        app_commands.Choice(name="General Exam",   value="General Exam"),
    ],
    outcome=[
        app_commands.Choice(name="Pass",       value="PASS"),
        app_commands.Choice(name="Fail",       value="FAIL"),
        app_commands.Choice(name="Incomplete", value="INCOMPLETE"),
    ],
)
async def logexam(
    interaction: discord.Interaction,
    member: discord.Member,
    exam_name: str,
    outcome: str,
    notes: str = "",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    ts = now_iso()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO exam_logs (user_id, examiner_id, exam_name, outcome, notes, logged_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (member.id, interaction.user.id, exam_name, outcome, notes or None, ts),
    )
    con.commit()
    con.close()

    outcome_emoji = EMOJI_TICK if outcome == "PASS" else (EMOJI_ACTION if outcome == "FAIL" else EMOJI_INFO)

    embed = discord.Embed(
        title=f"{EMOJI_ROBLOX} Exam Result Logged",
        description=(
            f"{outcome_emoji} **{member.mention}** — **{outcome}** on *{exam_name}*.\n"
            f"{EMOJI_SCHEDULE} **Date:** {format_dt(ts)}"
            + (f"\n{EMOJI_INFO} **Notes:** {notes}" if notes else "")
        ),
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=embed)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} LogExam",
        description=(
            f"{interaction.user.mention} logged **{outcome}** for {member.mention} on *{exam_name}*."
            + (f" Notes: *{notes}*" if notes else "")
        ),
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(interaction.user))
    await send_log(interaction.guild, log_embed)


# /result ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="result", description="[Staff] Send an exam result DM and optionally kick on failure.")
@app_commands.describe(
    member="The member to notify.",
    exam_name="The name or type of the exam.",
    outcome="The exam outcome.",
    kick_on_fail="Kick the member from the server if they failed (default: False).",
    notes="Optional notes to include in the DM.",
)
@app_commands.choices(
    exam_name=[
        app_commands.Choice(name="Phase 1 Exam", value="Phase 1 Exam"),
        app_commands.Choice(name="Phase 2 Exam", value="Phase 2 Exam"),
        app_commands.Choice(name="Phase 3 Exam", value="Phase 3 Exam"),
        app_commands.Choice(name="Final Exam",   value="Final Exam"),
        app_commands.Choice(name="General Exam", value="General Exam"),
    ],
    outcome=[
        app_commands.Choice(name="Pass",       value="PASS"),
        app_commands.Choice(name="Fail",       value="FAIL"),
        app_commands.Choice(name="Incomplete", value="INCOMPLETE"),
    ],
)
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
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    # Build DM embed
    if outcome == "PASS":
        dm_colour  = discord.Colour.green()
        dm_heading = f"{EMOJI_TICK} You have **passed** your *{exam_name}*!"
        dm_body    = "Congratulations — keep up the excellent work within the Norse Academy."
    elif outcome == "FAIL":
        dm_colour  = discord.Colour.red()
        dm_heading = f"{EMOJI_ACTION} You have **not passed** your *{exam_name}*."
        dm_body    = "You are welcome to re-apply after reviewing the material. Don't give up!"
    else:
        dm_colour  = discord.Colour.orange()
        dm_heading = f"{EMOJI_INFO} Your *{exam_name}* has been marked as **Incomplete**."
        dm_body    = "Please speak to a member of staff to arrange a follow-up."

    dm_embed = discord.Embed(
        title=f"{EMOJI_LOGO} Norse Academy — Exam Result",
        description=f"{dm_heading}\n\n{dm_body}"
        + (f"\n\n{EMOJI_INFO} **Examiner notes:** {notes}" if notes else ""),
        colour=dm_colour,
    )
    dm_embed.set_footer(text="Norse Academy")

    # Attempt to DM the member
    dm_sent = True
    try:
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        dm_sent = False

    # Kick on failure if requested
    kicked = False
    if outcome == "FAIL" and kick_on_fail:
        try:
            await member.kick(reason=f"Failed {exam_name}.")
            kicked = True
        except discord.Forbidden:
            pass

    status_lines = [
        f"{EMOJI_TICK if dm_sent else EMOJI_INFO} DM {'sent' if dm_sent else 'failed (DMs disabled)'}."
    ]
    if kick_on_fail:
        status_lines.append(
            f"{EMOJI_TICK if kicked else EMOJI_INFO} Member {'kicked' if kicked else 'kick failed (missing permissions)'}."
        )

    response_embed = discord.Embed(
        title=f"{EMOJI_ROBLOX} Result Processed",
        description=(
            f"Outcome **{outcome}** for {member.mention} on *{exam_name}*.\n\n"
            + "\n".join(status_lines)
        ),
        colour=discord.Colour.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=response_embed, ephemeral=True)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} Result",
        description=(
            f"{interaction.user.mention} sent **{outcome}** result to {member.mention} for *{exam_name}*."
            + (" Kicked." if kicked else "")
            + (f" Notes: *{notes}*" if notes else "")
        ),
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(interaction.user))
    await send_log(interaction.guild, log_embed)


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
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    dm_embed = discord.Embed(
        title=f"{EMOJI_LOGO} Message from Norse Academy Staff",
        description=message,
        colour=discord.Colour.gold(),
    )
    dm_embed.set_footer(text="Norse Academy")

    sent = True
    try:
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        sent = False

    if sent:
        await interaction.response.send_message(
            f"{EMOJI_TICK} Message sent to {member.mention}.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Could not send a DM to {member.mention} — they may have DMs disabled.",
            ephemeral=True,
        )

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} DM",
        description=f"{interaction.user.mention} sent a DM to {member.mention}:\n> {message}",
        colour=discord.Colour.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(interaction.user))
    await send_log(interaction.guild, log_embed)


# /canceltraining ─────────────────────────────────────────────────────────────

@bot.tree.command(name="canceltraining", description="[Staff] Cancel an existing training session.")
@app_commands.describe(
    training_id="The training session ID to cancel.",
    reason="Optional reason for the cancellation.",
)
async def canceltraining(
    interaction: discord.Interaction,
    training_id: str,
    reason: str = "",
) -> None:
    if not is_staff(interaction.user):
        await interaction.response.send_message(
            f"{EMOJI_INFO} You do not have permission to use this command.", ephemeral=True
        )
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT topic, department, cancelled FROM trainings WHERE training_id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Training `{training_id}` not found.", ephemeral=True
        )
        con.close()
        return
    if row[2]:
        await interaction.response.send_message(
            f"{EMOJI_INFO} Training `{training_id}` is already cancelled.", ephemeral=True
        )
        con.close()
        return

    cur.execute("UPDATE trainings SET cancelled = 1 WHERE training_id = ?", (training_id,))
    con.commit()
    con.close()

    embed = discord.Embed(
        title=f"{EMOJI_ACTION} Training Cancelled",
        description=(
            f"Training `{training_id}` has been cancelled.\n\n"
            f"{EMOJI_INFO} **Topic:** {row[0]}\n"
            f"{EMOJI_LOGO} **Department:** {row[1]}"
            + (f"\n{EMOJI_TAIL} **Reason:** {reason}" if reason else "")
        ),
        colour=discord.Colour.red(),
        timestamp=datetime.now(timezone.utc),
    )
    await interaction.response.send_message(embed=embed)

    log_embed = discord.Embed(
        title=f"{EMOJI_ACTION} CancelTraining",
        description=(
            f"{interaction.user.mention} cancelled training `{training_id}` (*{row[0]}*)."
            + (f" Reason: *{reason}*" if reason else "")
        ),
        colour=discord.Colour.red(),
        timestamp=datetime.now(timezone.utc),
    )
    log_embed.set_footer(text=str(interaction.user))
    await send_log(interaction.guild, log_embed)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")
    bot.run(TOKEN)

