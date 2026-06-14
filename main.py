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

AIR_SERBIA_BLUE = 0x0033A0

TRAINER_ROLE_ID = 1512023301457973280
TRAINEE_ROLE_ID = 1512023301445259316

CABIN_CREW_ROLE_ID = 1512023301432541295
GROUND_CREW_ROLE_ID = 1512023301432541294
FLIGHT_DECK_ROLE_ID = 1512023301432541292
HEALTH_SAFETY_ROLE_ID = 1512023301432541293

REGISTRATION_REVIEW_CHANNEL_ID = 1515685364860325999
LOG_CHANNEL_ID = 1515686645477937272

AIR_SERBIA_TAIL = "<:airserbiatail:1513465478918438942>"
AIR_SERBIA_LOGO = "<:airserbialogo:1513461621417054300>"
ARROW = "<:institutearrow:1513466776212738119>"
DOT = "<:institutedot:1513466696118177792>"
I1 = "<:institute1:1513466762652418069>"
I2 = "<:institute2:1513466746265145445>"
I3 = "<:institute3:1513466731627286538>"
I4 = "<:institute4:1513466717035298907>"
I8 = "<:institute8:1512762370383020122>"
I10 = "<:institute10:1512762340653924433>"
I13 = "<:institute13:1512762266271879249>"
I16 = "<:institute16:1512762179483336724>"
I17 = "<:institute17:1512762153382318161>"
BLANK = "<:blank:1513461587132944415>"
ASLOGO = "<:ASlogo:1497713214417535056>"

DEPARTMENT_ROLES = {
    "Cabin Crew Trainee": CABIN_CREW_ROLE_ID,
    "Ground Crew Trainee": GROUND_CREW_ROLE_ID,
    "Flight Deck Trainee": FLIGHT_DECK_ROLE_ID,
    "Health and Safety Department": HEALTH_SAFETY_ROLE_ID,
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect("air_serbia_academy.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_registrations (
    discord_id INTEGER PRIMARY KEY,
    discord_username TEXT,
    roblox_username TEXT,
    roblox_id TEXT,
    department TEXT,
    submitted_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS registrations (
    discord_id INTEGER PRIMARY KEY,
    discord_username TEXT,
    roblox_username TEXT,
    roblox_id TEXT,
    department TEXT,
    registered_at TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS trainings (
    training_id TEXT PRIMARY KEY,
    channel_id INTEGER,
    department_role_id INTEGER,
    course TEXT,
    phase TEXT,
    game_link TEXT,
    date_timestamp TEXT,
    time_timestamp TEXT,
    scheduled_by_id INTEGER,
    scheduled_by_name TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS training_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_id TEXT,
    trainee_id INTEGER,
    trainee_name TEXT,
    course_name TEXT,
    trainer_id INTEGER,
    trainer_name TEXT,
    logged_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS exam_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trainee_id INTEGER,
    trainee_name TEXT,
    exam_type TEXT,
    department TEXT,
    grade TEXT,
    points INTEGER,
    max_points INTEGER,
    percentage REAL,
    outcome TEXT,
    attempt_number INTEGER,
    comments TEXT,
    exam_link TEXT,
    grader_id INTEGER,
    grader_name TEXT,
    logged_at TEXT
)
""")

db.commit()


def is_trainer(member: discord.Member):
    return any(role.id == TRAINER_ROLE_ID for role in member.roles)


def is_trainee(member: discord.Member):
    return any(role.id == TRAINEE_ROLE_ID for role in member.roles)


def make_training_id():
    return "AST-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


async def send_log(guild: discord.Guild, title: str, description: str):
    if not guild:
        return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=AIR_SERBIA_BLUE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Air Serbia Education Institute Logs")
    await channel.send(embed=embed)


def roblox_headshot(roblox_id: str):
    return f"https://www.roblox.com/headshot-thumbnail/image?userId={roblox_id}&width=420&height=420&format=png"


def roblox_profile(roblox_id: str):
    return f"https://www.roblox.com/users/{roblox_id}/profile"


async def send_registration_dm(member: discord.Member):
    msg = f"""> {I13} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲**

You have been **successfully** registered and verified within the Air Serbia Education Institute. We are delighted to welcome you and congratulate you on the beginning of your academy journey.

> {I2} It is **essential** that you review the **[Central Hub](https://discord.com/channels/1512023301420224673/1512023301919084566)** to familiarize yourself with our academy policies, procedures, and regulations before attending any training sessions.

Should you have any questions or require further assistance, please do not hesitate to contact an **Institute Officer**.

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*

{BLANK}{BLANK}{ASLOGO} **Air Serbia** • *13 years of connecting people and creating memories.*
"""
    try:
        await member.send(msg)
    except:
        pass


async def send_rejection_dm(member: discord.Member):
    msg = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Registration Update**

We appreciate your interest in joining the **Air Serbia Education Institute**. After reviewing your registration submission, we regret to inform you that your request has not been approved at this time.

> {ARROW} Should you believe this decision was made in error, or should you require clarification, please contact an **Institute Officer** through the appropriate support channels.

Thank you for your time and interest in the Air Serbia Education Institute.

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""
    try:
        await member.send(msg)
    except:
        pass


class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="asei_register_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_trainer(interaction.user):
            await interaction.response.send_message("You do not have permission to approve registrations.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        discord_id = None

        for field in embed.fields:
            if field.name == "Discord ID":
                discord_id = int(field.value)
                break

        if not discord_id:
            await interaction.response.send_message("Could not find Discord ID in this registration.", ephemeral=True)
            return

        cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (discord_id,))
        data = cursor.fetchone()

        if not data:
            await interaction.response.send_message("This registration is no longer pending.", ephemeral=True)
            return

        discord_id, discord_username, roblox_username, roblox_id, department, submitted_at = data
        member = interaction.guild.get_member(discord_id)

        if not member:
            await interaction.response.send_message("Member not found in this server.", ephemeral=True)
            return

        trainee_role = interaction.guild.get_role(TRAINEE_ROLE_ID)
        department_role = interaction.guild.get_role(DEPARTMENT_ROLES.get(department))

        roles = []
        if trainee_role:
            roles.append(trainee_role)
        if department_role:
            roles.append(department_role)

        if roles:
            await member.add_roles(*roles, reason="Air Serbia Education Institute registration approved")

        today = datetime.now().strftime("%d %B %Y")

        cursor.execute(
            "REPLACE INTO registrations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (discord_id, discord_username, roblox_username, roblox_id, department, today, "Active")
        )
        cursor.execute("DELETE FROM pending_registrations WHERE discord_id = ?", (discord_id,))
        db.commit()

        await send_registration_dm(member)

        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Approved by {interaction.user.mention}", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        await send_log(
            interaction.guild,
            "Registration Approved",
            f"Applicant: {member.mention}\nDepartment: {department}\nApproved By: {interaction.user.mention}"
        )

        await interaction.response.send_message("Registration approved and roles assigned.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="asei_register_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_trainer(interaction.user):
            await interaction.response.send_message("You do not have permission to reject registrations.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        discord_id = None

        for field in embed.fields:
            if field.name == "Discord ID":
                discord_id = int(field.value)
                break

        if not discord_id:
            await interaction.response.send_message("Could not find Discord ID in this registration.", ephemeral=True)
            return

        cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (discord_id,))
        data = cursor.fetchone()

        if data:
            member = interaction.guild.get_member(discord_id)
            cursor.execute("DELETE FROM pending_registrations WHERE discord_id = ?", (discord_id,))
            db.commit()

            if member:
                await send_rejection_dm(member)

        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Rejected by {interaction.user.mention}", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        await send_log(
            interaction.guild,
            "Registration Rejected",
            f"Applicant ID: `{discord_id}`\nRejected By: {interaction.user.mention}"
        )

        await interaction.response.send_message("Registration rejected.", ephemeral=True)


@bot.event
async def on_ready():
    bot.add_view(RegistrationView())
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="register", description="Submit your Air Serbia Education Institute registration.")
@app_commands.choices(department=[
    app_commands.Choice(name="Cabin Crew Trainee", value="Cabin Crew Trainee"),
    app_commands.Choice(name="Ground Crew Trainee", value="Ground Crew Trainee"),
    app_commands.Choice(name="Flight Deck Trainee", value="Flight Deck Trainee"),
    app_commands.Choice(name="Health and Safety Department", value="Health and Safety Department"),
])
async def register(
    interaction: discord.Interaction,
    roblox_username: str,
    roblox_id: str,
    department: app_commands.Choice[str]
):
    trainee_role = interaction.guild.get_role(TRAINEE_ROLE_ID)

    if trainee_role and trainee_role in interaction.user.roles:
        await interaction.response.send_message("You are already registered within the Air Serbia Education Institute.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (interaction.user.id,))
    if cursor.fetchone():
        await interaction.response.send_message("Your registration is already pending review.", ephemeral=True)
        return

    submitted_at = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "REPLACE INTO pending_registrations VALUES (?, ?, ?, ?, ?, ?)",
        (interaction.user.id, str(interaction.user), roblox_username, roblox_id, department.value, submitted_at)
    )
    db.commit()

    review_channel = interaction.guild.get_channel(REGISTRATION_REVIEW_CHANNEL_ID)

    embed = discord.Embed(
        title=f"{AIR_SERBIA_LOGO} Registration Review",
        description="A new member has submitted an Education Institute registration.",
        color=AIR_SERBIA_BLUE,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Applicant", value=interaction.user.mention, inline=False)
    embed.add_field(name="Discord Username", value=str(interaction.user), inline=True)
    embed.add_field(name="Discord ID", value=str(interaction.user.id), inline=True)
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Roblox ID", value=roblox_id, inline=True)
    embed.add_field(name="Department", value=department.value, inline=False)
    embed.set_thumbnail(url=roblox_headshot(roblox_id))
    embed.set_footer(text="Air Serbia Education Institute Registration")

    if review_channel:
        await review_channel.send(embed=embed, view=RegistrationView())

    await interaction.response.send_message(
        "Your registration has been submitted for review. Please wait for an Institute Officer to approve it.",
        ephemeral=True
    )


@bot.tree.command(name="profile", description="View your Air Serbia Education Institute profile.")
async def profile(interaction: discord.Interaction):
    if not is_trainee(interaction.user):
        await interaction.response.send_message("You must complete registration before accessing your academy profile.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (interaction.user.id,))
    reg = cursor.fetchone()

    if not reg:
        await interaction.response.send_message("No academy profile was found for you.", ephemeral=True)
        return

    discord_id, discord_username, roblox_username, roblox_id, department, registered_at, status = reg

    cursor.execute("SELECT course_name, logged_at FROM training_logs WHERE trainee_id = ?", (interaction.user.id,))
    trainings = cursor.fetchall()

    cursor.execute("SELECT exam_type, outcome, percentage, grader_name FROM exam_logs WHERE trainee_id = ?", (interaction.user.id,))
    exams = cursor.fetchall()

    training_text = "\n".join([f"{DOT} {c} • {d}" for c, d in trainings]) or f"{DOT} No training attendance recorded."

    exam_text = "\n".join([f"{DOT} {e[0]} — **{e[1]}** ({round(e[2], 2)}%)" for e in exams]) or f"{DOT} No examination participation recorded."

    latest_examiner = exams[-1][3] if exams else "None"
    latest_grade = "None"

    cursor.execute("SELECT grade FROM exam_logs WHERE trainee_id = ? ORDER BY id DESC LIMIT 1", (interaction.user.id,))
    grade_data = cursor.fetchone()
    if grade_data:
        latest_grade = grade_data[0]

    embed = discord.Embed(
        title=f"{I17} {roblox_username} Profile",
        color=AIR_SERBIA_BLUE,
        timestamp=discord.utils.utcnow()
    )

    embed.set_author(
        name=f"{interaction.user.display_name}'s Academy Profile",
        icon_url=interaction.user.display_avatar.url
    )
    embed.set_thumbnail(url=roblox_headshot(roblox_id))

    embed.description = f"""> {I8} **Training Attendance**
{training_text}

> {I10} **Examination Participation**
{exam_text}

> {I10} **Notes**
{DOT} Department: {department}
{DOT} Registered: {registered_at}
{DOT} Academy Status: {status}
{DOT} Latest Grade: {latest_grade}
{DOT} Latest Examiner: {latest_examiner}

{AIR_SERBIA_TAIL} We wish you the best of luck!

-# [Profile Link]({roblox_profile(roblox_id)})
"""

    embed.set_footer(text="Air Serbia Education Institute")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="scheduletraining", description="Schedule a new course training.")
async def scheduletraining(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    department_role: discord.Role,
    course: str,
    phase: str,
    game_link: str,
    date_timestamp: str,
    time_timestamp: str
):
    if not is_trainer(interaction.user):
        await interaction.response.send_message("You do not have permission to schedule trainings.", ephemeral=True)
        return

    training_id = make_training_id()
    created_at = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "INSERT INTO trainings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            training_id,
            channel.id,
            department_role.id,
            course,
            phase,
            game_link,
            date_timestamp,
            time_timestamp,
            interaction.user.id,
            str(interaction.user),
            created_at
        )
    )
    db.commit()

    message = f"""{department_role.mention}

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Course Schedule**
{BLANK}{BLANK} ◜*a new course training has been scheduled*

*Salutations, trainees!* It gives us pleasure to announce that a new **{course}** training will be taking place at __[Location]({game_link})__.

> {ARROW} In case you are unable to attend this training programme, please ensure that you communicate this to a member of the Institute so that an alternative training session may be arranged according to your timezone.

{BLANK} {I16} **<t:{date_timestamp}:D>, <t:{time_timestamp}:t>**
{DOT} Upon the __unlock__ of the training, you will be provided **10 minutes** to join before the server commences __lock__ and the training proceedings begin.

> ◜*If you wish to attend, please allocate by utilising the appropriate reaction below.*

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""

    sent = await channel.send(message)
    await sent.add_reaction("✅")
    await sent.add_reaction("❌")

    try:
        await interaction.user.send(
            f"{AIR_SERBIA_LOGO} Training successfully scheduled.\n\nTraining ID: `{training_id}`\nCourse: {course}\nPhase: {phase}"
        )
    except:
        pass

    await send_log(
        interaction.guild,
        "Training Scheduled",
        f"Training ID: `{training_id}`\nCourse: {course}\nPhase: {phase}\nScheduled By: {interaction.user}"
    )

    await interaction.response.send_message(f"Training scheduled. Training ID: `{training_id}`", ephemeral=True)


@bot.tree.command(name="jointime", description="Open join time for a scheduled training.")
async def jointime(interaction: discord.Interaction, training_id: str):
    if not is_trainer(interaction.user):
        await interaction.response.send_message("You do not have permission to open join time.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await interaction.response.send_message("Training ID not found.", ephemeral=True)
        return

    training_id, channel_id, department_role_id, course, phase, game_link, date_timestamp, time_timestamp, scheduled_by_id, scheduled_by_name, created_at = data

    channel = interaction.guild.get_channel(channel_id)

    message = f"""<@&{department_role_id}>

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Course Commencement**
{BLANK}{BLANK}◜*we recommend that you review the information below*

> {I16} **All** participants are required to join promptly and ensure full attendance throughout.
{ARROW} **[Join Training]({game_link})**

{DOT} You are provided **10 minutes** to join before the server commences __lock__ and the training proceedings begin.

> {BLANK} *Please remain professional throughout the entirety of the session. Failure to do so may result in disciplinary action.*

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""

    await channel.send(message)

    await send_log(
        interaction.guild,
        "Join Time Opened",
        f"Training ID: `{training_id}`\nOpened By: {interaction.user}"
    )

    await interaction.response.send_message("Join time posted.", ephemeral=True)


@bot.tree.command(name="logtraining", description="Log training attendance for a trainee.")
async def logtraining(
    interaction: discord.Interaction,
    training_id: str,
    trainee: discord.Member,
    course_name: str
):
    if not is_trainer(interaction.user):
        await interaction.response.send_message("You do not have permission to log trainings.", ephemeral=True)
        return

    today = datetime.now().strftime("%d %B %Y")

    cursor.execute(
        "INSERT INTO training_logs (training_id, trainee_id, trainee_name, course_name, trainer_id, trainer_name, logged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            training_id,
            trainee.id,
            str(trainee),
            course_name,
            interaction.user.id,
            str(interaction.user),
            today
        )
    )
    db.commit()

    await send_log(
        interaction.guild,
        "Training Attendance Logged",
        f"Trainee: {trainee.mention}\nCourse: {course_name}\nTraining ID: `{training_id}`\nTrainer: {interaction.user}"
    )

    await interaction.response.send_message("Training attendance logged.", ephemeral=True)


@bot.tree.command(name="result", description="Send examination results to a trainee.")
@app_commands.choices(
    exam_type=[
        app_commands.Choice(name="Theory Examination", value="Theory"),
        app_commands.Choice(name="Course Examination", value="Course")
    ],
    outcome=[
        app_commands.Choice(name="Pass", value="PASSED"),
        app_commands.Choice(name="Fail", value="FAILED")
    ]
)
async def result(
    interaction: discord.Interaction,
    trainee: discord.Member,
    exam_type: app_commands.Choice[str],
    department: str,
    grade: str,
    points: int,
    max_points: int,
    outcome: app_commands.Choice[str],
    attempt_number: int,
    comments: str,
    exam_link: str
):
    if not is_trainer(interaction.user):
        await interaction.response.send_message("You do not have permission to issue results.", ephemeral=True)
        return

    percentage = (points / max_points) * 100
    today = datetime.now().strftime("%d %B %Y")
    grader = str(interaction.user)

    cursor.execute(
        "INSERT INTO exam_logs (trainee_id, trainee_name, exam_type, department, grade, points, max_points, percentage, outcome, attempt_number, comments, exam_link, grader_id, grader_name, logged_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            trainee.id,
            str(trainee),
            exam_type.value,
            department,
            grade,
            points,
            max_points,
            percentage,
            outcome.value,
            attempt_number,
            comments,
            exam_link,
            interaction.user.id,
            grader,
            today
        )
    )
    db.commit()

    if outcome.value == "PASSED" and exam_type.value == "Theory":
        dm = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Results**

{BLANK}{BLANK} ⦧ **Theory Examination Results**

On behalf of the **Air Serbia Instructional Board**, we are delighted to congratulate you on successfully passing your **Theory Examination** within the **{department}**.

> {DOT} **Grade:** {grade}
> {DOT} **Score:** {points}/{max_points} ({round(percentage, 2)}%)
> {DOT} **Attempt:** {attempt_number}
> {DOT} **Graded By:** {grader}

> {ARROW} **Comments:** {comments}

> {I1} Your performance demonstrates a strong understanding of the theoretical knowledge required by the Air Serbia Education Institute. Your academy record has been updated successfully.

We are confident that you will continue to perform to the highest standards throughout your academy journey.

> {I3} **Congratulations** on your accomplishment and continued dedication to the mission of the Air Serbia Education Institute.

{DOT} **[Your Examination]({exam_link})**

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*

{BLANK}{BLANK} __Board of Learning and Teaching__, Institute Headquarters
"""

    elif outcome.value == "PASSED" and exam_type.value == "Course":
        dm = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Results**

{BLANK}{BLANK} ⦧ **Course 1 Results**

On behalf of the **Air Serbia Instructional Board**, we would like to sincerely congratulate you on the successful completion of your **Course 1 Examination**.

> We are pleased to inform you that you have **passed** your **Course 1 Examination**. Congratulations on this outstanding achievement. Below are the official results recorded by your examiner.

> {DOT} **Department:** {department}
> {DOT} **Grade:** {grade}
> {DOT} **Score:** {points}/{max_points} ({round(percentage, 2)}%)
> {DOT} **Attempt:** {attempt_number}
> {DOT} **Graded By:** {grader}

> {ARROW} **Comments:** {comments}

> {I1} This feedback has been provided to support your continued development and assist you in achieving an even higher standard during future evaluations. Your final academy ranking will be assigned shortly and will determine your progression to **Course 2** within your assigned department.

> {ARROW} Successful completion of this course authorizes you to continue your training journey within the Air Serbia Education Institute. Please await further instructions from an **Institute Officer** regarding your progression.

> {I3} **Congratulations** on your accomplishment and your continued dedication to the mission of the Air Serbia Education Institute.

{DOT} **[Your Examination]({exam_link})**

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*

{BLANK}{BLANK} __Board of Learning and Teaching__, Institute Headquarters
"""
    else:
        dm = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Results**
{BLANK}{BLANK} ⦧ *Your Course Examination results*

On behalf of the **Air Serbia Instructional Board**, we regret to inform you that your performance in the Course Examination has __not met the required__ standard for a successful pass.

> After a __thorough evaluation__ of your submitted answers, it has been determined that the minimum criteria necessary for progression have not been fully satisfied at this time.

> {ARROW} **{comments}**

> {I4} This feedback is __intended__ to assist you in identifying areas that require improvement and to support your preparation for any *future attempts*. We **strongly** encourage you to review the training material carefully and focus on strengthening the clarity, completeness, and precision of your responses.

{ARROW} Please be **advised** that your current result does not permit progression to the next stage at this time. Further instructions regarding a possible retake or additional training requirements may be provided by an **Institute Officer** in due course.

> {DOT} **[Your Examination]({exam_link})**

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
{BLANK}{BLANK} __Board of Learning and Teaching__, Institute Headquarters
"""

    try:
        await trainee.send(dm)
    except:
        pass

    if outcome.value == "FAILED" and attempt_number >= 2:
        try:
            await trainee.kick(reason=f"Failed {exam_type.value} Examination on second attempt.")
        except:
            pass

    await send_log(
        interaction.guild,
        "Examination Result Issued",
        f"Trainee: {trainee.mention}\nExam: {exam_type.value}\nDepartment: {department}\nScore: {points}/{max_points} ({round(percentage, 2)}%)\nResult: {outcome.value}\nAttempt: {attempt_number}\nGraded By: {interaction.user}"
    )

    await interaction.response.send_message("Result issued and saved.", ephemeral=True)


@bot.tree.command(name="dm", description="Send an official institute DM to a member.")
async def dm(interaction: discord.Interaction, user: discord.Member, message: str):
    if not is_trainer(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    final = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Official Message**

{message}

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**
> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲**
"""

    try:
        await user.send(final)
    except:
        await interaction.response.send_message("Could not DM this user.", ephemeral=True)
        return

    await send_log(interaction.guild, "Official DM Sent", f"Recipient: {user.mention}\nSent By: {interaction.user}")
    await interaction.response.send_message("DM sent.", ephemeral=True)


bot.run(TOKEN)
