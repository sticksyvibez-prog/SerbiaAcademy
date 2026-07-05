import os

import asyncio
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

GUILD_ID = 1512023301420224673

TRAINER_ROLE_ID = 1512023301457973280
TRAINEE_ROLE_ID = 1512023301445259316
STAFF_REGISTER_ROLE_ID = 1512023301470421114

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
bot.persistent_views_added = False


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
CREATE TABLE IF NOT EXISTS pending_staff_registrations (
    discord_id INTEGER PRIMARY KEY,
    discord_username TEXT,
    discord_display_name TEXT,
    roblox_username TEXT,
    roblox_id TEXT,
    staff_role TEXT,
    submitted_by_id INTEGER,
    submitted_by_name TEXT,
    submitted_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS staff_registrations (
    discord_id INTEGER PRIMARY KEY,
    discord_username TEXT,
    discord_display_name TEXT,
    roblox_username TEXT,
    roblox_id TEXT,
    staff_role TEXT,
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


def can_register_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_REGISTER_ROLE_ID for role in member.roles)


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


async def get_roblox_username(roblox_id: str) -> str | None:
    try:
        api_url = f"https://users.roblox.com/v1/users/{roblox_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=8) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                return data.get("name")
    except Exception:
        return None


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


def progress_embed(title: str, steps: list[str], current_index: int, status: str = "running", note: str = "") -> discord.Embed:
    lines = []

    for index, step in enumerate(steps):
        if status == "failed" and index == current_index:
            lines.append(f"{I4} **{step}**")
        elif status == "done" or index < current_index:
            lines.append(f"{I15} {step}")
        elif index == current_index:
            lines.append(f"{I16} **{step}**")
        else:
            lines.append(f"{DOT} {step}")

    if note:
        lines.append(f"\n> {ARROW} {note}")

    return base_embed(title, "\n".join(lines))


async def start_progress(interaction: discord.Interaction, title: str, steps: list[str]) -> discord.Message:
    embed = progress_embed(title, steps, 0)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    message = await interaction.original_response()
    await asyncio.sleep(0.45)
    return message


async def update_progress(message: discord.Message, title: str, steps: list[str], current_index: int, note: str = ""):
    embed = progress_embed(title, steps, current_index, note=note)
    await message.edit(embed=embed)
    await asyncio.sleep(0.45)


async def finish_progress(message: discord.Message, title: str, steps: list[str], note: str = ""):
    embed = progress_embed(title, steps, len(steps) - 1, status="done", note=note)
    await message.edit(embed=embed)


async def fail_progress(message: discord.Message, title: str, steps: list[str], failed_index: int, note: str):
    embed = progress_embed(title, steps, failed_index, status="failed", note=note)
    await message.edit(embed=embed)


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

        disabled_view = RegistrationView()
        for item in disabled_view.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=disabled_view)

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

        disabled_view = RegistrationView()
        for item in disabled_view.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=disabled_view)

        await send_log(
            interaction.guild,
            "Registration Rejected",
            f"Applicant ID: `{discord_id}`\nRejected By: {interaction.user}"
        )

        await send_success(interaction, "Registration Rejected", "The applicant has been rejected.")


# ============================================================
# STAFF REGISTRATION APPROVAL VIEW
# ============================================================

class StaffRegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve Staff",
        style=discord.ButtonStyle.success,
        custom_id="asei_staff_registration_approve"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
            await send_error(interaction, "Permission Denied", "Only Institute Trainers may approve staff registrations.")
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

        cursor.execute("SELECT * FROM pending_staff_registrations WHERE discord_id = ?", (discord_id,))
        data = cursor.fetchone()
        if not data:
            await send_error(interaction, "Registration Error", "This staff registration is no longer pending.")
            return

        (
            discord_id, discord_username, discord_display_name, roblox_username,
            roblox_id, staff_role, submitted_by_id, submitted_by_name, submitted_at
        ) = data

        member = interaction.guild.get_member(discord_id)
        if not member:
            await send_error(interaction, "Member Not Found", "The staff member is no longer in this server.")
            return

        matching_role = discord.utils.find(
            lambda role: role.name.casefold() == staff_role.casefold(),
            interaction.guild.roles
        )

        if not matching_role:
            await send_error(
                interaction,
                "Role Not Found",
                f"No Discord role named `{staff_role}` was found. Create it or ensure the entered role name is exact."
            )
            return

        try:
            await member.add_roles(
                matching_role,
                reason="Air Serbia Education Institute staff registration approved"
            )
        except discord.Forbidden:
            await send_error(
                interaction,
                "Role Error",
                "I could not assign the staff role. Place the bot role above the selected staff role."
            )
            return

        registered_at = now_text()
        cursor.execute(
            """
            INSERT INTO staff_registrations (
                discord_id, discord_username, discord_display_name, roblox_username,
                roblox_id, staff_role, registered_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                discord_username = excluded.discord_username,
                discord_display_name = excluded.discord_display_name,
                roblox_username = excluded.roblox_username,
                roblox_id = excluded.roblox_id,
                staff_role = excluded.staff_role,
                registered_at = excluded.registered_at,
                status = excluded.status
            """,
            (
                discord_id, discord_username, discord_display_name, roblox_username,
                roblox_id, staff_role, registered_at, "Active"
            )
        )
        cursor.execute("DELETE FROM pending_staff_registrations WHERE discord_id = ?", (discord_id,))
        db.commit()

        try:
            dm_embed = base_embed(
                "Staff Registration Approved",
                f"Your staff registration has been approved.\n\n"
                f"{DOT} **Staff Role:** {staff_role}\n"
                f"{DOT} **Roblox Username:** {roblox_username}\n"
                f"{DOT} **Status:** Active"
            )
            await member.send(embed=dm_embed)
        except Exception:
            pass

        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Approved by {interaction.user}", inline=False)
        disabled_view = StaffRegistrationView()
        for item in disabled_view.children:
            item.disabled = True
        await interaction.message.edit(embed=embed, view=disabled_view)

        await send_log(
            interaction.guild,
            "Staff Registration Approved",
            f"Staff Member: {member} (`{member.id}`)\n"
            f"Staff Role: {staff_role}\nApproved By: {interaction.user}"
        )
        await send_success(interaction, "Staff Registration Approved", "The staff member has been registered and ranked.")

    @discord.ui.button(
        label="Reject Staff",
        style=discord.ButtonStyle.danger,
        custom_id="asei_staff_registration_reject"
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
            await send_error(interaction, "Permission Denied", "Only Institute Trainers may reject staff registrations.")
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

        cursor.execute("DELETE FROM pending_staff_registrations WHERE discord_id = ?", (discord_id,))
        db.commit()

        member = interaction.guild.get_member(discord_id)
        if member:
            try:
                await member.send(embed=base_embed(
                    "Staff Registration Rejected",
                    "Your staff registration request was not approved at this time."
                ))
            except Exception:
                pass

        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Rejected by {interaction.user}", inline=False)
        disabled_view = StaffRegistrationView()
        for item in disabled_view.children:
            item.disabled = True
        await interaction.message.edit(embed=embed, view=disabled_view)

        await send_log(
            interaction.guild,
            "Staff Registration Rejected",
            f"Staff Member ID: `{discord_id}`\nRejected By: {interaction.user}"
        )
        await send_success(interaction, "Staff Registration Rejected", "The staff registration has been rejected.")


# ============================================================
# BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    if not bot.persistent_views_added:
        bot.add_view(RegistrationView())
        bot.add_view(StaffRegistrationView())
        bot.persistent_views_added = True

    # Sync commands only once per process. This prevents reconnects from
    # accidentally replacing the guild command list.
    if not getattr(bot, "commands_synced", False):
        guild = discord.Object(id=GUILD_ID)

        try:
            # Copy the commands defined in this file to the Air Serbia guild.
            bot.tree.copy_global_to(guild=guild)

            # Remove old GLOBAL slash commands. An outdated global /register
            # can otherwise remain visible and cause CommandSignatureMismatch.
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()

            # Publish the current guild command signatures immediately.
            synced = await bot.tree.sync(guild=guild)
            bot.commands_synced = True

            print(f"Synced {len(synced)} guild command(s) to Air Serbia server:")
            for command in synced:
                print(f"/{command.name}")

        except Exception as e:
            print(f"Command sync failed: {type(e).__name__}: {e}")

    print(f"Logged in as {bot.user}")


# ============================================================
# PROFILE HELPER
# ============================================================

async def send_profile_embed(interaction: discord.Interaction):
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

    cursor.execute(
        "SELECT course_name, logged_at FROM training_logs WHERE trainee_id = ? ORDER BY id ASC",
        (interaction.user.id,)
    )
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
        [
            f"{DOT} {exam_type} — **{outcome}** • {round(percentage, 2)}% • {date}"
            for exam_type, outcome, percentage, grade, grader, date in exams
        ]
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


# ============================================================
# COMMANDS
# ============================================================


@bot.tree.command(name="register", description="Submit an Education Institute trainee registration.")
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
    department: app_commands.Choice[str],
    discord_user_id: str | None = None
):
    steps = [
        "Starting registration request",
        "Checking academy eligibility",
        "Verifying Discord and Roblox User IDs",
        "Saving registration request",
        "Sending request to trainers",
        "Registration submitted successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Registration Progress", steps)
    await update_progress(progress_message, f"{I17} Registration Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member):
        await fail_progress(progress_message, f"{I17} Registration Progress", steps, 1, "This command can only be used inside the server.")
        return

    target = interaction.user
    submitted_for_other = False

    if discord_user_id:
        if not re.fullmatch(r"\d{15,22}", discord_user_id):
            await fail_progress(progress_message, f"{I17} Registration Progress", steps, 2, "Please enter a valid numeric Discord User ID.")
            return

        requested_id = int(discord_user_id)
        if requested_id != interaction.user.id:
            if not can_register_staff(interaction.user):
                await fail_progress(
                    progress_message,
                    f"{I17} Registration Progress",
                    steps,
                    1,
                    "Only authorized staff may register another trainee. Leave Discord User ID empty to register yourself."
                )
                return
            target = interaction.guild.get_member(requested_id)
            submitted_for_other = True
            if not target:
                await fail_progress(progress_message, f"{I17} Registration Progress", steps, 2, "That Discord user could not be found in this server.")
                return

    if not submitted_for_other and has_institute_role(target):
        await fail_progress(progress_message, f"{I17} Registration Progress", steps, 1, "You are already registered or already hold an Institute role.")
        return

    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (target.id,))
    if cursor.fetchone():
        await fail_progress(progress_message, f"{I17} Registration Progress", steps, 1, "This trainee already has an approved Education Institute profile.")
        return

    cursor.execute("SELECT * FROM pending_registrations WHERE discord_id = ?", (target.id,))
    if cursor.fetchone():
        await fail_progress(progress_message, f"{I17} Registration Progress", steps, 1, "This trainee already has a registration pending review.")
        return

    await update_progress(progress_message, f"{I17} Registration Progress", steps, 2)
    if not re.fullmatch(r"\d{2,20}", roblox_id):
        await fail_progress(progress_message, f"{I17} Registration Progress", steps, 2, "Please enter the numeric Roblox User ID.")
        return

    await update_progress(progress_message, f"{I17} Registration Progress", steps, 3)
    submitted_at = now_text()

    cursor.execute(
        """
        INSERT INTO pending_registrations (
            discord_id, discord_username, discord_display_name, roblox_username,
            roblox_id, department, submitted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            discord_username = excluded.discord_username,
            discord_display_name = excluded.discord_display_name,
            roblox_username = excluded.roblox_username,
            roblox_id = excluded.roblox_id,
            department = excluded.department,
            submitted_at = excluded.submitted_at
        """,
        (
            target.id, str(target), target.display_name, roblox_username,
            roblox_id, department.value, submitted_at
        )
    )
    db.commit()

    await update_progress(progress_message, f"{I17} Registration Progress", steps, 4)
    review_channel = interaction.guild.get_channel(REGISTRATION_REVIEW_CHANNEL_ID)
    headshot_url = await get_roblox_headshot_url(roblox_id)

    embed = base_embed(
        f"{AIR_SERBIA_LOGO} Registration Review",
        "A new Education Institute trainee registration has been submitted and is awaiting review."
    )
    embed.add_field(name="Applicant", value=f"{target} (`{target.id}`)", inline=False)
    embed.add_field(name="Discord ID", value=str(target.id), inline=True)
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Roblox User ID", value=roblox_id, inline=True)
    embed.add_field(name="Department", value=department.value, inline=False)
    embed.add_field(name="Submitted By", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="Submitted", value=submitted_at, inline=True)
    embed.add_field(name="Roblox Profile", value=f"[Profile Link]({roblox_profile_url(roblox_id)})", inline=False)
    embed.set_thumbnail(url=headshot_url)

    if review_channel:
        await review_channel.send(embed=embed, view=RegistrationView())
    else:
        await fail_progress(progress_message, f"{I17} Registration Progress", steps, 4, "The registration review channel could not be found.")
        return

    await finish_progress(
        progress_message,
        f"{I17} Registration Progress",
        steps,
        f"{target.mention}'s registration has been submitted for review."
    )


@bot.tree.command(name="staffregister", description="Register an Air Serbia staff member for approval.")
async def staffregister(
    interaction: discord.Interaction,
    discord_user_id: str,
    roblox_id: str,
    staff_role: str
):
    steps = [
        "Starting staff registration",
        "Checking authorization",
        "Verifying Discord and Roblox User IDs",
        "Loading Roblox account",
        "Saving staff registration",
        "Sending request for approval",
        "Staff registration submitted successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Staff Registration Progress", steps)
    await update_progress(progress_message, f"{I17} Staff Registration Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not can_register_staff(interaction.user):
        await fail_progress(
            progress_message,
            f"{I17} Staff Registration Progress",
            steps,
            1,
            "You must hold the authorized staff-registration role to use this command."
        )
        return

    await update_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2)
    if not re.fullmatch(r"\d{15,22}", discord_user_id):
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2, "Please enter a valid numeric Discord User ID.")
        return
    if not re.fullmatch(r"\d{2,20}", roblox_id):
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2, "Please enter a valid numeric Roblox User ID.")
        return
    if not staff_role.strip():
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2, "Please enter the staff member's role name.")
        return

    target = interaction.guild.get_member(int(discord_user_id))
    if not target:
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2, "That Discord user could not be found in this server.")
        return

    cursor.execute("SELECT 1 FROM staff_registrations WHERE discord_id = ?", (target.id,))
    if cursor.fetchone():
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2, "This member already has an approved staff profile.")
        return
    cursor.execute("SELECT 1 FROM pending_staff_registrations WHERE discord_id = ?", (target.id,))
    if cursor.fetchone():
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 2, "This member already has a pending staff registration.")
        return

    await update_progress(progress_message, f"{I17} Staff Registration Progress", steps, 3)
    roblox_username = await get_roblox_username(roblox_id)
    if not roblox_username:
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 3, "The Roblox account could not be found from that User ID.")
        return

    await update_progress(progress_message, f"{I17} Staff Registration Progress", steps, 4)
    submitted_at = now_text()
    cursor.execute(
        """
        INSERT INTO pending_staff_registrations (
            discord_id, discord_username, discord_display_name, roblox_username,
            roblox_id, staff_role, submitted_by_id, submitted_by_name, submitted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            discord_username = excluded.discord_username,
            discord_display_name = excluded.discord_display_name,
            roblox_username = excluded.roblox_username,
            roblox_id = excluded.roblox_id,
            staff_role = excluded.staff_role,
            submitted_by_id = excluded.submitted_by_id,
            submitted_by_name = excluded.submitted_by_name,
            submitted_at = excluded.submitted_at
        """,
        (
            target.id, str(target), target.display_name, roblox_username, roblox_id,
            staff_role.strip(), interaction.user.id, str(interaction.user), submitted_at
        )
    )
    db.commit()

    await update_progress(progress_message, f"{I17} Staff Registration Progress", steps, 5)
    review_channel = interaction.guild.get_channel(REGISTRATION_REVIEW_CHANNEL_ID)
    headshot_url = await get_roblox_headshot_url(roblox_id)

    embed = base_embed(
        f"{AIR_SERBIA_LOGO} Staff Registration Review",
        "A new staff registration has been submitted and is awaiting approval."
    )
    embed.add_field(name="Staff Member", value=f"{target} (`{target.id}`)", inline=False)
    embed.add_field(name="Discord ID", value=str(target.id), inline=True)
    embed.add_field(name="Roblox Username", value=roblox_username, inline=True)
    embed.add_field(name="Roblox User ID", value=roblox_id, inline=True)
    embed.add_field(name="Staff Role", value=staff_role.strip(), inline=False)
    embed.add_field(name="Submitted By", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="Submitted", value=submitted_at, inline=True)
    embed.add_field(name="Roblox Profile", value=f"[Profile Link]({roblox_profile_url(roblox_id)})", inline=False)
    embed.set_thumbnail(url=headshot_url)

    if not review_channel:
        await fail_progress(progress_message, f"{I17} Staff Registration Progress", steps, 5, "The registration review channel could not be found.")
        return

    await review_channel.send(embed=embed, view=StaffRegistrationView())
    await send_log(
        interaction.guild,
        "Staff Registration Submitted",
        f"Staff Member: {target} (`{target.id}`)\n"
        f"Roblox: {roblox_username} (`{roblox_id}`)\n"
        f"Role: {staff_role.strip()}\nSubmitted By: {interaction.user}"
    )
    await finish_progress(
        progress_message,
        f"{I17} Staff Registration Progress",
        steps,
        f"{target.mention}'s staff registration has been submitted for approval."
    )


@bot.tree.command(name="profile", description="View your Air Serbia Education Institute profile.")
async def profile(interaction: discord.Interaction):
    steps = [
        "Opening academy profile",
        "Checking registration status",
        "Loading training records",
        "Loading examination records",
        "Fetching Roblox profile image",
        "Profile prepared successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Profile Progress", steps)

    if not isinstance(interaction.user, discord.Member):
        await fail_progress(progress_message, f"{I17} Profile Progress", steps, 1, "This command can only be used inside the server.")
        return

    await update_progress(progress_message, f"{I17} Profile Progress", steps, 1)

    cursor.execute("SELECT * FROM staff_registrations WHERE discord_id = ?", (interaction.user.id,))
    staff_reg = cursor.fetchone()

    if staff_reg:
        (
            discord_id, discord_username, discord_display_name, roblox_username,
            roblox_id, staff_role, registered_at, status
        ) = staff_reg

        await update_progress(progress_message, f"{I17} Profile Progress", steps, 2)
        await update_progress(progress_message, f"{I17} Profile Progress", steps, 3)
        await update_progress(progress_message, f"{I17} Profile Progress", steps, 4)

        headshot_url = await get_roblox_headshot_url(roblox_id)
        embed = base_embed(
            f"{I17} {roblox_username} Staff Profile",
            f"""> {I10} **Staff Information**
{DOT} Discord User: {interaction.user.mention}
{DOT} Roblox Username: {roblox_username}
{DOT} Roblox User ID: {roblox_id}
{DOT} Staff Role: {staff_role}
{DOT} Registered: {registered_at}
{DOT} Status: {status}

{AIR_SERBIA_TAIL} Thank you for your service to Air Serbia.

[Roblox Profile]({roblox_profile_url(roblox_id)})
"""
        )
        embed.set_author(
            name=f"{interaction.user.display_name}'s Staff Profile",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_thumbnail(url=headshot_url)
        await progress_message.edit(embed=embed)
        return

    if not is_trainee(interaction.user):
        await fail_progress(progress_message, f"{I17} Profile Progress", steps, 1, "You must complete registration before accessing your academy profile.")
        return

    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (interaction.user.id,))
    reg = cursor.fetchone()

    if not reg:
        await fail_progress(progress_message, f"{I17} Profile Progress", steps, 1, "No approved academy profile was found for you.")
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

    await update_progress(progress_message, f"{I17} Profile Progress", steps, 2)

    cursor.execute(
        "SELECT course_name, logged_at FROM training_logs WHERE trainee_id = ? ORDER BY id ASC",
        (interaction.user.id,)
    )
    trainings = cursor.fetchall()

    await update_progress(progress_message, f"{I17} Profile Progress", steps, 3)

    cursor.execute("""
    SELECT exam_type, outcome, percentage, grade, grader_name, logged_at
    FROM exam_logs
    WHERE trainee_id = ?
    ORDER BY id ASC
    """, (interaction.user.id,))
    exams = cursor.fetchall()

    await update_progress(progress_message, f"{I17} Profile Progress", steps, 4)

    training_text = "\n".join(
        [f"{DOT} {course} • {date}" for course, date in trainings]
    ) or f"{DOT} No training attendance recorded."

    exam_text = "\n".join(
        [
            f"{DOT} {exam_type} — **{outcome}** • {round(percentage, 2)}% • {date}"
            for exam_type, outcome, percentage, grade, grader, date in exams
        ]
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

    await progress_message.edit(embed=embed)



@bot.tree.command(name="progress", description="View your or another user's academy progress.")
async def progress(
    interaction: discord.Interaction,
    user: discord.Member | None = None
):
    target = user or interaction.user
    steps = [
        "Opening academy progress",
        "Checking registration status",
        "Loading training records",
        "Loading examination records",
        "Fetching Roblox profile image",
        "Progress prepared successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Academy Progress", steps)

    cursor.execute("SELECT * FROM registrations WHERE discord_id = ?", (target.id,))
    reg = cursor.fetchone()

    if not reg:
        await fail_progress(progress_message, f"{I17} Academy Progress", steps, 1, "No approved academy profile was found for that user.")
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

    await update_progress(progress_message, f"{I17} Academy Progress", steps, 2)

    cursor.execute(
        "SELECT course_name, logged_at FROM training_logs WHERE trainee_id = ? ORDER BY id ASC",
        (target.id,)
    )
    trainings = cursor.fetchall()

    await update_progress(progress_message, f"{I17} Academy Progress", steps, 3)

    cursor.execute("""
    SELECT exam_type, outcome, percentage, grade, grader_name, logged_at
    FROM exam_logs
    WHERE trainee_id = ?
    ORDER BY id ASC
    """, (target.id,))
    exams = cursor.fetchall()

    await update_progress(progress_message, f"{I17} Academy Progress", steps, 4)

    training_text = "\n".join(
        [f"{DOT} {course} • {date}" for course, date in trainings]
    ) or f"{DOT} No training attendance recorded."

    exam_text = "\n".join(
        [
            f"{DOT} {exam_type} — **{outcome}** • {round(percentage, 2)}% • {date}"
            for exam_type, outcome, percentage, grade, grader, date in exams
        ]
    ) or f"{DOT} No examination participation recorded."

    latest_grade = "None"
    latest_examiner = "None"

    if exams:
        latest_grade = exams[-1][3]
        latest_examiner = exams[-1][4]

    headshot_url = await get_roblox_headshot_url(roblox_id)

    embed = base_embed(
        f"{I17} {roblox_username} Progress",
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

{AIR_SERBIA_TAIL} Keep progressing through your academy journey.

[Profile Link]({roblox_profile_url(roblox_id)})
"""
    )

    embed.set_author(
        name=f"{target.display_name}'s Academy Progress",
        icon_url=target.display_avatar.url
    )
    embed.set_thumbnail(url=headshot_url)

    await progress_message.edit(embed=embed)



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
    steps = [
        "Starting training schedule",
        "Checking trainer permissions",
        "Validating department role",
        "Saving training schedule",
        "Posting course schedule",
        "Sending confirmation and logs",
        "Training scheduled successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Schedule Training Progress", steps)

    await update_progress(progress_message, f"{I17} Schedule Training Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Schedule Training Progress", steps, 1, "Only Institute Trainers may schedule trainings.")
        return

    game_link = ensure_url(game_link)

    await update_progress(progress_message, f"{I17} Schedule Training Progress", steps, 2)

    department_role_id = DEPARTMENT_ROLES[department.value]
    department_role = interaction.guild.get_role(department_role_id)

    if not department_role:
        await fail_progress(progress_message, f"{I17} Schedule Training Progress", steps, 2, "The selected department role could not be found.")
        return

    await update_progress(progress_message, f"{I17} Schedule Training Progress", steps, 3)

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

    await update_progress(progress_message, f"{I17} Schedule Training Progress", steps, 4)

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

    await update_progress(progress_message, f"{I17} Schedule Training Progress", steps, 5)

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

    await finish_progress(
        progress_message,
        f"{I17} Schedule Training Progress",
        steps,
        f"Training has been posted successfully. Training ID: `{training_id}`"
    )



@bot.tree.command(name="jointime", description="Open join time for a scheduled training.")
async def jointime(
    interaction: discord.Interaction,
    training_id: str
):
    steps = [
        "Starting join time request",
        "Checking trainer permissions",
        "Finding training record",
        "Preparing course commencement",
        "Posting join time",
        "Join time posted successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Join Time Progress", steps)

    await update_progress(progress_message, f"{I17} Join Time Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Join Time Progress", steps, 1, "Only Institute Trainers may open join time.")
        return

    await update_progress(progress_message, f"{I17} Join Time Progress", steps, 2)

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await fail_progress(progress_message, f"{I17} Join Time Progress", steps, 2, "No training was found with that Training ID.")
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

    await update_progress(progress_message, f"{I17} Join Time Progress", steps, 3)

    channel = interaction.guild.get_channel(channel_id)
    department_role = interaction.guild.get_role(department_role_id)

    if not channel or not department_role:
        await fail_progress(progress_message, f"{I17} Join Time Progress", steps, 3, "The saved channel or department role could not be found.")
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

    await update_progress(progress_message, f"{I17} Join Time Progress", steps, 4)

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

    await finish_progress(progress_message, f"{I17} Join Time Progress", steps, "Course commencement has been posted successfully.")



@bot.tree.command(name="logtraining", description="Log training attendance for a trainee.")
async def logtraining(
    interaction: discord.Interaction,
    training_id: str,
    trainee: discord.Member,
    course_name: str
):
    steps = [
        "Starting attendance log",
        "Checking trainer permissions",
        "Finding training record",
        "Saving attendance record",
        "Sending log confirmation",
        "Attendance logged successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Attendance Log Progress", steps)

    await update_progress(progress_message, f"{I17} Attendance Log Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Attendance Log Progress", steps, 1, "Only Institute Trainers may log training attendance.")
        return

    await update_progress(progress_message, f"{I17} Attendance Log Progress", steps, 2)

    cursor.execute("SELECT training_id FROM trainings WHERE training_id = ?", (training_id,))
    if not cursor.fetchone():
        await fail_progress(progress_message, f"{I17} Attendance Log Progress", steps, 2, "No training was found with that Training ID.")
        return

    await update_progress(progress_message, f"{I17} Attendance Log Progress", steps, 3)

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

    await update_progress(progress_message, f"{I17} Attendance Log Progress", steps, 4)

    await send_log(
        interaction.guild,
        "Training Attendance Logged",
        f"Trainee: {trainee} (`{trainee.id}`)\nCourse: {course_name}\nTraining ID: `{training_id}`\nTrainer: {interaction.user}"
    )

    await finish_progress(progress_message, f"{I17} Attendance Log Progress", steps, "Training attendance has been saved successfully.")



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
    steps = [
        "Starting examination result",
        "Checking trainer permissions",
        "Validating examination score",
        "Saving examination result",
        "Preparing result message",
        "Delivering result to trainee",
        "Logging result action",
        "Result issued successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Result Progress", steps)

    await update_progress(progress_message, f"{I17} Result Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Result Progress", steps, 1, "Only Institute Trainers may issue results.")
        return

    await update_progress(progress_message, f"{I17} Result Progress", steps, 2)

    if max_points <= 0:
        await fail_progress(progress_message, f"{I17} Result Progress", steps, 2, "Maximum points must be greater than 0.")
        return

    exam_link = ensure_url(exam_link)
    percentage = (points / max_points) * 100
    today = now_text()
    grader = str(interaction.user)

    await update_progress(progress_message, f"{I17} Result Progress", steps, 3)

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

    await update_progress(progress_message, f"{I17} Result Progress", steps, 4)

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

    await update_progress(progress_message, f"{I17} Result Progress", steps, 5)

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

    await update_progress(progress_message, f"{I17} Result Progress", steps, 6)

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

    await finish_progress(
        progress_message,
        f"{I17} Result Progress",
        steps,
        f"Result saved and delivered. Result: **{outcome.value}** • Percentage: **{round(percentage, 2)}%**"
    )



@bot.tree.command(name="dm", description="Send an official institute DM to a member.")
async def dm(
    interaction: discord.Interaction,
    user: discord.Member,
    message: str
):
    steps = [
        "Starting official DM",
        "Checking trainer permissions",
        "Preparing institute message",
        "Sending direct message",
        "Logging delivery",
        "Official DM sent successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Official DM Progress", steps)

    await update_progress(progress_message, f"{I17} Official DM Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Official DM Progress", steps, 1, "Only Institute Trainers may use this command.")
        return

    await update_progress(progress_message, f"{I17} Official DM Progress", steps, 2)

    dm_embed = base_embed(
        f"{I17} Official Institute Message",
        f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Official Message**

{message}

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**
> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲**
"""
    )

    await update_progress(progress_message, f"{I17} Official DM Progress", steps, 3)

    try:
        await user.send(embed=dm_embed)
    except Exception:
        await fail_progress(progress_message, f"{I17} Official DM Progress", steps, 3, "I could not send a DM to this user.")
        return

    await update_progress(progress_message, f"{I17} Official DM Progress", steps, 4)

    await send_log(
        interaction.guild,
        "Official DM Sent",
        f"Recipient: {user} (`{user.id}`)\nSent By: {interaction.user}"
    )

    await finish_progress(progress_message, f"{I17} Official DM Progress", steps, "The official institute message has been delivered.")



@bot.tree.command(name="canceltraining", description="Cancel a scheduled training.")
async def canceltraining(
    interaction: discord.Interaction,
    training_id: str,
    reason: str
):
    steps = [
        "Starting training cancellation",
        "Checking trainer permissions",
        "Finding training record",
        "Preparing cancellation notice",
        "Posting cancellation notice",
        "Logging cancellation",
        "Training cancelled successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Cancellation Progress", steps)

    await update_progress(progress_message, f"{I17} Cancellation Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Cancellation Progress", steps, 1, "Only Institute Trainers may cancel trainings.")
        return

    await update_progress(progress_message, f"{I17} Cancellation Progress", steps, 2)

    cursor.execute("SELECT * FROM trainings WHERE training_id = ?", (training_id,))
    data = cursor.fetchone()

    if not data:
        await fail_progress(progress_message, f"{I17} Cancellation Progress", steps, 2, "No training was found with that Training ID.")
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

    await update_progress(progress_message, f"{I17} Cancellation Progress", steps, 3)

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

        await update_progress(progress_message, f"{I17} Cancellation Progress", steps, 4)

        await channel.send(
            content=department_role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )
    else:
        await update_progress(progress_message, f"{I17} Cancellation Progress", steps, 4, "Saved channel or role could not be found, but the cancellation will still be logged.")

    await update_progress(progress_message, f"{I17} Cancellation Progress", steps, 5)

    await send_log(
        interaction.guild,
        "Training Cancelled",
        f"Training ID: `{training_id}`\nCourse: {course}\nDepartment: {department}\nCancelled By: {interaction.user}\nReason: {reason}"
    )

    await finish_progress(progress_message, f"{I17} Cancellation Progress", steps, "The training cancellation has been posted.")



@bot.tree.command(name="deleteregistration", description="Delete a trainee registration record.")
async def deleteregistration(
    interaction: discord.Interaction,
    user: discord.Member,
    remove_roles: bool = True
):
    steps = [
        "Starting registration deletion",
        "Checking trainer permissions",
        "Deleting academy records",
        "Checking trainee roles",
        "Removing trainee roles",
        "Logging deletion",
        "Registration deleted successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Delete Registration Progress", steps)

    await update_progress(progress_message, f"{I17} Delete Registration Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Delete Registration Progress", steps, 1, "Only Institute Trainers may delete registrations.")
        return

    await update_progress(progress_message, f"{I17} Delete Registration Progress", steps, 2)

    cursor.execute("DELETE FROM pending_registrations WHERE discord_id = ?", (user.id,))
    cursor.execute("DELETE FROM registrations WHERE discord_id = ?", (user.id,))
    cursor.execute("DELETE FROM training_logs WHERE trainee_id = ?", (user.id,))
    cursor.execute("DELETE FROM exam_logs WHERE trainee_id = ?", (user.id,))
    db.commit()

    removed_roles = []

    await update_progress(progress_message, f"{I17} Delete Registration Progress", steps, 3)

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

        await update_progress(progress_message, f"{I17} Delete Registration Progress", steps, 4)

        if roles_to_remove:
            try:
                await user.remove_roles(
                    *roles_to_remove,
                    reason="Education Institute registration deleted"
                )
            except discord.Forbidden:
                await fail_progress(progress_message, f"{I17} Delete Registration Progress", steps, 4, "The registration was deleted, but I could not remove the user's roles. Move my bot role above the trainee roles.")
                return
    else:
        await update_progress(progress_message, f"{I17} Delete Registration Progress", steps, 4, "Role removal was skipped.")

    await update_progress(progress_message, f"{I17} Delete Registration Progress", steps, 5)

    await send_log(
        interaction.guild,
        "Registration Deleted",
        f"User: {user} (`{user.id}`)\n"
        f"Deleted By: {interaction.user}\n"
        f"Roles Removed: {', '.join(removed_roles) if removed_roles else 'None'}"
    )

    await finish_progress(
        progress_message,
        f"{I17} Delete Registration Progress",
        steps,
        f"{user.mention}'s registration, training logs, and examination logs have been deleted."
    )



@bot.tree.command(name="startexamroom", description="Randomly assign a trainee to an examination room.")
async def startexamroom(
    interaction: discord.Interaction,
    trainee: discord.Member
):
    steps = [
        "Starting examination room assignment",
        "Checking trainer permissions",
        "Finding available exam rooms",
        "Matching exam text channel",
        "Connecting bot to voice room",
        "Moving trainee to assigned room",
        "Posting examination notice",
        "Examination room started successfully"
    ]
    progress_message = await start_progress(interaction, f"{I17} Exam Room Progress", steps)

    await update_progress(progress_message, f"{I17} Exam Room Progress", steps, 1)

    if not isinstance(interaction.user, discord.Member) or not is_trainer(interaction.user):
        await fail_progress(progress_message, f"{I17} Exam Room Progress", steps, 1, "Only Institute Trainers may start an exam room.")
        return

    await update_progress(progress_message, f"{I17} Exam Room Progress", steps, 2)

    exam_rooms = []

    for channel in interaction.guild.voice_channels:
        match = re.fullmatch(r"room-(\d+)", channel.name.lower())
        if match:
            room_number = match.group(1)
            exam_rooms.append((channel, room_number))

    if not exam_rooms:
        await fail_progress(progress_message, f"{I17} Exam Room Progress", steps, 2, "I could not find any voice channels named `room-1`, `room-2`, `room-3`, etc.")
        return

    empty_rooms = [(channel, number) for channel, number in exam_rooms if len(channel.members) == 0]

    if empty_rooms:
        selected_room, room_number = random.choice(empty_rooms)
    else:
        selected_room, room_number = random.choice(exam_rooms)

    await update_progress(progress_message, f"{I17} Exam Room Progress", steps, 3)

    exam_text_channel = discord.utils.get(
        interaction.guild.text_channels,
        name=f"exam-{room_number}"
    )

    if not exam_text_channel:
        await fail_progress(progress_message, f"{I17} Exam Room Progress", steps, 3, f"I found `{selected_room.name}`, but I could not find the matching text channel `exam-{room_number}`.")
        return

    await update_progress(progress_message, f"{I17} Exam Room Progress", steps, 4)

    try:
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_connected():
            await fail_progress(
                progress_message,
                f"{I17} Exam Room Progress",
                steps,
                4,
                f"I am already connected to {voice_client.channel.mention}. Please ask the trainer to disconnect me before starting another examination room."
            )
            return

        await selected_room.connect(self_deaf=True)

    except discord.Forbidden:
        await fail_progress(progress_message, f"{I17} Exam Room Progress", steps, 4, f"I do not have permission to connect to {selected_room.mention}.")
        return

    except Exception as e:
        await fail_progress(progress_message, f"{I17} Exam Room Progress", steps, 4, f"I could not join the selected exam room. Error: `{e}`")
        return

    await update_progress(progress_message, f"{I17} Exam Room Progress", steps, 5)

    try:
        await trainee.move_to(selected_room, reason="Trainee assigned to examination room")
    except Exception:
        pass

    try:
        ghost_ping = await exam_text_channel.send(interaction.user.mention)
        await ghost_ping.delete(delay=1)
    except Exception:
        pass

    await update_progress(progress_message, f"{I17} Exam Room Progress", steps, 6)

    embed = base_embed(
        f"{I17} Examination Centre",
        f"""> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** — **Examination Centre**

{BLANK}{BLANK} ⦧ *Your examination room has been prepared.*

{DOT} **Trainee:** {trainee.mention}
{DOT} **Examination Room:** {selected_room.mention}
{DOT} **Assigned Trainer:** {interaction.user.mention}

> {ARROW} Please remain present within your assigned voice room for the duration of the examination session.

> {I16} Your assigned trainer will be sharing the official examination link with you shortly. Please wait patiently and do not leave the examination room unless instructed by an **Institute Officer**.

> {I4} Leaving the examination room without permission may result in your examination being reviewed, cancelled, or marked invalid.

**ᴡɪᴛʜ ʀᴇɢᴀʀᴅꜱ,**

> {I17} **𝗔𝗶𝗿 𝗦𝗲𝗿𝗯𝗶𝗮 𝗘𝗱𝘂𝗰𝗮𝘁𝗶𝗼𝗻 𝗜𝗻𝘀𝘁𝗶𝘁𝘂𝘁𝗲** ⦧ *Reaching new heights, revolutionising the industry*
"""
    )

    await exam_text_channel.send(
        content=trainee.mention,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True)
    )

    await send_log(
        interaction.guild,
        "Examination Room Started",
        f"Trainee: {trainee} (`{trainee.id}`)\n"
        f"Voice Room: {selected_room.name}\n"
        f"Text Channel: #{exam_text_channel.name}\n"
        f"Trainer: {interaction.user}"
    )

    await finish_progress(
        progress_message,
        f"{I17} Exam Room Progress",
        steps,
        f"{trainee.mention} has been assigned to {selected_room.mention}. The examination notice was posted in {exam_text_channel.mention}."
    )



@bot.tree.command(name="help", description="View Institute Core commands.")
async def help_command(interaction: discord.Interaction):
    steps = [
        "Opening command directory",
        "Loading institute commands",
        "Preparing help panel"
    ]
    progress_message = await start_progress(interaction, f"{I17} Help Progress", steps)
    await update_progress(progress_message, f"{I17} Help Progress", steps, 1)
    await update_progress(progress_message, f"{I17} Help Progress", steps, 2)

    description = f"""{AIR_SERBIA_LOGO} **Institute Core Command Directory**

> {DOT} `/register` — Submit a trainee registration for review.
> {DOT} `/staffregister` — Submit a staff registration for approval.
> {DOT} `/profile` — View your academy profile.
> {DOT} `/progress` — View your academy progress.
> {DOT} `/scheduletraining` — Schedule a course training.
> {DOT} `/jointime` — Open join time using a Training ID.
> {DOT} `/logtraining` — Log training attendance.
> {DOT} `/result` — Issue examination results.
> {DOT} `/dm` — Send an official institute DM.
> {DOT} `/canceltraining` — Cancel a scheduled training.
> {DOT} `/deleteregistration` — Delete a trainee registration record.
> {DOT} `/startexamroom` — Randomly assign a trainee to an examination room.

{I17} **Air Serbia Education Institute** ⦧ *Reaching new heights, revolutionising the industry*
"""
    embed = base_embed("Institute Core Help", description)
    await progress_message.edit(embed=embed)



bot.run(TOKEN)
