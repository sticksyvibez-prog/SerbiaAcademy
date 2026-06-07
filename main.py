import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import sqlite3
import os
import random
import string
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

STAFF_ROLE_ID = 1500972974155632762
LOG_CHANNEL_ID = 1513062138254594069

TAIL = "<:tailnorse:1513072003513454602>"
INFO = "<:informationnorse:1513072124707999785>"
ACTION = "<:actionnorse:1513072191019810846>"
SCHEDULE = "<:schedulenorse:1513073281492848712>"
TICK = "<:tick:1513073385939275796>"
ROBLOX = "<:robloxnorse:1513073646254686299>"
LOGO = "<:logonorse:1513074690581598218>"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect("norse_academy.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS registrations (
    discord_id INTEGER PRIMARY KEY,
    discord_username TEXT,
    roblox_id TEXT,
    department TEXT,
    registered_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS trainings (
    training_id TEXT PRIMARY KEY,
    department TEXT,
    phase TEXT,
    timestamp TEXT,
    host_id INTEGER,
    host_name TEXT,
    channel_id INTEGER,
    trainee_role_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS training_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_id TEXT,
    trainee_id INTEGER,
    trainee_name TEXT,
    status TEXT,
    notes TEXT,
    logged_by TEXT,
    logged_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS exam_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trainee_id INTEGER,
    trainee_name TEXT,
    exam_name TEXT,
    score TEXT,
    result TEXT,
    examiner TEXT,
    logged_at TEXT
)
""")

db.commit()


def is_staff(member: discord.Member):
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


def make_training_id():
    return "NTA-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


async def send_log(guild: discord.Guild, title: str, content: str):
    if not guild:
        return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"**{title}**\n\n{content}")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="register", description="Register yourself in Academy Core.")
@app_commands.choices(department=[
    app_commands.Choice(name="Cabin Crew Trainee", value="Cabin Crew Trainee"),
    app_commands.Choice(name="Flight Deck Trainee", value="Flight Deck Trainee"),
    app_commands.Choice(name="Ground Crew Trainee", value="Ground Crew Trainee"),
    app_commands.Choice(name="Instructor", value="Instructor"),
    app_commands.Choice(name="Academy Director", value="Academy Director"),
    app_commands.Choice(name="Council Member", value="Council Member"),
])
async def register(
    interaction: discord.Interaction,
    discord_username: str,
    roblox_id: str,
    department: app_commands.Choice[str]
):
    today = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "REPLACE INTO registrations VALUES (?, ?, ?, ?, ?)",
        (
            interaction.user.id,
            discord_username,
            roblox_id,
            department.value,
            today
        )
    )
    db.commit()

    await send_log(
        interaction.guild,
        "NEW REGISTRATION",
        f"User: {interaction.user.mention}\nDiscord Username: {discord_username}\nRoblox ID: {roblox_id}\nDepartment: {department.value}"
    )

    await interaction.response.send_message(
        f"{TAIL} Registration complete. You may now use `/progress`.",
        ephemeral=True
    )


@bot.tree.command(name="progress", description="View your academy progress.")
async def progress(interaction: discord.Interaction):
    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (interaction.user.id,))
    reg = cursor.fetchone()

    if not reg:
        await interaction.response.send_message(
            "You are not registered in the Academy database. Please use `/register` first.",
            ephemeral=True
        )
        return

    cursor.execute("SELECT training_id, status FROM training_logs WHERE trainee_id = ?", (interaction.user.id,))
    trainings = cursor.fetchall()

    cursor.execute("SELECT exam_name, score, result FROM exam_logs WHERE trainee_id = ?", (interaction.user.id,))
    exams = cursor.fetchall()

    training_text = "\n".join(
        [f"{i+1}, `{t[0]}` — **{t[1]}**" for i, t in enumerate(trainings)]
    ) or "No training attended yet."

    exam_text = "\n".join(
        [f"{i+1}, {e[0]} — **{e[2]}** — Score: {e[1]}" for i, e in enumerate(exams)]
    ) or "No exams recorded yet."

    message = f"""** {LOGO} Your Progress**

> Training Attended
{training_text}

> Exams
{exam_text}

{TAIL} We wish you the best of luck!
"""

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="createtraining", description="Create a formatted Norse training announcement.")
@app_commands.describe(
    channel="Channel where the announcement will be posted",
    trainee_role="Role to ping for the training",
    department="Training department",
    phase="Training stage/phase number",
    host="Training host",
    timestamp="Discord timestamp number only, example: 1780759800"
)
@app_commands.choices(department=[
    app_commands.Choice(name="Cabin Crew", value="Cabin Crew"),
    app_commands.Choice(name="Flight Deck", value="Flight Deck"),
    app_commands.Choice(name="Ground Crew", value="Ground Crew"),
    app_commands.Choice(name="Academy Services", value="Academy Services")
])
async def createtraining(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    trainee_role: discord.Role,
    department: app_commands.Choice[str],
    phase: str,
    host: discord.Member,
    timestamp: str
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    training_id = make_training_id()

    message = f"""** {TAIL} Training Session Scheduled**
-# A newly scheduled training session

{trainee_role.mention}

{SCHEDULE} A new **Stage {phase}** training session has been scheduled for **<t:{timestamp}:F>**.

> **Department:** {department.value}
> **Host:** {host.mention}
> **Training ID:** `{training_id}`

{INFO} The training server will unlock at the scheduled time. Trainees are expected to join promptly and follow all instructions issued by the host.

{TICK} Ensure you react below if you are able to attend this session.
"""

    sent = await channel.send(message)
    await sent.add_reaction("✅")

    cursor.execute(
        "INSERT INTO trainings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            training_id,
            department.value,
            phase,
            timestamp,
            host.id,
            str(host),
            channel.id,
            trainee_role.id
        )
    )
    db.commit()

    try:
        await host.send(
            f"{TAIL} Your training has been created.\n\n"
            f"Training ID: `{training_id}`\n"
            f"Department: {department.value}\n"
            f"Stage: {phase}\n"
            f"Time: <t:{timestamp}:F>"
        )
    except:
        pass

    await send_log(
        interaction.guild,
        "TRAINING CREATED",
        f"Training ID: `{training_id}`\nDepartment: {department.value}\nStage: {phase}\nHost: {host.mention}\nCreated By: {interaction.user.mention}\nChannel: {channel.mention}\nPing Role: {trainee_role.mention}"
    )

    await interaction.response.send_message(
        f"Training posted. Training ID: `{training_id}`",
        ephemeral=True
    )


@bot.tree.command(name="jointime", description="Open join time for a training.")
async def jointime(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    trainee_role: discord.Role,
    training_id: str,
    link: str
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await interaction.response.send_message("Training ID not found.", ephemeral=True)
        return

    training_id, department, phase, timestamp, host_id, host_name, old_channel_id, old_role_id = data

    message = f"""** {TAIL} Training Session Open **
-# Join time has officially commenced

{trainee_role.mention}

{INFO} The **Stage {phase}** training session is now accepting attendees.

> **Department:** {department}
> **Host:** <@{host_id}>
> **[Training]({link})**

{ROBLOX} The training server will lock in **5 minutes**. Late arrivals will not be admitted unless authorized by the training host.

-# Please proceed to the training server immediately.
"""

    await channel.send(message)

    await send_log(
        interaction.guild,
        "JOIN TIME OPENED",
        f"Training ID: `{training_id}`\nDepartment: {department}\nStage: {phase}\nOpened By: {interaction.user.mention}\nChannel: {channel.mention}\nPing Role: {trainee_role.mention}"
    )

    await interaction.response.send_message("Join time announcement posted.", ephemeral=True)


@bot.tree.command(name="logtraining", description="Log trainee attendance.")
@app_commands.choices(status=[
    app_commands.Choice(name="Attended", value="ATTENDED"),
    app_commands.Choice(name="Absent", value="ABSENT"),
    app_commands.Choice(name="Failed", value="FAILED"),
])
async def logtraining(
    interaction: discord.Interaction,
    training_id: str,
    trainee: discord.Member,
    status: app_commands.Choice[str],
    notes: str = "No notes provided."
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    training = cursor.fetchone()

    if not training:
        await interaction.response.send_message("Training ID not found.", ephemeral=True)
        return

    today = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "INSERT INTO training_logs (training_id, trainee_id, trainee_name, status, notes, logged_by, logged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            training_id,
            trainee.id,
            str(trainee),
            status.value,
            notes,
            str(interaction.user),
            today
        )
    )
    db.commit()

    await send_log(
        interaction.guild,
        "TRAINING LOGGED",
        f"Training ID: `{training_id}`\nTrainee: {trainee.mention}\nStatus: {status.value}\nLogged By: {interaction.user.mention}\nNotes: {notes}"
    )

    await interaction.response.send_message(f"Training log saved for {trainee.mention}.", ephemeral=True)


@bot.tree.command(name="logexam", description="Log an exam result without DM.")
@app_commands.choices(
    exam_name=[
        app_commands.Choice(name="Theory Examination", value="Theory Examination"),
        app_commands.Choice(name="Universal Examination", value="Universal Examination")
    ],
    outcome=[
        app_commands.Choice(name="Passed", value="PASSED"),
        app_commands.Choice(name="Failed", value="FAILED")
    ]
)
async def logexam(
    interaction: discord.Interaction,
    trainee: discord.Member,
    exam_name: app_commands.Choice[str],
    score: str,
    outcome: app_commands.Choice[str]
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    today = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "INSERT INTO exam_logs (trainee_id, trainee_name, exam_name, score, result, examiner, logged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            trainee.id,
            str(trainee),
            exam_name.value,
            score,
            outcome.value,
            str(interaction.user),
            today
        )
    )
    db.commit()

    await send_log(
        interaction.guild,
        "EXAM LOGGED",
        f"Trainee: {trainee.mention}\nExam: {exam_name.value}\nScore: {score}\nResult: {outcome.value}\nExaminer: {interaction.user.mention}"
    )

    await interaction.response.send_message("Exam log saved.", ephemeral=True)


@bot.tree.command(name="result", description="Send examination result to a trainee.")
@app_commands.choices(
    exam_name=[
        app_commands.Choice(name="Theory Examination", value="Theory Examination"),
        app_commands.Choice(name="Universal Examination", value="Universal Examination")
    ],
    outcome=[
        app_commands.Choice(name="Passed", value="PASSED"),
        app_commands.Choice(name="Failed", value="FAILED")
    ]
)
async def result(
    interaction: discord.Interaction,
    trainee: discord.Member,
    exam_name: app_commands.Choice[str],
    score: str,
    outcome: app_commands.Choice[str]
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    date = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "INSERT INTO exam_logs (trainee_id, trainee_name, exam_name, score, result, examiner, logged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            trainee.id,
            str(trainee),
            exam_name.value,
            score,
            outcome.value,
            str(interaction.user),
            date
        )
    )
    db.commit()

    if outcome.value == "PASSED":
        dm = f"""## {TAIL} Results
-# Your results of {exam_name.value}

NORSE Training Division, {date}

{INFO} Greetings! {trainee.mention},

We hope this message finds you well. This message is here to deliver your results for your **{exam_name.value}**.

{ACTION} Score: {score}
{ACTION} Result: PASSED

Congratulations on successfully completing your examination. Your performance has met the standards required by the NORSE Training Division, and your academy record has been updated accordingly.

We wish you the very best as you continue your progression within Norse Atlantic Airways.

Kind regards,

NORSE Training Division
"""
    else:
        dm = f"""## {TAIL} Results
-# Your results of {exam_name.value}

NORSE Training Division, {date}

{INFO} Greetings! {trainee.mention},

We hope this message finds you well. This message is here to deliver your results for your **{exam_name.value}**. We do not provide feedback in this instance.

{ACTION} Score: {score}
{ACTION} Result: FAILED

You will soon be dismissed from the program for an unsuccessful second attempt of your examination. If you have any questions regarding anything mentioned above, please alert your examiner immediately.

Kind regards,

NORSE Training Division
"""

    try:
        await trainee.send(dm)
    except:
        await interaction.response.send_message("Could not DM the trainee. Result was still saved.", ephemeral=True)
        return

    await send_log(
        interaction.guild,
        "RESULT ISSUED",
        f"Trainee: {trainee.mention}\nExam: {exam_name.value}\nScore: {score}\nResult: {outcome.value}\nExaminer: {interaction.user.mention}"
    )

    if outcome.value == "FAILED":
        try:
            await trainee.kick(reason=f"Failed {exam_name.value}")
        except:
            await interaction.response.send_message(
                "Result sent, but I could not kick the trainee. Check bot permissions.",
                ephemeral=True
            )
            return

    await interaction.response.send_message(
        f"Result sent to {trainee.mention} and added to progress.",
        ephemeral=True
    )


@bot.tree.command(name="dm", description="Send an academy DM through the bot.")
async def dm(
    interaction: discord.Interaction,
    user: discord.Member,
    message: str
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    final_message = f"""** {TAIL} Message from the Academy**

{message}
"""

    try:
        await user.send(final_message)
    except:
        await interaction.response.send_message("Could not DM this user.", ephemeral=True)
        return

    await send_log(
        interaction.guild,
        "ACADEMY DM SENT",
        f"Recipient: {user.mention}\nSent By: {interaction.user.mention}\nMessage:\n{message}"
    )

    await interaction.response.send_message("DM sent successfully.", ephemeral=True)


@bot.tree.command(name="canceltraining", description="Cancel a training session.")
async def canceltraining(
    interaction: discord.Interaction,
    training_id: str,
    reason: str
):
    if not is_staff(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await interaction.response.send_message("Training ID not found.", ephemeral=True)
        return

    training_id, department, phase, timestamp, host_id, host_name, channel_id, trainee_role_id = data
    channel = interaction.guild.get_channel(channel_id)

    if channel:
        await channel.send(
            f"""** {TAIL} Training Session Cancelled**
-# A scheduled training session has been cancelled

<@&{trainee_role_id}>

{INFO} The **Stage {phase}** training session has been cancelled.

> **Department:** {department}
> **Host:** <@{host_id}>
> **Training ID:** `{training_id}`
> **Reason:** {reason}

-# Please await further updates from Academy Services.
"""
        )

    await send_log(
        interaction.guild,
        "TRAINING CANCELLED",
        f"Training ID: `{training_id}`\nDepartment: {department}\nStage: {phase}\nCancelled By: {interaction.user.mention}\nReason: {reason}"
    )

    await interaction.response.send_message("Training cancelled.", ephemeral=True)


bot.run(TOKEN)