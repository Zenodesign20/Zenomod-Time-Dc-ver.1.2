import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, date, time, timedelta, timezone
import json
import os
import shutil
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DATA_FILE = "members.json"
BACKUP_FILE = "members_backup.json"

GIF_THUMBNAIL = "https://cdn.discordapp.com/attachments/1468621028598087843/1471249375706746890/Black_White_Minimalist_Animation_Logo_Video_1.gif"

ROLE_PACKAGES = {
    "VIP": {"price": 200, "days": 30, "color": discord.Color.gold()},
    "Supreme": {"price": 300, "days": 30, "color": discord.Color.red()}
}

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

MESSAGE_CACHE = {}
API_QUEUE = asyncio.Queue()

# ================= JSON =================

def load_data():

    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except:
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        return {}

def save_data(data):

    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=4)

    shutil.copy(DATA_FILE,BACKUP_FILE)

# ================= TIME =================

def parse_date(date_str):

    return datetime.strptime(date_str,"%d/%m/%y").date()

def calc_expire(start_date):

    return start_date + timedelta(days=29)

# ================= ROLE PACKAGE =================

def package_from_role(role):

    if not role:
        return "-",discord.Color.greyple()

    for key,val in ROLE_PACKAGES.items():

        if role.name.startswith(key):

            text=f"{key} | ราคา {val['price']} บาท | จำนวน {val['days']} วัน"

            return text,val["color"]

    return role.name,discord.Color.blurple()

# ================= EMBED =================

def build_embed(member,info):

    role=member.guild.get_role(info["role_id"])

    start_date=date.fromisoformat(info["start_date"])
    expire_date=date.fromisoformat(info["expire_date"])

    package,color=package_from_role(role)

    embed=discord.Embed(
        title="👑 สถานะสมาชิก",
        color=color
    )

    embed.set_thumbnail(url=GIF_THUMBNAIL)

    embed.add_field(name="👤 ผู้รับ Role",value=member.mention,inline=False)

    embed.add_field(name="🎭 Role",value=role.mention if role else "-",inline=False)

    embed.add_field(name="📅 วันที่สมัคร",value=start_date.strftime("%d/%m/%Y"),inline=True)

    embed.add_field(name="💎 แพ็กเกจ",value=package,inline=False)

    embed.add_field(name="📅 วันหมดอายุ",value=expire_date.strftime("%d/%m/%Y"),inline=True)

    embed.set_footer(text="MEMBER SYSTEM • 30 DAYS")

    return embed

# ================= API QUEUE =================

async def api_worker():

    while True:

        func,args,kwargs=await API_QUEUE.get()

        try:
            await func(*args,**kwargs)
        except:
            pass

        await asyncio.sleep(1)

# ================= COMMAND =================

@bot.tree.command(name="setrole")
async def setrole(interaction:discord.Interaction,member:discord.Member,role:discord.Role,start_date:str):

    if interaction.user.id!=ADMIN_ID:
        await interaction.response.send_message("❌ Admin only",ephemeral=True)
        return

    start=parse_date(start_date)

    expire=calc_expire(start)

    await member.add_roles(role)

    info={
        "role_id":role.id,
        "start_date":start.isoformat(),
        "expire_date":expire.isoformat()
    }

    await interaction.response.send_message(embed=build_embed(member,info))

    msg=await interaction.original_response()

    info["channel_id"]=msg.channel.id
    info["message_id"]=msg.id

    MESSAGE_CACHE[str(member.id)]=msg

    data=load_data()

    data[str(member.id)]=info

    save_data(data)

# ================= RENEW =================

@bot.tree.command(name="renew")
async def renew(interaction:discord.Interaction,member:discord.Member):

    if interaction.user.id!=ADMIN_ID:
        return

    data=load_data()

    if str(member.id) not in data:

        await interaction.response.send_message("❌ ไม่พบสมาชิก",ephemeral=True)

        return

    info=data[str(member.id)]

    expire=date.fromisoformat(info["expire_date"])

    expire=expire+timedelta(days=30)

    info["expire_date"]=expire.isoformat()

    save_data(data)

    await interaction.response.send_message("✅ ต่ออายุเรียบร้อย")

    await refresh_embed(member,info)

# ================= REFRESH =================

async def refresh_embed(member,info):

    if str(member.id) in MESSAGE_CACHE:

        msg=MESSAGE_CACHE[str(member.id)]

        await API_QUEUE.put((msg.edit,(),{"embed":build_embed(member,info)}))

# ================= CHECK EXPIRE =================

@tasks.loop(minutes=60)
async def check_expire():

    data=load_data()

    now=datetime.now(timezone.utc)

    if not bot.guilds:
        return

    guild=bot.guilds[0]

    for uid,info in list(data.items()):

        member=guild.get_member(int(uid))

        role=guild.get_role(info["role_id"])

        expire_date=date.fromisoformat(info["expire_date"])

        expire_dt=datetime.combine(expire_date,time.max,tzinfo=timezone.utc)

        if now>=expire_dt:

            try:

                if member and role:

                    await member.remove_roles(role)

            except:
                pass

            try:

                channel=bot.get_channel(info["channel_id"])

                msg=await channel.fetch_message(info["message_id"])

                await msg.delete()

            except:
                pass

            del data[uid]

    save_data(data)

# ================= READY =================

@bot.event
async def on_ready():

    await bot.tree.sync()

    bot.loop.create_task(api_worker())

    check_expire.start()

    print("ULTIMATE MEMBER BOT v4 ONLINE")

bot.run(TOKEN)