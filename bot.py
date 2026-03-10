```python
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

GIF_THUMBNAIL = "https://cdn.discordapp.com/attachments/1468621028598087843/1471249375706746890/Black_White_Minimalist_Animation_Logo_Video_1.gif"

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

        if os.path.exists(BACKUP_FILE):
            shutil.copy(BACKUP_FILE, DATA_FILE)

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

def save_data(data):

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    shutil.copy(DATA_FILE, BACKUP_FILE)

# ================= TIME =================

def parse_date(text):
    return datetime.strptime(text, "%d/%m/%y").date()

def calc_expire(start):
    return start + timedelta(days=29)

# ================= PACKAGE =================

def get_package(role):

    if role is None:
        return "-", "-", "-"

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

# ================= CANCEL BUTTON =================

class CancelRoleView(discord.ui.View):

    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="❌ ยกเลิกสมาชิก", style=discord.ButtonStyle.danger)
    async def cancel_member(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("❌ admin only", ephemeral=True)
            return

        data = load_data()

        if str(self.member_id) not in data:
            await interaction.response.send_message("❌ ไม่มีข้อมูลสมาชิก", ephemeral=True)
            return

        info = data[str(self.member_id)]

        member = interaction.guild.get_member(self.member_id)
        role = interaction.guild.get_role(info["role_id"])

        try:
            await member.remove_roles(role)
        except:
            pass

        del data[str(self.member_id)]
        save_data(data)

        embed = discord.Embed(
            title="⛔ สมาชิกถูกยกเลิก",
            description=f"Member : {member.mention}",
            color=discord.Color.dark_red()
        )

        try:
            await interaction.message.edit(embed=embed, view=None)
        except:
            pass

        try:
            await member.send("⛔ สมาชิกของคุณถูกยกเลิกแล้ว")
        except:
            pass

        await interaction.response.send_message("✅ ยกเลิกสมาชิกเรียบร้อย", ephemeral=True)

# ================= DM SYSTEM =================

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

# ================= SET ROLE =================

@bot.tree.command(name="setrole", description="เพิ่มสมาชิก")

async def setrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role, start_date: str):

    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ admin only", ephemeral=True)
        return

    start = parse_date(start_date)
    expire = calc_expire(start)

    await member.add_roles(role)

    info = {
        "role_id": role.id,
        "start_date": start.isoformat(),
        "expire_date": expire.isoformat(),
        "warned": False
    }

    embed = build_embed(member, info)

    view = CancelRoleView(member.id)

    await interaction.response.send_message(embed=embed, view=view)

    msg = await interaction.original_response()

    info["channel_id"] = msg.channel.id
    info["message_id"] = msg.id

    data = load_data()

    data[str(member.id)] = info

    save_data(data)

    await dm_user(member, "👑 คุณได้รับ Role สมาชิกแล้ว")

# ================= RENEW =================

@bot.tree.command(name="renew", description="ต่ออายุสมาชิก")

async def renew(interaction: discord.Interaction, member: discord.Member):

    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ admin only", ephemeral=True)
        return

    data = load_data()

    if str(member.id) not in data:
        await interaction.response.send_message("❌ ไม่มีสมาชิก", ephemeral=True)
        return

    info = data[str(member.id)]

    expire = date.fromisoformat(info["expire_date"])

    new_expire = expire + timedelta(days=30)

    info["expire_date"] = new_expire.isoformat()
    info["warned"] = False

    save_data(data)

    try:

        channel = bot.get_channel(info["channel_id"])

        if channel:
            msg = await channel.fetch_message(info["message_id"])

            await msg.edit(
                embed=build_embed(member, info),
                view=CancelRoleView(member.id)
            )

    except:
        pass

    await interaction.response.send_message(
        f"✅ ต่ออายุ {member.mention} แล้ว\nหมดอายุใหม่ {new_expire.strftime('%d/%m/%Y')}"
    )

# ================= AUTO CHECK =================

@tasks.loop(minutes=10)

async def check_expire():

    data = load_data()

    now = datetime.now(timezone.utc)

    if not bot.guilds:
        return

    guild = bot.guilds[0]

    changed = False

    for uid, info in list(data.items()):

        member = guild.get_member(int(uid))
        role = guild.get_role(info["role_id"])

        if member is None:
            continue

        expire = date.fromisoformat(info["expire_date"])

        expire_dt = datetime.combine(expire, datetime.max.time(), tzinfo=timezone.utc)

        remain = expire_dt - now

        if remain.days == 3 and not info["warned"]:

            await dm_user(member, "⚠ สมาชิกจะหมดอายุในอีก 3 วัน")

            info["warned"] = True

            changed = True

        if now >= expire_dt:

            try:
                await member.remove_roles(role)
            except:
                pass

            await dm_user(member, "⛔ สมาชิกของคุณหมดอายุแล้ว")

            del data[uid]

            changed = True

            continue

        try:

            channel = bot.get_channel(info["channel_id"])

            if channel:

                msg = await channel.fetch_message(info["message_id"])

                await msg.edit(
                    embed=build_embed(member, info),
                    view=CancelRoleView(member.id)
                )

                await asyncio.sleep(2)

        except:
            pass

    if changed:
        save_data(data)

# ================= READY =================

@bot.event
async def on_ready():

    await bot.tree.sync()

    check_expire.start()

    print("BOT ONLINE")

bot.run(TOKEN)
```
