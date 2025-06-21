
import asyncio
import json
from bot import Bot, web_app
from pyrogram import compose

# Static default fallback message templates (can be overridden per setup entry if needed)
default_messages = {
    'START': "<blockquote><b>Hᴇʏ, {mention}✌🏻.  I ʜᴏᴘᴇ ʏᴏᴜ're ғᴇᴇʟɪɴɢ ᴛʜᴇ ᴘᴏᴡᴇʀ ᴏғ 𝐒ʜᴀᴅᴏᴡ Mᴏɴᴀʀᴄʜ .</b></blockquote>\n\n"
         "<blockquote expandable><b>I'm 𝐓ʜᴇ Uʟᴛɪᴍᴀᴛᴇ Fɪʟᴇ Sʜᴀʀɪɴɢ Bᴏᴛ, ʙᴜɪʟᴛ ᴛᴏ ʀᴜʟᴇ ᴛʜᴇ 𝐒ʜᴀᴅᴏᴡ Rᴇᴀʟᴍ 🖤\n\n"
         "‣ 🔱 Sᴛᴏʀᴇ & Sʜᴀʀᴇ Fɪʟᴇs ᴡɪᴛʜ ᴀ Sɪɴɢʟᴇ Cʟɪᴄᴋ.\n"
         "‣ 🛡️ Iɴꜰɪɴɪᴛᴇ Fɪʟᴇ Mᴀɴᴀɢᴇᴍᴇɴᴛ Sʏꜱᴛᴇᴍ.\n"
         "‣ 📂 Pᴏsᴛ Fɪʟᴇs ɪɴ 𝐀ɴɪᴍᴇ Mᴏɴᴀʀᴄʜ 👑 Tᴇᴍᴘʟᴀᴛᴇ.\n\n"
         "𝐍ᴏᴡ, 𝐓ʜᴇ Fɪʟᴇ Rᴇᴀʟᴍ Iꜱ Uɴᴅᴇʀ Mʏ Cᴏɴᴛʀᴏʟ .\n\n"
         "𝐀ʀᴇ Yᴏᴜ Rᴇᴀᴅʏ ᴛᴏ Dᴏᴍɪɴᴀᴛᴇ, {mention}-Sᴀᴍᴀ? 👑</b></blockquote>",
    'FSUB': '',
    'ABOUT': 'client.messages.get('ABOUT', 'No Start Message').format(
    owner_id=client.owner,
    bot_username=client.username,
    first=query.from_user.first_name,
    last=query.from_user.last_name,
    username=None if not query.from_user.username else '@' + query.from_user.username,
    mention=query.from_user.mention,
    id=query.from_user.id
)',
    'REPLY': 'reply_text',
    'START_PHOTO': '',
    'FSUB_PHOTO': ''
}

async def main():
    app = []

    # Load setup.json
    with open("setup.json", "r") as f:
        setups = json.load(f)

    # Loop through each bot setup config
    for config in setups:
        session = config["session"]
        workers = config["workers"]
        db = config["db"]
        fsubs = config["fsubs"]
        token = config["token"]
        admins = config["admins"]
        messages = config.get("messages", default_messages)
        auto_del = config["auto_del"]
        db_uri = config["db_uri"]
        db_name = config["db_name"]
        api_id = int(config["api_id"])
        api_hash = config["api_hash"]
        protect = config["protect"]
        disable_btn = config["disable_btn"]

        app.append(
            Bot(
                session,
                workers,
                db,
                fsubs,
                token,
                admins,
                messages,
                auto_del,
                db_uri,
                db_name,
                api_id,
                api_hash,
                protect,
                disable_btn
            )
        )

    await compose(app)


async def runner():
    await asyncio.gather(
        main(),
        web_app()
    )

asyncio.run(runner())
