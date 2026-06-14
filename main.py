import os
import re
import random
import string
import sqlite3
from datetime import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Add it in Railway Variables.")


# ============================================================
# BRANDING / CONFIG
# ============================================================

BRAND_COLOR = 0xAE998A

TRAINER_ROLE_ID = 1512023301457973280
TRAINEE_ROLE_ID = 1512023301445259316

CABIN_CREW_ROLE_ID = 1512023301432541295
GROUND_CREW_ROLE_ID = 1512023301432541294
FLIGHT_DECK_ROLE_ID = 1512023301432541292
HEALTH_SAFETY_ROLE_ID = 1512023301432541293

REGISTRATION_REVIEW_CHANNEL_ID = 1515685364860325999
LOG_CHANNEL_ID = 1515686645477937272
GUILD_ID = 1512023301420224673

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
I14 = "<:institute14:1512762250124070972>"  # Cross
I15 = "<:institute15:1512762236018622545>"  # Tick
I16 = "<:institute16:1512762179483336724>"
I17 = "<:institute17:1512762153382318161>"

BLANK = "<:blank:1513461587132944415>"

DEPARTMENT_ROLES = {
    "Cabin Crew Trainee": CABIN_CREW_ROLE_ID,
    "Ground Crew Trainee": GROUND_CREW_ROLE_ID,
    "Flight Deck Trainee": FLIGHT_DECK_ROLE_ID,
    "Health and Safety Department": HEALTH_SAFETY_ROLE_ID,
}

INSTITUTE_ROLE_IDS = {
    TRAINER_ROLE_ID,
    TRAINEE_ROLE_ID,
    CABIN_CREW_ROLE_ID,
    GROUND_CREW_ROLE_ID,
    FLIGHT_DECK_ROLE_ID,
    HEALTH_SAFETY_ROLE_ID,
}


# ============================================================
# DISCORD SETUP
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect("institute_core_v2.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_registrations (
    discord_id INTEGER PRIMARY KEY,
    discord_username TEXT,
    discord_display_name TEXT,
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
    discord_display_name TEXT,
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
    department TEXT,
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


# ============================================================
# HELPERS
# ============================================================

def now_text() -> str:
    return datetime.now().strftime("%d %B %Y")


def is_trainer(member: discord.Member) -> bool:
    return any(role.id == TRAINER_ROLE_ID for role in member.roles)


def is_trainee(member: discord.Member) -> bool:
    return any(role.id == TRAINEE_ROLE_ID for role in member.roles)


def has_institute_role(member: discord.Member) -> bool:
    return any(role.id in INSTITUTE_ROLE_IDS for role in member.roles)


def make_training_id() -> str:
    return "AST-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def ensure_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return "https://" + url
    return url


def roblox_profile_url(roblox_id: str) -> str:
    return f"https://www.roblox.com/users/{roblox_id}/profile"


async def get_roblox_headshot_url(roblox_id: str) -> str:
    fallback = f"https://www.roblox.com/headshot-thumbnail/image?userId={roblox_id}&width=420&height=420&format=png"

    try:
        api_url = (
            "https://thumbnails.roblox.com/v1/users/avatar-headshot"
            f"?userIds={roblox_id}&size=420x420&format=Png&isCircular=false"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=8) as response:
                if response.status != 200:
                    return fallback

                data = await response.json()
                items = data.get("data", [])

                if not items:
                    return fallback

                image_url = items[0].get("imageUrl")
                return image_url or fallback

    except Exception:
        return fallback


def base_embed(title: str, description: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=BRAND_COLOR,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Air Serbia Education Institute")
    return embed


async def send_log(guild: discord.Guild, title: str, description: str):
    if not guild:
        return

    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return

    embed = base_embed(title, description)
    await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def send_error(interaction: discord.Interaction, title: str, description: str, ephemeral: bool = True):
    embed = base_embed(f"{I4} {title}", description)
    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


async def send_success(interaction: discord.Interaction, title: str, description: str, ephemeral: bool = True):
    embed = base_embed(f"{I3} {title}", description)
    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


# ============================================================
# EMBED TEMPLATES
# ============================================================

def registration_welcome_embed() -> discord.Embed:
    description = f"""> {I13} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲**

You have been **successfully** registered and verified within the Air Serbia Education Institute. We are delighted to welcome you and congratulate you on the beginning of your academy journey.

> {I2} It is **essential** that you review the **[Central Hub](https://discord.com/channels/1512023301420224673/1512023301919084566)** to familiarize yourself with our academy policies, procedures, and regulations before attending any training sessions.

Should you have any questions or require further assistance, please do not hesitate to contact an **Institute Officer**.

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*

{BLANK}{BLANK}{AIR_SERBIA_LOGO} **Air Serbia** • *13 years of connecting people and creating memories.*
"""
    return base_embed("Registration Approved", description)


def registration_rejection_embed() -> discord.Embed:
    description = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Registration Update**

We appreciate your interest in joining the **Air Serbia Education Institute**. After reviewing your registration submission, we regret to inform you that your request has not been approved at this time.

> {ARROW} If you believe this decision was made in error, or if you require clarification, please contact an **Institute Officer** through the appropriate support channels.

Thank you for your time and interest in the Air Serbia Education Institute.

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""
    return base_embed("Registration Rejected", description)


def fail_result_embed(comments: str, exam_link: str) -> discord.Embed:
    description = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Results**
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
    return base_embed("Examination Results", description)


def theory_pass_embed(
    department: str,
    grade: str,
    points: int,
    max_points: int,
    percentage: float,
    attempt_number: int,
    comments: str,
    exam_link: str,
    grader: str
) -> discord.Embed:
    description = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Results**

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
    return base_embed("Theory Examination Passed", description)


def course_pass_embed(
    department: str,
    grade: str,
    points: int,
    max_points: int,
    percentage: float,
    attempt_number: int,
    comments: str,
    exam_link: str,
    grader: str
) -> discord.Embed:
    description = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Results**

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
    return base_embed("Course Examination Passed", description)


# ============================================================
# REGISTRATION APPROVAL VIEW
# ============================================================

class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="asei_registration_approve"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
            await send_error(interaction, "Permission Denied", "Only Institute Trainers may approve registrations.")
            return

        embed = interaction.message.embeds[0]
        discord_id = None

        for field in embed.fields:
            if field.name == "Discord ID":
                discord_id = int(field.value)
                break

        if not discord_id:
            await send_error(interaction, "Registration Error", "Discord ID could not be found in this registration request.")
            return

        cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (discord_id,))
        data = cursor.fetchone()

        if not data:
            await send_error(interaction, "Registration Error", "This registration request is no longer pending.")
            return

        (
            discord_id,
            discord_username,
            discord_display_name,
            roblox_username,
            roblox_id,
            department,
            submitted_at
        ) = data

        member = interaction.guild.get_member(discord_id)

        if not member:
            await send_error(interaction, "Member Not Found", "The applicant is no longer in this server.")
            return

        trainee_role = interaction.guild.get_role(TRAINEE_ROLE_ID)
        department_role = interaction.guild.get_role(DEPARTMENT_ROLES.get(department))

        roles_to_add = []
        if trainee_role:
            roles_to_add.append(trainee_role)
        if department_role:
            roles_to_add.append(department_role)

        try:
            if roles_to_add:
                await member.add_roles(
                    *roles_to_add,
                    reason="Air Serbia Education Institute registration approved"
                )
        except discord.Forbidden:
            await send_error(
                interaction,
                "Role Error",
                "I could not assign the roles. Please place my bot role above the trainee and department roles."
            )
            return

        registered_at = now_text()

        cursor.execute(
            "REPLACE INTO registrations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                discord_id,
                discord_username,
                discord_display_name,
                roblox_username,
                roblox_id,
                department,
                registered_at,
                "Active"
            )
        )
        cursor.execute("DELETE FROM pending_registrations WHERE discord_id = ?", (discord_id,))
        db.commit()

        try:
            await member.send(embed=registration_welcome_embed())
        except Exception:
            pass

        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Approved by {interaction.user}", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        await send_log(
            interaction.guild,
            "Registration Approved",
            f"Applicant: {member} (`{member.id}`)\nDepartment: {department}\nApproved By: {interaction.user}"
        )

        await send_success(interaction, "Registration Approved", "The applicant has been registered and ranked.")

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="asei_registration_reject"
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
            await send_error(interaction, "Permission Denied", "Only Institute Trainers may reject registrations.")
            return

        embed = interaction.message.embeds[0]
        discord_id = None

        for field in embed.fields:
            if field.name == "Discord ID":
                discord_id = int(field.value)
                break

        if not discord_id:
            await send_error(interaction, "Registration Error", "Discord ID could not be found in this registration request.")
            return

        cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (discord_id,))
        data = cursor.fetchone()

        member = interaction.guild.get_member(discord_id)

        if data:
            cursor.execute("DELETE FROM pending_registrations WHERE discord_id = ?", (discord_id,))
            db.commit()

        if member:
            try:
                await member.send(embed=registration_rejection_embed())
            except Exception:
                pass

        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Rejected by {interaction.user}", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        await send_log(
            interaction.guild,
            "Registration Rejected",
            f"Applicant ID: `{discord_id}`\nRejected By: {interaction.user}"
        )

        await send_success(interaction, "Registration Rejected", "The applicant has been rejected.")


# ============================================================
# BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    bot.add_view(RegistrationView())
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


# ============================================================
# COMMANDS
# ============================================================

@bot.tree.command(name="register", description="Submit your Education Institute registration.")
@app_commands.choices(department=[
    app_commands.Choice(name="Cabin Crew Trainee", value="Cabin Crew Trainee"),
    app_commands.Choice(name="Ground Crew Trainee", value="Ground Crew Trainee"),
    app_commands.Choice(name="Flight Deck Trainee", value="Flight Deck Trainee"),
    app_commands.Choice(name="Health and Safety Department", value="Health and Safety Department"),
])
@bot.event
async def on_ready():
    bot.add_view(RegistrationView())

    guild = discord.Object(id=GUILD_ID)

    try:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to Air Serbia server.")
    except Exception as e:
        print(f"Command sync failed: {e}")

    print(f"Logged in as {bot.user}")
):
    if not isinstance(interaction.user, discord.Member):
        await send_error(interaction, "Server Only", "This command can only be used inside the server.")
        return

    if has_institute_role(interaction.user):
        await send_error(
            interaction,
            "Already Registered",
            "You are already registered or already hold an Institute role."
        )
        return

    if not re.fullmatch(r"\d{2,20}", roblox_id):
        await send_error(
            interaction,
            "Invalid Roblox User ID",
            "Please enter your numeric Roblox User ID, not your Roblox username."
        )
        return

    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (interaction.user.id,))
    if cursor.fetchone():
        await send_error(
            interaction,
            "Already Registered",
            "You already have an approved Education Institute profile."
        )
        return

    cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (interaction.user.id,))
    if cursor.fetchone():
        await send_error(
            interaction,
            "Registration Pending",
            "Your registration is already pending review by an Institute Officer."
        )
        return

    submitted_at = now_text()

    cursor.execute(
        "REPLACE INTO pending_registrations VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            interaction.user.id,
            str(interaction.user),
            interaction.user.display_name,
            roblox_username,
            roblox_id,
            department.value,
            submitted_at
        )
    )
    db.commit()

    review_channel = interaction.guild.get_channel(REGISTRATION_REVIEW_CHANNEL_ID)
    headshot_url = await get_roblox_headshot_url(roblox_id)

    embed = base_embed(
        f"{AIR_SERBIA_LOGO} Registration Review",
        "A new Education Institute registration has been submitted and is awaiting review."
    )
    embed.add_field(name="Applicant", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="Discord ID", value=str(interaction.user.id), inline=True)
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Roblox User ID", value=roblox_id, inline=True)
    embed.add_field(name="Department", value=department.value, inline=False)
    embed.add_field(name="Submitted", value=submitted_at, inline=True)
    embed.add_field(name="Roblox Profile", value=f"[Profile Link]({roblox_profile_url(roblox_id)})", inline=False)
    embed.set_thumbnail(url=headshot_url)

    if review_channel:
        await review_channel.send(embed=embed, view=RegistrationView())

    await send_success(
        interaction,
        "Registration Submitted",
        "Your registration has been submitted for review. Please wait for an Institute Officer to approve it."
    )


@bot.tree.command(name="profile", description="View your Air Serbia Education Institute profile.")
async def profile(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await send_error(interaction, "Server Only", "This command can only be used inside the server.")
        return

    if not is_trainee(interaction.user):
        await send_error(
            interaction,
            "Registration Required",
            "You must complete registration before accessing your academy profile."
        )
        return

    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (interaction.user.id,))
    reg = cursor.fetchone()

    if not reg:
        await send_error(
            interaction,
            "Profile Not Found",
            "No approved academy profile was found for you."
        )
        return

    (
        discord_id,
        discord_username,
        discord_display_name,
        roblox_username,
        roblox_id,
        department,
        registered_at,
        status
    ) = reg

    cursor.execute("SELECT course_name, logged_at FROM training_logs WHERE trainee_id = ? ORDER BY id ASC", (interaction.user.id,))
    trainings = cursor.fetchall()

    cursor.execute("""
    SELECT exam_type, outcome, percentage, grade, grader_name, logged_at
    FROM exam_logs
    WHERE trainee_id = ?
    ORDER BY id ASC
    """, (interaction.user.id,))
    exams = cursor.fetchall()

    training_text = "\n".join(
        [f"{DOT} {course} • {date}" for course, date in trainings]
    ) or f"{DOT} No training attendance recorded."

    exam_text = "\n".join(
        [f"{DOT} {exam_type} — **{outcome}** • {round(percentage, 2)}% • {date}" for exam_type, outcome, percentage, grade, grader, date in exams]
    ) or f"{DOT} No examination participation recorded."

    latest_grade = "None"
    latest_examiner = "None"

    if exams:
        latest_grade = exams[-1][3]
        latest_examiner = exams[-1][4]

    headshot_url = await get_roblox_headshot_url(roblox_id)

    embed = base_embed(
        f"{I17} {roblox_username} Profile",
        f"""> {I8} **Training Attendance**
{training_text}

> {I10} **Examination Participation**
{exam_text}

> {I10} **Notes**
{DOT} Warnings: None
{DOT} Department: {department}
{DOT} Registered: {registered_at}
{DOT} Academy Status: {status}
{DOT} Latest Grade: {latest_grade}
{DOT} Latest Examiner: {latest_examiner}

{AIR_SERBIA_TAIL} We wish you the best of luck!

[Profile Link]({roblox_profile_url(roblox_id)})
"""
    )
    embed.set_author(
        name=f"{interaction.user.display_name}'s Academy Profile",
        icon_url=interaction.user.display_avatar.url
    )
    embed.set_thumbnail(url=headshot_url)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="progress", description="View your academy progress.")
async def progress(interaction: discord.Interaction):
    await profile(interaction)


@bot.tree.command(name="scheduletraining", description="Schedule a new course training.")
@app_commands.choices(department=[
    app_commands.Choice(name="Cabin Crew Trainee", value="Cabin Crew Trainee"),
    app_commands.Choice(name="Ground Crew Trainee", value="Ground Crew Trainee"),
    app_commands.Choice(name="Flight Deck Trainee", value="Flight Deck Trainee"),
    app_commands.Choice(name="Health and Safety Department", value="Health and Safety Department"),
])
async def scheduletraining(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    department: app_commands.Choice[str],
    course: str,
    phase: str,
    game_link: str,
    date_timestamp: str,
    time_timestamp: str
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may schedule trainings.")
        return

    game_link = ensure_url(game_link)

    department_role_id = DEPARTMENT_ROLES[department.value]
    department_role = interaction.guild.get_role(department_role_id)

    if not department_role:
        await send_error(interaction, "Role Not Found", "The selected department role could not be found.")
        return

    training_id = make_training_id()
    created_at = now_text()

    cursor.execute(
        "INSERT INTO trainings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            training_id,
            channel.id,
            department.value,
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

    description = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Course Schedule**
{BLANK}{BLANK} ◜*a new course training has been scheduled*

*Salutations, trainees!* It gives us pleasure to announce that a new **{course}** training will be taking place at **[Location]({game_link})**.

> {ARROW} In case you are unable to attend this training programme, please ensure that you communicate this to a member of the Institute so that an alternative training session may be arranged according to your timezone.

{BLANK} {I16} **<t:{date_timestamp}:D>, <t:{time_timestamp}:t>**

{DOT} Upon the __unlock__ of the training, you will be provided **10 minutes** to join before the server commences __lock__ and the training proceedings begin.

> ◜*If you wish to attend, please allocate by utilising the appropriate reaction below.*

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""

    embed = base_embed("Course Schedule", description)

    sent = await channel.send(
        content=department_role.mention,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

    await sent.add_reaction(discord.PartialEmoji.from_str(I15))
    await sent.add_reaction(discord.PartialEmoji.from_str(I14))

    dm_embed = base_embed(
        "Training Successfully Scheduled",
        f"{AIR_SERBIA_LOGO} Your course training has been scheduled successfully.\n\n"
        f"{DOT} **Training ID:** `{training_id}`\n"
        f"{DOT} **Course:** {course}\n"
        f"{DOT} **Phase:** {phase}\n"
        f"{DOT} **Department:** {department.value}\n\n"
        "Please keep this Training ID safe. It will be required for join time and attendance logging."
    )

    try:
        await interaction.user.send(embed=dm_embed)
    except Exception:
        pass

    await send_log(
        interaction.guild,
        "Training Scheduled",
        f"Training ID: `{training_id}`\n"
        f"Course: {course}\n"
        f"Phase: {phase}\n"
        f"Department: {department.value}\n"
        f"Scheduled By: {interaction.user}\n"
        f"Channel: #{channel.name}"
    )

    await send_success(
        interaction,
        "Training Scheduled",
        f"Training has been posted successfully.\n\n{DOT} **Training ID:** `{training_id}`"
    )


@bot.tree.command(name="jointime", description="Open join time for a scheduled training.")
async def jointime(
    interaction: discord.Interaction,
    training_id: str
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may open join time.")
        return

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await send_error(interaction, "Training Not Found", "No training was found with that Training ID.")
        return

    (
        training_id,
        channel_id,
        department,
        department_role_id,
        course,
        phase,
        game_link,
        date_timestamp,
        time_timestamp,
        scheduled_by_id,
        scheduled_by_name,
        created_at
    ) = data

    channel = interaction.guild.get_channel(channel_id)
    department_role = interaction.guild.get_role(department_role_id)

    if not channel or not department_role:
        await send_error(interaction, "Training Error", "The saved channel or department role could not be found.")
        return

    description = f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Course Commencement**
{BLANK}{BLANK}◜*we recommend that you review the information below*

> {I16} **All** participants are required to join promptly and ensure full attendance throughout.

{ARROW} **[Join Training]({game_link})**

{DOT} You are provided **10 minutes** to join before the server commences __lock__ and the training proceedings begin.

> {BLANK} *Please remain professional throughout the entirety of the session. Failure to do so may result in disciplinary action.*

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""

    embed = base_embed("Course Commencement", description)

    await channel.send(
        content=department_role.mention,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

    await send_log(
        interaction.guild,
        "Join Time Opened",
        f"Training ID: `{training_id}`\nCourse: {course}\nDepartment: {department}\nOpened By: {interaction.user}"
    )

    await send_success(interaction, "Join Time Posted", "Course commencement has been posted successfully.")


@bot.tree.command(name="logtraining", description="Log training attendance for a trainee.")
async def logtraining(
    interaction: discord.Interaction,
    training_id: str,
    trainee: discord.Member,
    course_name: str
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may log training attendance.")
        return

    cursor.execute("SELECT training_id FROM trainings WHERE training_id = ?", (training_id,))
    if not cursor.fetchone():
        await send_error(interaction, "Training Not Found", "No training was found with that Training ID.")
        return

    today = now_text()

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
        f"Trainee: {trainee} (`{trainee.id}`)\nCourse: {course_name}\nTraining ID: `{training_id}`\nTrainer: {interaction.user}"
    )

    await send_success(interaction, "Attendance Logged", "Training attendance has been saved successfully.")


@bot.tree.command(name="result", description="Issue examination results to a trainee.")
@app_commands.choices(
    exam_type=[
        app_commands.Choice(name="Theory Examination", value="Theory"),
        app_commands.Choice(name="Universal Course Examination", value="Course"),
    ],
    department=[
        app_commands.Choice(name="Cabin Crew Trainee", value="Cabin Crew Trainee"),
        app_commands.Choice(name="Ground Crew Trainee", value="Ground Crew Trainee"),
        app_commands.Choice(name="Flight Deck Trainee", value="Flight Deck Trainee"),
        app_commands.Choice(name="Health and Safety Department", value="Health and Safety Department"),
    ],
    outcome=[
        app_commands.Choice(name="Pass", value="PASSED"),
        app_commands.Choice(name="Fail", value="FAILED"),
    ]
)
async def result(
    interaction: discord.Interaction,
    trainee: discord.Member,
    exam_type: app_commands.Choice[str],
    department: app_commands.Choice[str],
    grade: str,
    points: int,
    max_points: int,
    outcome: app_commands.Choice[str],
    attempt_number: int,
    comments: str,
    exam_link: str
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may issue results.")
        return

    if max_points <= 0:
        await send_error(interaction, "Invalid Score", "Maximum points must be greater than 0.")
        return

    exam_link = ensure_url(exam_link)
    percentage = (points / max_points) * 100
    today = now_text()
    grader = str(interaction.user)

    cursor.execute(
        """
        INSERT INTO exam_logs (
            trainee_id, trainee_name, exam_type, department, grade,
            points, max_points, percentage, outcome, attempt_number,
            comments, exam_link, grader_id, grader_name, logged_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trainee.id,
            str(trainee),
            exam_type.value,
            department.value,
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
        dm_embed = theory_pass_embed(
            department.value,
            grade,
            points,
            max_points,
            percentage,
            attempt_number,
            comments,
            exam_link,
            grader
        )
    elif outcome.value == "PASSED" and exam_type.value == "Course":
        dm_embed = course_pass_embed(
            department.value,
            grade,
            points,
            max_points,
            percentage,
            attempt_number,
            comments,
            exam_link,
            grader
        )
    else:
        dm_embed = fail_result_embed(comments, exam_link)

    try:
        await trainee.send(embed=dm_embed)
    except Exception:
        pass

    kicked = False
    if outcome.value == "FAILED" and attempt_number >= 2:
        try:
            await trainee.kick(reason=f"Failed {exam_type.name} on second attempt.")
            kicked = True
        except Exception:
            kicked = False

    await send_log(
        interaction.guild,
        "Examination Result Issued",
        f"Trainee: {trainee} (`{trainee.id}`)\n"
        f"Exam: {exam_type.name}\n"
        f"Department: {department.value}\n"
        f"Score: {points}/{max_points} ({round(percentage, 2)}%)\n"
        f"Grade: {grade}\n"
        f"Result: {outcome.value}\n"
        f"Attempt: {attempt_number}\n"
        f"Graded By: {interaction.user}\n"
        f"Second Attempt Kick: {'Yes' if kicked else 'No'}"
    )

    await send_success(
        interaction,
        "Result Issued",
        f"The result has been saved and delivered.\n\n{DOT} **Result:** {outcome.value}\n{DOT} **Percentage:** {round(percentage, 2)}%"
    )


@bot.tree.command(name="dm", description="Send an official institute DM to a member.")
async def dm(
    interaction: discord.Interaction,
    user: discord.Member,
    message: str
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may use this command.")
        return

    dm_embed = base_embed(
        f"{I17} Official Institute Message",
        f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Official Message**

{message}

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**
> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲**
"""
    )

    try:
        await user.send(embed=dm_embed)
    except Exception:
        await send_error(interaction, "DM Failed", "I could not send a DM to this user.")
        return

    await send_log(
        interaction.guild,
        "Official DM Sent",
        f"Recipient: {user} (`{user.id}`)\nSent By: {interaction.user}"
    )

    await send_success(interaction, "DM Sent", "The official institute message has been delivered.")


@bot.tree.command(name="canceltraining", description="Cancel a scheduled training.")
async def canceltraining(
    interaction: discord.Interaction,
    training_id: str,
    reason: str
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may cancel trainings.")
        return

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await send_error(interaction, "Training Not Found", "No training was found with that Training ID.")
        return

    (
        training_id,
        channel_id,
        department,
        department_role_id,
        course,
        phase,
        game_link,
        date_timestamp,
        time_timestamp,
        scheduled_by_id,
        scheduled_by_name,
        created_at
    ) = data

    channel = interaction.guild.get_channel(channel_id)
    department_role = interaction.guild.get_role(department_role_id)

    if channel and department_role:
        embed = base_embed(
            "Course Training Cancelled",
            f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Training Cancellation**

The scheduled **{course}** training has been cancelled.

{DOT} **Training ID:** `{training_id}`
{DOT} **Department:** {department}
{DOT} **Reason:** {reason}

Please await further instructions from an **Institute Officer**.
"""
        )

        await channel.send(
            content=department_role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

    await send_log(
        interaction.guild,
        "Training Cancelled",
        f"Training ID: `{training_id}`\nCourse: {course}\nDepartment: {department}\nCancelled By: {interaction.user}\nReason: {reason}"
    )

    await send_success(interaction, "Training Cancelled", "The training cancellation has been posted.")

    
    @bot.tree.command(name="deleteregistration", description="Delete a trainee registration record.")
async def deleteregistration(
    interaction: discord.Interaction,
    user: discord.Member,
    remove_roles: bool = True
):
    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await send_error(interaction, "Permission Denied", "Only Institute Trainers may delete registrations.")
        return

    cursor.execute("DELETE FROM pending_registrations WHERE discord_id = ?", (user.id,))
    cursor.execute("DELETE FROM registrations WHERE discord_id = ?", (user.id,))
    cursor.execute("DELETE FROM training_logs WHERE trainee_id = ?", (user.id,))
    cursor.execute("DELETE FROM exam_logs WHERE trainee_id = ?", (user.id,))
    db.commit()

    removed_roles = []

    if remove_roles:
        role_ids = [
            TRAINEE_ROLE_ID,
            CABIN_CREW_ROLE_ID,
            GROUND_CREW_ROLE_ID,
            FLIGHT_DECK_ROLE_ID,
            HEALTH_SAFETY_ROLE_ID
        ]

        roles_to_remove = []

        for role_id in role_ids:
            role = interaction.guild.get_role(role_id)
            if role and role in user.roles:
                roles_to_remove.append(role)
                removed_roles.append(role.name)

        if roles_to_remove:
            try:
                await user.remove_roles(
                    *roles_to_remove,
                    reason="Education Institute registration deleted"
                )
            except discord.Forbidden:
                await send_error(
                    interaction,
                    "Role Error",
                    "The registration was deleted, but I could not remove the user's roles. Move my bot role above the trainee roles."
                )
                return

    await send_log(
        interaction.guild,
        "Registration Deleted",
        f"User: {user} (`{user.id}`)\n"
        f"Deleted By: {interaction.user}\n"
        f"Roles Removed: {', '.join(removed_roles) if removed_roles else 'None'}"
    )

    await send_success(
        interaction,
        "Registration Deleted",
        f"{user.mention}'s registration, training logs, and examination logs have been deleted."
    )


@bot.tree.command(name="help", description="View Institute Core commands.")
async def help_command(interaction: discord.Interaction):
    description = f"""{AIR_SERBIA_LOGO} **Institute Core Command Directory**

> {DOT} `/register` — Submit your registration for review.
> {DOT} `/profile` — View your academy profile.
> {DOT} `/progress` — View your academy progress.
> {DOT} `/scheduletraining` — Schedule a course training.
> {DOT} `/jointime` — Open join time using a Training ID.
> {DOT} `/logtraining` — Log training attendance.
> {DOT} `/result` — Issue examination results.
> {DOT} `/dm` — Send an official institute DM.
> {DOT} `/canceltraining` — Cancel a scheduled training.

{I17} **Air Serbia Education Institute** ⦧ *Reaching new heights, revolutionising the industry*
"""
    embed = base_embed("Institute Core Help", description)
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(TOKEN)
