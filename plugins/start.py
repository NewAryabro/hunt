from helper.helper_func import *
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import humanize
from config import MSG_EFFECT
import time
from collections import defaultdict


user_requests = defaultdict(list)
RATE_LIMIT_WINDOW = 60 
MAX_REQUESTS_PER_WINDOW = 5 

def rate_limit(user_id):
    """Check if user has exceeded rate limit"""
    now = time.time()
    
    user_requests[user_id] = [req_time for req_time in user_requests[user_id] 
                             if now - req_time < RATE_LIMIT_WINDOW]
    
    if len(user_requests[user_id]) >= MAX_REQUESTS_PER_WINDOW:
        return False
    
    user_requests[user_id].append(now)
    return True

def get_remaining_time(user_id):
    """Get remaining time until user can make another request"""
    if user_id not in user_requests or not user_requests[user_id]:
        return 0
    
    now = time.time()
    oldest_request = min(user_requests[user_id])
    next_available = oldest_request + RATE_LIMIT_WINDOW
    return max(0, int(next_available - now))

@Client.on_message(filters.command('start') & filters.private)
@force_sub
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in client.admins and not rate_limit(user_id):
        remaining_time = get_remaining_time(user_id)
        if remaining_time > 0:
            readable_time = get_readable_time(remaining_time)
            rate_limit_msg = await message.reply(
                f"**⚠️ Please Wait**\n\n"
                f"**{readable_time}** before making another request\n"
             #   f"`{MAX_REQUESTS_PER_WINDOW} req/min limit`\n\n"
             #   f"_Auto-deleting in 8s..._"
            )
            await asyncio.sleep(8)
            try:
                await rate_limit_msg.delete()
            except:
                pass
            return
    present = await client.mongodb.present_user(user_id)
    if not present:
        try:
            await client.mongodb.add_user(user_id)
        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Error adding a user:\n{e}")
    
    is_banned = await client.mongodb.is_banned(user_id)
    if is_banned:
        return await message.reply("**You have been banned from using this bot!**")
    
    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        string = await decode(base64_string)
        argument = string.split("-")
        
        ids = []
        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db))
                end = int(int(argument[2]) / abs(client.db))
                ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))
            except Exception as e:
                client.LOGGER(__name__, client.name).warning(f"Error decoding IDs: {e}")
                return

        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except Exception as e:
                client.LOGGER(__name__, client.name).warning(f"Error decoding ID: {e}")
                return
        
        temp_msg = await message.reply("Wait A Sec..")
        
        try:
            messages = await get_messages(client, ids)
        except Exception as e:
            await temp_msg.edit_text("Something Went Wrong..!")
            client.LOGGER(__name__, client.name).warning(f"Error getting messages: {e}")
            return
        finally:
            if messages:
                await temp_msg.delete()
            else:
                await temp_msg.edit("Couldn't find the files in the database.")

        yugen_msgs = []

        for msg in messages:
            caption = (
                client.messages.get('CAPTION', '').format(
                    previouscaption=f"<blockquote>{msg.caption.html}</blockquote>" if msg.caption else f"<blockquote>{msg.document.file_name}</blockquote>"
                )
                if bool(client.messages.get('CAPTION', '')) and bool(msg.document)
                else ("" if not msg.caption else f"<blockquote>{msg.caption.html}</blockquote>")
            )

            reply_markup = msg.reply_markup if not client.disable_btn else None

            try:
                copied_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, 
                                            reply_markup=(reply_markup if not client.disable_btn else None), protect_content=client.protect)
                yugen_msgs.append(copied_msg)
            except FloodWait as e:
                await asyncio.sleep(e.x)
                copied_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, 
                                            reply_markup=(reply_markup if not client.disable_btn else None), protect_content=client.protect)
                yugen_msgs.append(copied_msg)
            except Exception as e:
                client.LOGGER(__name__, client.name).warning(f"Failed to send message: {e}")
                pass
        
        if messages:
            if client.auto_del > 0:
                enter = text
                buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔁 Forward to Saved Messages", switch_inline_query_current_chat=""),
                    InlineKeyboardButton("💬 Join Chat", url="https://t.me/WeebChat2u")
                ]
            ]
        )

        k = await client.send_message(
            chat_id=message.from_user.id,
            text=(
                f"<b><i>This File will delete automatically in "
                f"{humanize.naturaldelta(client.auto_del)}."
                " Forward to your Saved Messages..!                            "
                "💬𝗝𝗼𝗶𝗻𝗖𝗵𝗮𝘁: @WeebChat2u </i></b>"
            ),
            reply_markup=buttons
        )
                asyncio.create_task(delete_files(yugen_msgs, client, k, enter))
                return
    else:
        buttons = [
            [InlineKeyboardButton("📢 Mᴀɪɴ Cʜᴀɴɴᴇʟ", url="https://t.me/TeluguFlixs")],
            [InlineKeyboardButton("🫧  Aɴɪᴍᴇ ɪɴᴅᴇx ", url="https://t.me/Animes2u_Index")],
            [InlineKeyboardButton("⚠️ ᴀʙᴏᴜᴛ ⚠️", callback_data="about"), InlineKeyboardButton("💰 Pʀᴏᴍᴏ 💰", url="https://t.me/LuffyDSunGodBot")]
        ]
        if user_id in client.admins:
            buttons.insert(0, [InlineKeyboardButton("⛩️ ꜱᴇᴛᴛɪɴɢꜱ ⛩️", callback_data="settings")])
        
        photo = client.messages.get("START_PHOTO", "")
        if photo:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=photo,
                caption=client.messages.get('START', 'No Start Msg').format(
                    first=message.from_user.first_name,
                    last=message.from_user.last_name,
                    username=None if not message.from_user.username else '@' + message.from_user.username,
                    mention=message.from_user.mention,
                    id=message.from_user.id
                ),
                message_effect_id=MSG_EFFECT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await client.send_message(
                chat_id=message.chat.id,
                text=client.messages.get('START', 'No Start Message').format(
                    first=message.from_user.first_name,
                    last=message.from_user.last_name,
                    username=None if not message.from_user.username else '@' + message.from_user.username,
                    mention=message.from_user.mention,
                    id=message.from_user.id
                ),
                message_effect_id=MSG_EFFECT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        return
