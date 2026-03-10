import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, date, timedelta, timezone
import json
import os
import shutil
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DATA_FILE = "members.json"
BACKUP_FILE = "members_backup.json"

ROLE_PACKAGES = {
    "VIP": {"price": 200, "days": 30},
    "Supreme": {"price": 300, "days": 30}
}

GIF_THUMBNAIL = "https://cdn.discordapp.com/attachments/1468621028598087843/1471260996394811605/Sponsor-Zenobot1.png?ex=69b139d4&is=69afe854&hm=343446e669659e06a6459a162ae0a764c2b56dad5a5bbb1ab2b8a9e39d15113a&"

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= JSON SAFE =================

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

        shutil.copy(BACKUP_FILE, DATA_FILE)

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def save_data(data):

    tmp = "members.tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    os.replace(tmp, DATA_FILE)

    shutil.copy(DATA_FILE, BACKUP_FILE)


DATA = load_data()

# ================= QUEUE =================

queue = asyncio.Queue()

@tasks.loop(seconds=1)
async def queue_worker():

    if queue.empty():
        return

    task = await queue.get()

    if task["type"] == "add_role":

        try:
            await task["member"].add_roles(task["role"])
        except:
            pass

    if task["type"] == "remove_role":

        try:
            await task["member"].remove_roles(task["role"])
        except:
            pass


# ================= TIME =================

def parse_date(text):
    return datetime.strptime(text, "%d/%m/%y").date()


def calc_expire(start):
    return start + timedelta(days=29)


# ================= PACKAGE =================

def get_package(role):

    for key in ROLE_PACKAGES:

        if role.name.startswith(key):
            p = ROLE_PACKAGES[key]
            return key, p["price"], p["days"]

    return role.name, "-", "-"


# ================= EMBED =================

def build_embed(member, info):

    role = member.guild.get_role(info["role_id"])

    package, price, days = get_package(role)

    start = date.fromisoformat(info["start_date"])
    expire = date.fromisoformat(info["expire_date"])

    color = discord.Color.gold()

    if package == "Supreme":
        color = discord.Color.red()

    embed = discord.Embed(
        title="👑 สถานะสมาชิก",
        color=color
    )

    embed.set_thumbnail(url=GIF_THUMBNAIL)

    embed.add_field(name="👤 ผู้รับ Role", value=member.mention, inline=False)

    embed.add_field(name="🎭 Role", value=role.mention if role else "-", inline=False)

    embed.add_field(name="📅 วันที่สมัคร", value=start.strftime("%d/%m/%Y"), inline=True)

    embed.add_field(
        name="💎 แพ็กเกจ",
        value=f"{package} | ราคา {price} บาท | จำนวน {days} วัน",
        inline=False
    )

    embed.add_field(name="📅 วันหมดอายุ", value=expire.strftime("%d/%m/%Y"), inline=True)

    embed.set_footer(text="Zeno thanks for your support")

    return embed


# ================= BUTTON =================

class CancelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="❌ ยกเลิก Role", style=discord.ButtonStyle.red, custom_id="cancel_role")

    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("❌ admin only", ephemeral=True)
            return

        message_id = interaction.message.id

        member_id = None
        info = None

        for uid, data in DATA.items():

            if data.get("message_id") == message_id:
                member_id = uid
                info = data
                break

        if not member_id:

            await interaction.response.send_message("❌ ไม่พบข้อมูลสมาชิก", ephemeral=True)
            return

        member = interaction.guild.get_member(int(member_id))

        role = interaction.guild.get_role(info["role_id"])

        await queue.put({
            "type": "remove_role",
            "member": member,
            "role": role
        })

        del DATA[member_id]
        save_data(DATA)

        await interaction.response.send_message("✅ ยกเลิก Role แล้ว")


# ================= DM =================

async def dm_user(member, text):

    try:
        await member.send(text)
    except:
        pass


async def dm_admin(text):

    admin = bot.get_user(ADMIN_ID)

    if admin:

        try:
            await admin.send(text)
        except:
            pass


# ================= SETROLE =================

@bot.tree.command(name="setrole", description="เพิ่มสมาชิก")

async def setrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role, start_date: str):

    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ admin only", ephemeral=True)
        return

    start = parse_date(start_date)
    expire = calc_expire(start)

    await queue.put({
        "type": "add_role",
        "member": member,
        "role": role
    })

    info = {
        "role_id": role.id,
        "start_date": start.isoformat(),
        "expire_date": expire.isoformat(),
        "warned": False
    }

    embed = build_embed(member, info)

    await interaction.response.send_message(embed=embed, view=CancelView())

    msg = await interaction.original_response()

    info["channel_id"] = msg.channel.id
    info["message_id"] = msg.id

    DATA[str(member.id)] = info
    save_data(DATA)

    package, price, days = get_package(role)

    await dm_user(member,
        f"👑 คุณได้รับ Role สมาชิก\n\n"
        f"Member : {package}\n"
        f"ราคา : {price} บาท\n"
        f"จำนวน : {days} วัน"
    )

    await dm_admin(f"✅ เพิ่ม Role ให้ {member}")


# ================= RENEW =================

@bot.tree.command(name="renew", description="ต่ออายุสมาชิก")

async def renew(interaction: discord.Interaction, member: discord.Member):

    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ admin only", ephemeral=True)
        return

    if str(member.id) not in DATA:

        await interaction.response.send_message("❌ ไม่มีสมาชิก", ephemeral=True)
        return

    info = DATA[str(member.id)]

    expire = date.fromisoformat(info["expire_date"])

    new_expire = expire + timedelta(days=30)

    info["expire_date"] = new_expire.isoformat()

    save_data(DATA)

    await interaction.response.send_message("✅ ต่ออายุแล้ว")


# ================= EXPIRE CHECK =================

@tasks.loop(minutes=10)
async def check_expire():

    now = datetime.now(timezone.utc)

    if not bot.guilds:
        return

    guild = bot.guilds[0]

    changed = False

    for uid, info in list(DATA.items()):

        member = guild.get_member(int(uid))

        role = guild.get_role(info["role_id"])

        expire = date.fromisoformat(info["expire_date"])

        expire_dt = datetime.combine(expire, datetime.max.time(), tzinfo=timezone.utc)

        remain = expire_dt - now

        if remain.days == 3 and not info["warned"]:

            await dm_user(member, "⚠ สมาชิกจะหมดอายุในอีก 3 วัน")

            await dm_admin(f"⚠ {member} จะหมดอายุใน 3 วัน")

            info["warned"] = True
            changed = True

        if now >= expire_dt:

            await queue.put({
                "type": "remove_role",
                "member": member,
                "role": role
            })

            await dm_user(member, "⛔ สมาชิกของคุณหมดอายุแล้ว")

            await dm_admin(f"⛔ หมดอายุ {member}")

            del DATA[uid]
            changed = True
            continue

        try:

            channel = bot.get_channel(info["channel_id"])

            msg = await channel.fetch_message(info["message_id"])

            await msg.edit(embed=build_embed(member, info), view=CancelView())

        except:
            pass

    if changed:
        save_data(DATA)


# ================= READY =================

@bot.event
async def on_ready():

    await bot.tree.sync()

    bot.add_view(CancelView())

    queue_worker.start()
    check_expire.start()

    print("BOT ONLINE")


bot.run(TOKEN)