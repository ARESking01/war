import nest_asyncio

nest_asyncio.apply()

import logging
import json
import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter, Forbidden, BadRequest
import sys
import random
import asyncio
from datetime import datetime
import threading
import time

# Silence noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ===== 7 BOTS TOKENS =====
BOT_TOKENS = [
"8315379223:AAFhGKbb6DnHoMJcMBf5Oz6bGQjab0A6M00",
"8587447679:AAHeHxYaydBST0wAtqPQOga2G6lehgNR83I",
"7966291144:AAGsedT-K6H5SM7eN5kWBbDTQUedLb85lpQ",
"8573329126:AAHss3YLZ3w1M-SKbegWZ7hlUTEp2_OcIA0",
"8533855145:AAEeoD4Vz2b1gFz_x0Xcu2LHe7Hi2ngOgeA",
"8287351984:AAH8jZV0C9vkQLPN4_ZBpB3mjoIjIgxeqVA",
"8597521420:AAEwNGf3xM9dqZKy81rwsWke9EBd2HyqMhs"
]

OWNER_USER_ID = 8477357886
USERS_FILE = "users.json"

# 🔥 UNIQUE SYSTEM: SINGLE vs POWER COMMANDS
SINGLE_BOT_CMDS = {
"start": True,
"menu": True,
"myrank": True,
"status": True,
"userinfo": True,
"ping": True,
"coinflip": True
}

POWER_BOT_CMDS = {
"ncloop": True,
"ncloop2": True,
"ncloop3": True,
"ncloop4": True,
"slide": True,
"stopslide": True,
"stop": True,
"emoreact": True,
"stopemo": True,
"promote": True,
"depromote": True
}

# 🔥 EMOJI LISTS
hearts = ["❤️", "💕", "♥️", "💖", "💗"]
words = ["cudkd", "cud", "tmkc", "chmr", "dafan"]
animals = ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵"]

# 🔥 4 RANK SYSTEM
RANK_EMOJIS = {
"owner": "👑",
"coowner": "💎",
"admin": "🔧",
"cutie": "🎮"
}

RANK_NAMES = ["owner", "coowner", "admin", "cutie"]

# 🔥 FIXED USER SYSTEM (INSTANT LOAD/SAVE)
def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                data = json.load(f)
            print(f"📁 Loaded {len(data)} users")
            return data
        return {}
    except Exception as e:
        print(f"❌ Load error: {e}")
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        print(f"💾 Saved {len(users)} users")
    except Exception as e:
        print(f"❌ Save error: {e}")

def get_user_rank(user_id):
    users = load_users()
    return users.get(str(user_id), "none")

def set_user_rank(user_id, rank):
    users = load_users()
    users[str(user_id)] = rank
    save_users(users)
    print(f"👑 PROMOTED {user_id} → {rank}")

def remove_user_rank(user_id):
    users = load_users()
    if str(user_id) in users:
        del users[str(user_id)]
        save_users(users)
    print(f"❌ DEPROMOTED {user_id}")

# 🔥 PERFECT PERMISSION CHECK
def check_permission(user_id, required_rank, command_name=""):
    rank = get_user_rank(user_id)
    rank_order = {"owner": 4, "coowner": 3, "admin": 2, "cutie": 1, "none": 0}
    user_level = rank_order.get(rank, 0)
    required_level = rank_order.get(required_rank, 0)
    if user_level < required_level:
        rank_display = rank.upper() if rank != "none" else "USER"
        return False, f"❌ **PERMISSION DENIED!**\n**{rank_display}** cannot use **{command_name or 'this command'}**\n**Contact Owner for promotion 👑**"
    return True, ""

# 🔥 UNIQUE SINGLE BOT COORDINATOR
last_single_cmd_time = {}
SINGLE_CMD_COOLDOWN = 0.5

def should_handle_single_cmd(bot_id, update):
    """Only 1 bot handles SINGLE commands (/menu /myrank /status)"""
    cmd = update.message.text.split()[0][1:].lower() # /menu → menu
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    key = f"{chat_id}_{user_id}_{cmd}"
    now = time.time()
    if key not in last_single_cmd_time:
        last_single_cmd_time[key] = now
        print(f"🎯 BOT {bot_id+1} handles SINGLE: /{cmd}")
        return True
    if now - last_single_cmd_time[key] > SINGLE_CMD_COOLDOWN:
        last_single_cmd_time[key] = now
        print(f"🎯 BOT {bot_id+1} handles SINGLE: /{cmd}")
        return True
    print(f"⏭️ BOT {bot_id+1} skips SINGLE: /{cmd}")
    return False

# ===== BOT STATES =====
bot_states = {i: {'loop_running': False, 'loop_task': None, 'active_chat_id': None, 'global_name': "Vaibhav Group", 'global_delay': 0.3, 'app': None, 'loop_type': None} for i in range(len(BOT_TOKENS))}

# 🔥 GLOBAL SYSTEMS
emoji_react_active = False
emoji_react_chat_id = None
current_emoji = "❤️"
slide_active = False
slide_chat_id = None
slide_text = ""
slide_delay = 0.5

def api_react(bot_token, chat_id, message_id, emoji):
    url = f"https://api.telegram.org/bot{bot_token}/setMessageReaction"
    data = {"chat_id": chat_id, "message_id": message_id, "reaction": [{"type": "emoji", "emoji": emoji}]}
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            print(f"🎭 ✅ REACTED {emoji}")
            return True
    except:
        pass
    return False

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global emoji_react_active, emoji_react_chat_id, current_emoji, slide_active, slide_chat_id, slide_text, slide_delay
    message = update.message
    if not message or message.from_user.is_bot or message.text.startswith('/'):
        return
    chat_id = message.chat_id
    if emoji_react_active and chat_id == emoji_react_chat_id:
        api_react(context.bot.token, chat_id, message.message_id, current_emoji)
    if slide_active and chat_id == slide_chat_id:
        try:
            await asyncio.sleep(slide_delay)
            await context.bot.send_message(chat_id=chat_id, text=slide_text, reply_to_message_id=message.message_id, disable_notification=True)
            print(f"📱 SLIDED '{slide_text}'")
        except:
            pass

async def safe_set_title(app, chat_id, title):
    for attempt in range(3):
        try:
            await app.bot.set_chat_title(chat_id=chat_id, title=title)
            print(f"✅ TITLE: {title[:30]}")
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + random.uniform(0.5, 1.5))
        except (Forbidden, BadRequest):
            return False
        except:
            await asyncio.sleep(1)
    return False

# 🔥 LOOPS (COMPLETE) - MODIFIED FOR CUSTOM NAME/TITLE
async def time_loop(bot_id, custom_name):
    state = bot_states[bot_id]
    state['global_name'] = custom_name or state['global_name']
    while state['loop_running']:
        try:
            if not state['active_chat_id'] or not state['app']:
                await asyncio.sleep(1)
                continue
            now = datetime.now().strftime("%H:%M:%S")
            title = f"{state['global_name']} | {now}"
            await safe_set_title(state['app'], state['active_chat_id'], title)
            await asyncio.sleep(state['global_delay'])
        except:
            await asyncio.sleep(2)

async def heart_loop(bot_id, custom_name):
    state = bot_states[bot_id]
    state['global_name'] = custom_name or state['global_name']
    while state['loop_running']:
        try:
            if not state['active_chat_id'] or not state['app']:
                await asyncio.sleep(1)
                continue
            h1, h2 = random.choice(hearts), random.choice(hearts)
            title = f"{h1} {state['global_name']} {h2}"
            await safe_set_title(state['app'], state['active_chat_id'], title)
            await asyncio.sleep(state['global_delay'])
        except:
            await asyncio.sleep(2)

async def words_loop(bot_id, custom_name):
    state = bot_states[bot_id]
    state['global_name'] = custom_name or state['global_name']
    while state['loop_running']:
        try:
            if not state['active_chat_id'] or not state['app']:
                await asyncio.sleep(1)
                continue
            word = random.choice(words)
            title = f"{state['global_name']} {word} ❤️"
            await safe_set_title(state['app'], state['active_chat_id'], title)
            await asyncio.sleep(state['global_delay'])
        except:
            await asyncio.sleep(2)

async def animal_loop(bot_id, custom_name):
    state = bot_states[bot_id]
    state['global_name'] = custom_name or state['global_name']
    while state['loop_running']:
        try:
            if not state['active_chat_id'] or not state['app']:
                await asyncio.sleep(1)
                continue
            animal = random.choice(animals)
            title = f"{animal} {state['global_name']} {animal}"
            await safe_set_title(state['app'], state['active_chat_id'], title)
            await asyncio.sleep(state['global_delay'])
        except:
            await asyncio.sleep(2)

# 🔥 SINGLE BOT COMMANDS (ONLY 1 BOT REPLIES)
async def start(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    rank = get_user_rank(update.effective_user.id)
    emoji = RANK_EMOJIS.get(rank, "👤")
    rank_display = rank.upper() if rank != "none" else "USER"
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(
        f"""🤖 **BOT #{bot_num}** | 🚀 **VAIBHAV 7-BOT EMPIRE!** 🔥💎⚡
{emoji} **{rank_display}**: {update.effective_user.first_name}
📋 **/menu** - Your commands 👇
🔍 **/myrank** - Check rank""",
        parse_mode='Markdown'
    )

async def myrank(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    user_id = update.effective_user.id
    rank = get_user_rank(user_id)
    emoji = RANK_EMOJIS.get(rank, "👤")
    rank_display = rank.upper() if rank != "none" else "USER"
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    text = f"""🤖 **BOT #{bot_num}** | {emoji} **YOUR RANK:** {rank_display}
**Permissions:** {'✅ ACTIVE' if rank != 'none' else '❌ NONE'}
"""
    if rank == "owner":
        text += """👑 **OWNER COMMANDS:**
`/promote` `/depromote` `/ncloop*` `/slide` `/emoreact`"""
    elif rank == "coowner":
        text += """💎 **CO-OWNER COMMANDS:**
`/ncloop*` `/slide` `/emoreact`"""
    elif rank == "admin":
        text += """🔧 **ADMIN COMMANDS:**
`/ncloop2-4` `/slide` `/stop*`"""
    else:
        text += """🎮 **CUTIE COMMANDS:**
`/coinflip` `/userinfo` `/ping`"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def menu(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    allowed, msg = check_permission(update.effective_user.id, "admin", "/menu")
    if not allowed:
        await update.message.reply_text(msg)
        return
    rank = get_user_rank(update.effective_user.id)
    rank_display = rank.upper()
    emoji = RANK_EMOJIS[rank]
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    text = f"""🤖 **BOT #{bot_num}** | 🚀 **VAIBHAV ULTIMATE SCRIPT!** 🔥💎⚡🪙🎲👤
{emoji} **{rank_display} MODE ACTIVATED!** 👑

"""
    if rank == "owner":
        text += """👑 **OWNER - भगवान** 🔥🔥🔥
├ /promote rank → Promote (admin,coowner,cutie)
├ /depromote → Remove rank
├ /ncloop "name" → VAIBHAV TIME NCLOOP ⚡
├ /ncloop2 "name" → VAIBHAV HEARTS NCLOOP 💕
├ /ncloop3 "name" → VAIBHAV WORDS NCLOOP 📝
├ /ncloop4 "name" → ANIMALS NCLOOP🐶
├ /slide "text" → Reply slide 📱
├ /emoreact ❤️ → Auto react 🎭
└ /stop → Stop loop ⏹️

"""
    elif rank == "coowner":
        text += """💎 **CO-OWNER - ELITE** 🔥🔥
├ /ncloop "name" → TIME LOOP ⚡
├ /ncloop2 "name" → HEARTS 💕
├ /ncloop3 "name" → WORDS 📝
├ /ncloop4 "name" → ANIMALS 🐶
├ /slide "text" → Reply slide 📱
└ /emoreact ❤️ → Auto react 🎭

"""
    elif rank == "admin":
        text += """🔧 **ADMIN - POWER** 🔥
├ /ncloop2 "name" → HEARTS 💕
├ /ncloop3 "name" → WORDS 📝
├ /ncloop4 "name" → ANIMALS 🐶
├ /slide "text" → Reply slide 📱
└ /stop → Stop loop ⏹️

"""
    else:
        text += """🎮 **CUTIE - GAMES** ✨
├ /coinflip → Coin battle 🪙
├ /userinfo → Profile info 👤
├ /ping → Speed test ⚡
└ /dice_battle @user→ Dice fight 🎲

"""
    text += f"""
**⚡ UTILS (ALL RANKS):**
• `/myrank`
• `/start`
• `/menu`

**🔥 POWER LEVEL: MAXIMUM! 💯**
**{emoji} {rank_display} = {RANK_EMOJIS['owner']} VAIBHAV EMPIRE ALIVE!**"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def status(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    allowed, msg = check_permission(update.effective_user.id, "admin", "/status")
    if not allowed:
        await update.message.reply_text(msg)
        return
    bot_id = int(context.bot.id) % len(BOT_TOKENS)
    state = bot_states[bot_id]
    bot_num = bot_id + 1
    emoji_status = f"🟢 `{current_emoji}`" if emoji_react_active else "🔴 OFF"
    slide_status = f"🟢 `{slide_text[:20]}`" if slide_active else "🔴 OFF"
    loop_status = "🟢 ON" if state['loop_running'] else "🔴 OFF"
    loop_type = state.get('loop_type', 'NONE')
    text = f"""🤖 **BOT #{bot_num} STATUS** 🔥
🔄 **Loop:** {loop_status} ({loop_type})
🎭 **React:** {emoji_status}
📱 **Slide:** {slide_status}
⏱️ **Delay:** {state['global_delay']*1000:.0f}ms"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def ping(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    allowed, msg = check_permission(update.effective_user.id, "cutie", "/ping")
    if not allowed:
        await update.message.reply_text(msg)
        return
    start_time = time.time()
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except:
        pass
    ping_ms = round((time.time() - start_time) * 1000, 2)
    speed_emoji = "🚀" if ping_ms < 50 else "⚡" if ping_ms < 100 else "🐌"
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | ⚡ **PONG!** {speed_emoji}\n**{ping_ms}ms**")

async def userinfo(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    allowed, msg = check_permission(update.effective_user.id, "cutie", "/userinfo")
    if not allowed:
        await update.message.reply_text(msg)
        return
    chat = update.effective_chat
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    else:
        target_user = update.effective_user
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    try:
        member = await context.bot.get_chat_member(chat.id, target_user.id)
        status_map = {
        "creator": ("⭐", "OWNER"), "administrator": ("👑", "ADMIN"),
        "member": ("👤", "USER"), "restricted": ("🔒", "RESTRICTED")
        }
        status_emoji, status_text = status_map.get(member.status, ("👤", "USER"))
        rank = get_user_rank(target_user.id)
        rank_emoji = RANK_EMOJIS.get(rank, "👤")
        info_text = f"""🤖 **BOT #{bot_num}** | 👤 **{target_user.first_name or 'No Name'}**
{status_emoji} **{status_text}** | {rank_emoji} **{rank.upper()}**
🆔 `{target_user.id}`
📱 `@{target_user.username or 'No username'}`"""
        await update.message.reply_text(info_text, parse_mode='Markdown')
    except:
        rank = get_user_rank(target_user.id)
        rank_emoji = RANK_EMOJIS.get(rank, "👤")
        await update.message.reply_text(f"🤖 **BOT #{bot_num}** | 👤 **{target_user.first_name or 'User'}**\n🆔 `{target_user.id}`\n{rank_emoji} **{rank.upper()}**")

async def coinflip(update: Update, context):
    if not should_handle_single_cmd(int(context.bot.id) % len(BOT_TOKENS), update):
        return
    allowed, msg = check_permission(update.effective_user.id, "cutie", "/coinflip")
    if not allowed:
        await update.message.reply_text(msg)
        return
    user_name = update.effective_user.first_name
    bot_emojis = ["🤖", "⚡", "🔥", "💎", "🚀", "🎯", "👑"]
    random_bot_emoji = random.choice(bot_emojis)
    result = random.choice(["🪙 **HEADS!** ✅", "🪙 **TAILS!** ❌"])
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    coinflip_msg = f"""🤖 **BOT #{bot_num}** | 🪙 **COIN FLIP!**
{random_bot_emoji} **BOT** vs **{user_name}**
{result}"""
    await update.message.reply_text(coinflip_msg, parse_mode='Markdown')

# 🔥 POWER COMMANDS (ALL 7 BOTS WORK!)
async def promote(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "owner", "/promote")
    if not allowed:
        await update.message.reply_text(msg)
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ **REPLY to user → `/promote coowner`**\n**Ranks:** `owner/coowner/admin/cutie`", parse_mode='Markdown')
        return
    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name or "User"
    if not context.args or context.args[0].lower() not in RANK_NAMES:
        await update.message.reply_text(f"❌ **Valid ranks:** `{RANK_NAMES}`\n**REPLY → `/promote coowner`**", parse_mode='Markdown')
        return
    rank = context.args[0].lower()
    set_user_rank(target_id, rank)
    emoji = RANK_EMOJIS[rank]
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | {emoji} **{target_name}** → **{rank.upper()} RANK!** ✅\n**Permissions ACTIVATED instantly!**")

async def depromote(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "owner", "/depromote")
    if not allowed:
        await update.message.reply_text(msg)
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ **REPLY to user → `/depromote`**", parse_mode='Markdown')
        return
    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name or "User"
    old_rank = get_user_rank(target_id)
    remove_user_rank(target_id)
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | 👤 **{target_name}** → **DEPROMOTED!**\n**(was {old_rank.upper()})** ❌")

# 🔥 TITLE LOOPS (ALL 7 BOTS) - MODIFIED FOR CUSTOM NAME
async def ncloop(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "coowner", "/ncloop")
    if not allowed:
        await update.message.reply_text(msg)
        return
    bot_id = int(context.bot.id) % len(BOT_TOKENS)
    state = bot_states[bot_id]
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ **GROUP ONLY!**")
        return
    
    # Get custom name or use chat title
    custom_name = " ".join(context.args) if context.args else (chat.title or "Vaibhav Group")
    state['active_chat_id'] = chat.id
    state['app'] = context.application
    state['loop_type'] = "TIME"
    
    if state['loop_running']:
        await update.message.reply_text(f"🔄 **🎗 NCLOOP {custom_name} started now 🎗!**")
        return
    
    state['loop_running'] = True
    state['loop_task'] = asyncio.create_task(time_loop(bot_id, custom_name))
    await update.message.reply_text(f"⚡ **⏲ VAIBHAV TIME LOOP ON: {custom_name}!**")

async def ncloop2(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "admin", "/ncloop2")
    if not allowed:
        await update.message.reply_text(msg)
        return
    bot_id = int(context.bot.id) % len(BOT_TOKENS)
    state = bot_states[bot_id]
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ **GROUP ONLY!**")
        return
    
    # Get custom name or use chat title
    custom_name = " ".join(context.args) if context.args else (chat.title or "Vaibhav Group")
    state['active_chat_id'] = chat.id
    state['app'] = context.application
    state['loop_type'] = "HEARTS"
    
    if state['loop_running']:
        await update.message.reply_text(f"🔄 **🎗 NCLOOP {custom_name} started now 🎗!**")
        return
    
    state['loop_running'] = True
    state['loop_task'] = asyncio.create_task(heart_loop(bot_id, custom_name))
    await update.message.reply_text(f"💕 **💘 VAIBHAV HEARTS LOOP ON: {custom_name}!**")

async def ncloop3(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "admin", "/ncloop3")
    if not allowed:
        await update.message.reply_text(msg)
        return
    bot_id = int(context.bot.id) % len(BOT_TOKENS)
    state = bot_states[bot_id]
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ **GROUP ONLY!**")
        return
    
    # Get custom name or use chat title
    custom_name = " ".join(context.args) if context.args else (chat.title or "Vaibhav Group")
    state['active_chat_id'] = chat.id
    state['app'] = context.application
    state['loop_type'] = "WORDS"
    
    if state['loop_running']:
        await update.message.reply_text(f"🔄 **🎗 NCLOOP {custom_name} started now 🎗!**")
        return
    
    state['loop_running'] = True
    state['loop_task'] = asyncio.create_task(words_loop(bot_id, custom_name))
    await update.message.reply_text(f"📝 **💪 VAIBHAV WORDS LOOP ON: {custom_name}!**")

async def ncloop4(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "admin", "/ncloop4")
    if not allowed:
        await update.message.reply_text(msg)
        return
    bot_id = int(context.bot.id) % len(BOT_TOKENS)
    state = bot_states[bot_id]
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ **GROUP ONLY!**")
        return
    
    # Get custom name or use chat title
    custom_name = " ".join(context.args) if context.args else (chat.title or "Vaibhav Group")
    state['active_chat_id'] = chat.id
    state['app'] = context.application
    state['loop_type'] = "ANIMALS"
    
    if state['loop_running']:
        await update.message.reply_text(f"🔄 **🎗 NCLOOP {custom_name} started now 🎗!**")
        return
    
    state['loop_running'] = True
    state['loop_task'] = asyncio.create_task(animal_loop(bot_id, custom_name))
    await update.message.reply_text(f"🐾 **ANIMAL LOOP ON: {custom_name}!** 🐶")

async def slide(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "admin", "/slide")
    if not allowed:
        await update.message.reply_text(msg)
        return
    global slide_active, slide_chat_id, slide_text
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ **GROUP ONLY!**")
        return
    if not context.args:
        await update.message.reply_text("❌ **`/slide Vaibhav`**")
        return
    slide_text = " ".join(context.args)
    slide_chat_id = chat.id
    slide_active = True
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | 📱 **SLIDE ON!** `{slide_text}`")

async def stopslide(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "admin", "/stopslide")
    if not allowed:
        await update.message.reply_text(msg)
        return
    global slide_active
    slide_active = False
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | ⏹️ **SLIDE OFF!**")

async def stop(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "admin", "/stop")
    if not allowed:
        await update.message.reply_text(msg)
        return
    bot_id = int(context.bot.id) % len(BOT_TOKENS)
    state = bot_states[bot_id]
    state['loop_running'] = False
    if state['loop_task']:
        state['loop_task'].cancel()
    bot_num = bot_id + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | ⏹️ **BOT{bot_num} STOPPED!**")

# 🔥 OWNER ONLY EMOJI REACT (ALL 7 BOTS)
async def emoreact(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "owner", "/emoreact")
    if not allowed:
        await update.message.reply_text(msg)
        return
    global emoji_react_active, emoji_react_chat_id, current_emoji
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ **GROUP ONLY!**")
        return
    current_emoji = context.args[0] if context.args else "❤️"
    emoji_react_chat_id = chat.id
    emoji_react_active = True
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | 🎭 **REACTIONS ON!** `{current_emoji}` → ALL messages! 👑")

async def stopemo(update: Update, context):
    allowed, msg = check_permission(update.effective_user.id, "owner", "/stopemo")
    if not allowed:
        await update.message.reply_text(msg)
        return
    global emoji_react_active
    emoji_react_active = False
    bot_num = (int(context.bot.id) % len(BOT_TOKENS)) + 1
    await update.message.reply_text(f"🤖 **BOT #{bot_num}** | ⏹️ **REACTIONS OFF!** 👑")

# ===== MAIN RUNNER =====
def run_single_bot(token, num):
    print(f"🤖 BOT {num} STARTING... 🎯 UNIQUE SINGLE+POWER MODE!")
    app = Application.builder().token(token).build()
    
    # 🔥 SINGLE BOT COMMANDS (ONLY 1 BOT REPLIES)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myrank", myrank))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("userinfo", userinfo))
    app.add_handler(CommandHandler("coinflip", coinflip))
    
    # 🔥 POWER COMMANDS (ALL 7 BOTS REPLY)
    app.add_handler(CommandHandler("promote", promote))
    app.add_handler(CommandHandler("depromote", depromote))
    app.add_handler(CommandHandler("ncloop", ncloop))
    app.add_handler(CommandHandler("ncloop2", ncloop2))
    app.add_handler(CommandHandler("ncloop3", ncloop3))
    app.add_handler(CommandHandler("ncloop4", ncloop4))
    app.add_handler(CommandHandler("slide", slide))
    app.add_handler(CommandHandler("stopslide", stopslide))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("emoreact", emoreact))
    app.add_handler(CommandHandler("stopemo", stopemo))
    
    # 🔥 MESSAGE HANDLER (ALL 7 WORK)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    
    bot_states[num-1]['app'] = app
    print(f"✅ BOT {num} READY! 🎯 SINGLE: /menu/myrank | 🔥 POWER: /ncloop/slide/emoreact")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    # Auto-set owner
    set_user_rank(OWNER_USER_ID, "owner")
    print("🚀 VAIBHAV ULTIMATE 7-BOT UNIQUE SYSTEM ACTIVATED!")
    print("🎯 SINGLE COMMANDS (/menu /myrank /status): **1 BOT ONLY**")
    print("🔥 POWER COMMANDS (/ncloop /slide /emoreact): **ALL 7 BOTS**")
    print("👑 Owner auto-set: 8477357886")
    print("✅ NEW: /ncloop vaibhav → Uses 'vaibhav' as custom name!")
    
    threads = []
    for i, token in enumerate(BOT_TOKENS, 1):
        t = threading.Thread(target=run_single_bot, args=(token, i), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(1)
    
    print("\n✅ ALL 7 BOTS + UNIQUE SYSTEM READY! 🚀🎯")
    print("📱 **TEST:** /menu (1 bot) → /ncloop vaibhav (7 bots!)")
    
    try:
        input("Press Enter to stop...")
    except:
        pass
