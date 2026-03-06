import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, date, timedelta, timezone
import json
import os
import shutil
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1392851942480412822"))

DATA_FILE = "roles.json"
BACKUP_FILE = "roles_backup.json"

GIF_THUMBNAIL = "https://cdn.discordapp.com/attachments/1468621028598087843/1471249375706746890/Black_White_Minimalist_Animation_Logo_Video_1.gif"

ROLE_PACKAGES = {
    "VIP": {"price": 200, "days": 30, "color": discord.Color.gold()},
    "Supreme": {"price": 300, "days": 30, "color": discord.Color.red()}
}

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATA =================

def load_data():

    if not os.path.exists(DATA_FILE):

        if os.path.exists(BACKUP_FILE):
            shutil.copy(BACKUP_FILE, DATA_FILE)
        else:
            return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except:

        if os.path.exists(BACKUP_FILE):

            shutil.copy(BACKUP_FILE, DATA_FILE)

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)

    return {}

def save_data(data):

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    shutil.copy(DATA_FILE, BACKUP_FILE)

# ================= TIME =================

def parse_date(date_str):

    return datetime.strptime(date_str, "%d/%m/%Y").date()

def calc_expire(start, days):

    return start + timedelta(days=days - 1)

# ================= PACKAGE =================

def get_package(role):

    if not role:
        return None

    for name in ROLE_PACKAGES:

        if role.name.startswith(name):
            return name

    return None

# ================= EMBED =================

def build_embed(member, info):

    role = member.guild.get_role(info["role_id"])

    start_date = date.fromisoformat(info["start_date"])
    expire_date = date.fromisoformat(info["expire_date"])

    pack = get_package(role)

    color = ROLE_PACKAGES[pack]["color"] if pack else discord.Color.blue()

    embed = discord.Embed(
        title="👑 สถานะสมาชิก",
        color=color
    )

    embed.set_thumbnail(url=GIF_THUMBNAIL)

    embed.add_field(name="👤 ผู้รับ Role", value=member.mention, inline=False)

    embed.add_field(name="🎭 Role", value=role.mention if role else "-", inline=False)

    embed.add_field(name="📅 วันที่สมัคร", value=start_date.strftime("%d/%m/%Y"), inline=True)

    if pack:

        price = ROLE_PACKAGES[pack]["price"]
        days = ROLE_PACKAGES[pack]["days"]

        embed.add_field(
            name="💎 แพ็กเกจ",
            value=f"{pack} | ราคา {price} บาท | จำนวน {days} วัน",
            inline=False
        )

    embed.add_field(
        name="📅 วันหมดอายุ",
        value=expire_date.strftime("%d/%m/%Y"),
        inline=True
    )

    embed.set_footer(text="MEMBER SYSTEM • 30 DAYS")

    return embed

# ================= REFRESH EMBED =================

async def refresh_embed(member_id):

    data = load_data()

    if member_id not in data:
        return

    info = data[member_id]

    guild = bot.guilds[0]

    member = guild.get_member(int(member_id))

    if not member:
        return

    try:

        channel = bot.get_channel(info["channel_id"])

        msg = await channel.fetch_message(info["message_id"])

        await msg.edit(embed=build_embed(member, info))

        await asyncio.sleep(0.5)

    except discord.HTTPException:
        pass

# ================= SETROLE =================

@bot.tree.command(name="setrole")

async def setrole(interaction: discord.Interaction,
                  member: discord.Member,
                  role: discord.Role,
                  start_date: str):

    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ admin only", ephemeral=True)
        return

    start = parse_date(start_date)

    pack = get_package(role)

    if not pack:
        await interaction.response.send_message("❌ role package error")
        return

    days = ROLE_PACKAGES[pack]["days"]

    expire = calc_expire(start, days)

    await member.add_roles(role)

    info = {
        "role_id": role.id,
        "start_date": start.isoformat(),
        "expire_date": expire.isoformat()
    }

    embed = build_embed(member, info)

    await interaction.response.send_message(embed=embed)

    msg = await interaction.original_response()

    info["channel_id"] = msg.channel.id
    info["message_id"] = msg.id

    data = load_data()

    data[str(member.id)] = info

    save_data(data)

# ================= RENEW =================

@bot.tree.command(name="renew")

async def renew(interaction: discord.Interaction, member: discord.Member):

    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ admin only", ephemeral=True)
        return

    data = load_data()

    uid = str(member.id)

    if uid not in data:

        await interaction.response.send_message("❌ ไม่มีข้อมูล")
        return

    info = data[uid]

    role = interaction.guild.get_role(info["role_id"])

    pack = get_package(role)

    days = ROLE_PACKAGES[pack]["days"]

    expire = date.fromisoformat(info["expire_date"])

    new_expire = expire + timedelta(days=days)

    info["expire_date"] = new_expire.isoformat()

    save_data(data)

    await refresh_embed(uid)

    await interaction.response.send_message("✅ ต่ออายุสำเร็จ")

# ================= EXPIRE =================

@tasks.loop(minutes=1)

async def check_expired():

    data = load_data()

    now = datetime.now(timezone.utc)

    if not bot.guilds:
        return

    guild = bot.guilds[0]

    changed = False

    for uid, info in list(data.items()):

        member = guild.get_member(int(uid))

        role = guild.get_role(info["role_id"])

        expire = date.fromisoformat(info["expire_date"])

        expire_dt = datetime.combine(expire, datetime.max.time(), tzinfo=timezone.utc)

        if now >= expire_dt:

            try:

                if member and role:
                    await member.remove_roles(role)

            except:
                pass

            try:

                channel = bot.get_channel(info["channel_id"])
                msg = await channel.fetch_message(info["message_id"])
                await msg.delete()

            except:
                pass

            del data[uid]

            changed = True

            await asyncio.sleep(1)

    if changed:
        save_data(data)

# ================= READY =================

@bot.event

async def on_ready():

    await bot.tree.sync()

    check_expired.start()

    print("👑 ULTIMATE MEMBER BOT ONLINE")

bot.run(TOKEN)