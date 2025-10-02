from pyrogram import Client, filters, types
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
import asyncio
import time
from datetime import datetime
import math
from typing import Dict, List, Set
import json

# Global variables for broadcast management
active_broadcasts: Dict[int, Dict] = {}
broadcast_status: Dict[int, Dict] = {}

class BroadcastManager:
    def __init__(self):
        self.active_broadcasts = {}
        self.broadcast_tasks = {}
    
    def start_broadcast(self, broadcast_id, user_ids, message, is_pinned=False):
        self.active_broadcasts[broadcast_id] = {
            'user_ids': user_ids,
            'message': message,
            'is_pinned': is_pinned,
            'start_time': time.time(),
            'current_index': 0,
            'status': {
                'total': len(user_ids),
                'successful': 0,
                'blocked': 0,
                'deleted': 0,
                'unsuccessful': 0,
                'progress': 0,
                'speed': 0,
                'eta': 0
            },
            'running': True
        }
        return broadcast_id
    
    def stop_broadcast(self, broadcast_id):
        if broadcast_id in self.active_broadcasts:
            self.active_broadcasts[broadcast_id]['running'] = False
            return True
        return False
    
    def get_broadcast_status(self, broadcast_id):
        return self.active_broadcasts.get(broadcast_id)

broadcast_manager = BroadcastManager()

def generate_progress_bar(percentage, length=20):
    filled = math.floor(length * percentage / 100)
    empty = length - filled
    return '█' * filled + '░' * empty

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def format_number(num):
    return f"{num:,}"

@Client.on_message(filters.command('users'))
async def user_count(client, message):
    if not message.from_user.id in client.admins:
        return await message.reply("❌ You are not authorized to use this command.")
    
    try:
        total_users = await client.mongodb.full_userbase()
        active_count = len(total_users)
        
        today = datetime.now().strftime("%Y-%m-%d")

        stats_text = f"""
📊 **User Statistics**

👥 **Total Users:** `{format_number(active_count)}`
"""
        await message.reply(stats_text)
        
    except Exception as e:
        await message.reply(f"❌ Error fetching user statistics: {e}")

@Client.on_message(filters.private & filters.command('broadcast'))
async def send_text(client, message):
    admin_ids = client.admins
    user_id = message.from_user.id
    
    if user_id not in admin_ids:
        return await message.reply("❌ You are not authorized to use this command.")
    
    if not message.reply_to_message:
        help_text = """
📢 **Broadcast Command Help**

**Usage:** Reply to a message with `/broadcast`

**Features:**
• Progress tracking with live updates
• Speed and ETA calculations  
• Stop broadcast anytime
• Detailed analytics
• FloodWait handling

**Quick Commands:**
`/broadcast` - Normal broadcast
`/pbroadcast` - Pinned broadcast  
`/stop_broadcast` - Stop active broadcast
`/broadcast_status` - Check progress
"""
        msg = await message.reply(help_text)
        await asyncio.sleep(10)
        await msg.delete()
        return

    # Generate unique broadcast ID
    broadcast_id = int(time.time())
    query = await client.mongodb.full_userbase()
    broadcast_msg = message.reply_to_message
    
    if not query:
        return await message.reply("❌ No users found in database.")

    # Start broadcast
    broadcast_manager.start_broadcast(broadcast_id, query, broadcast_msg)
    
    # Create status message with buttons
    keyboard = types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton("🛑 Stop Broadcast", f"stop_{broadcast_id}")],
        [types.InlineKeyboardButton("📊 Refresh Status", f"refresh_{broadcast_id}")]
    ])
    
    status_msg = await message.reply(
        "🔄 **Initializing Broadcast...**\n"
        "Please wait while we start sending messages...",
        reply_markup=keyboard
    )
    
    # Start broadcast task
    asyncio.create_task(
        execute_broadcast(client, broadcast_id, status_msg, broadcast_msg, False)
    )

# -------------------------------
# Enhanced Pinned Broadcast Command
# -------------------------------
@Client.on_message(filters.private & filters.command('pbroadcast'))
async def pin_bdcst_text(client, message):
    admin_ids = client.admins
    user_id = message.from_user.id
    
    if user_id not in admin_ids:
        return await message.reply("❌ You are not authorized to use this command.")
    
    if not message.reply_to_message:
        help_text = """
📌 **Pinned Broadcast Command Help**

**Usage:** Reply to a message with `/pbroadcast`

**Features:**
• Messages will be pinned in user chats
• Progress tracking with live updates
• Stop functionality
• Detailed delivery reports

**Note:** Users need to allow pinning for this to work.
"""
        msg = await message.reply(help_text)
        await asyncio.sleep(10)
        await msg.delete()
        return

    # Generate unique broadcast ID
    broadcast_id = int(time.time())
    query = await client.mongodb.full_userbase()
    broadcast_msg = message.reply_to_message
    
    if not query:
        return await message.reply("❌ No users found in database.")

    # Start broadcast
    broadcast_manager.start_broadcast(broadcast_id, query, broadcast_msg, True)
    
    # Create status message with buttons
    keyboard = types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton("🛑 Stop Broadcast", f"stop_{broadcast_id}")],
        [types.InlineKeyboardButton("📊 Refresh Status", f"refresh_{broadcast_id}")]
    ])
    
    status_msg = await message.reply(
        "📌 **Initializing Pinned Broadcast...**\n"
        "Please wait while we start sending and pinning messages...",
        reply_markup=keyboard
    )
    
    # Start broadcast task
    asyncio.create_task(
        execute_broadcast(client, broadcast_id, status_msg, broadcast_msg, True)
    )

# -------------------------------
# Broadcast Execution Function
# -------------------------------
async def execute_broadcast(client, broadcast_id, status_msg, broadcast_msg, is_pinned=False):
    broadcast_data = broadcast_manager.get_broadcast_status(broadcast_id)
    if not broadcast_data:
        return
    
    user_ids = broadcast_data['user_ids']
    total_users = len(user_ids)
    start_time = time.time()
    last_update_time = start_time
    
    for index, chat_id in enumerate(user_ids):
        # Check if broadcast was stopped
        if not broadcast_data['running']:
            await update_final_status(client, status_msg, broadcast_data, "STOPPED", broadcast_id)
            return
        
        try:
            # Send message
            sent_msg = await broadcast_msg.copy(chat_id)
            broadcast_data['status']['successful'] += 1
            
            # Pin message if required
            if is_pinned and sent_msg:
                try:
                    await client.pin_chat_message(
                        chat_id=chat_id, 
                        message_id=sent_msg.id, 
                        both_sides=True
                    )
                except Exception as e:
                    print(f"Failed to pin message for {chat_id}: {e}")
                    # Continue even if pinning fails
                    
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                sent_msg = await broadcast_msg.copy(chat_id)
                broadcast_data['status']['successful'] += 1
                if is_pinned and sent_msg:
                    await client.pin_chat_message(chat_id=chat_id, message_id=sent_msg.id)
            except Exception:
                broadcast_data['status']['unsuccessful'] += 1
                
        except UserIsBlocked:
            broadcast_data['status']['blocked'] += 1
        except InputUserDeactivated:
            broadcast_data['status']['deleted'] += 1
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")
            broadcast_data['status']['unsuccessful'] += 1
        
        # Update progress
        broadcast_data['current_index'] = index + 1
        progress = (index + 1) / total_users * 100
        
        # Calculate speed and ETA
        current_time = time.time()
        time_elapsed = current_time - start_time
        messages_per_second = (index + 1) / time_elapsed if time_elapsed > 0 else 0
        eta_seconds = (total_users - (index + 1)) / messages_per_second if messages_per_second > 0 else 0
        
        broadcast_data['status'].update({
            'progress': progress,
            'speed': messages_per_second,
            'eta': eta_seconds
        })
        
        # Update status message periodically (every 2 seconds or 50 messages)
        if current_time - last_update_time >= 2 or index % 50 == 0:
            await update_status_message(client, status_msg, broadcast_data, broadcast_id, is_pinned)
            last_update_time = current_time
        
        # Small delay to avoid flooding
        await asyncio.sleep(0.1)
    
    # Broadcast completed
    await update_final_status(client, status_msg, broadcast_data, "COMPLETED", broadcast_id)

# -------------------------------
# Status Update Functions
# -------------------------------
async def update_status_message(client, status_msg, broadcast_data, broadcast_id, is_pinned):
    status = broadcast_data['status']
    progress_bar = generate_progress_bar(status['progress'])
    
    status_text = f"""
{'📌' if is_pinned else '📢'} **{'Pinned ' if is_pinned else ''}Broadcast in Progress**

{progress_bar} `{status['progress']:.1f}%`

📊 **Progress:** `{format_number(broadcast_data['current_index'])}/{format_number(status['total'])}`
✅ **Successful:** `{format_number(status['successful'])}`
❌ **Blocked:** `{format_number(status['blocked'])}`
🗑️ **Deleted:** `{format_number(status['deleted'])}`
⚠️ **Failed:** `{format_number(status['unsuccessful'])}`

⚡ **Speed:** `{status['speed']:.1f} msg/sec`
⏱️ **ETA:** `{format_time(status['eta'])}`

**Broadcast ID:** `{broadcast_id}`
"""
    
    keyboard = types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton("🛑 Stop Broadcast", f"stop_{broadcast_id}")],
        [types.InlineKeyboardButton("📊 Refresh Status", f"refresh_{broadcast_id}")]
    ])
    
    try:
        await status_msg.edit_text(status_text, reply_markup=keyboard)
    except Exception as e:
        print(f"Failed to update status: {e}")

async def update_final_status(client, status_msg, broadcast_data, status_type, broadcast_id):
    status = broadcast_data['status']
    total_time = time.time() - broadcast_data['start_time']
    
    if status_type == "COMPLETED":
        status_emoji = "✅"
        status_text = "Completed"
    else:
        status_emoji = "🛑"
        status_text = "Stopped by User"
    
    final_text = f"""
{status_emoji} **Broadcast {status_text}**

📊 **Final Statistics:**
├ ✅ **Successful:** `{format_number(status['successful'])}`
├ ❌ **Blocked:** `{format_number(status['blocked'])}`
├ 🗑️ **Deleted:** `{format_number(status['deleted'])}`
├ ⚠️ **Failed:** `{format_number(status['unsuccessful'])}`
└ 👥 **Total Processed:** `{format_number(broadcast_data['current_index'])}`

⏱️ **Total Time:** `{format_time(total_time)}`
📈 **Average Speed:** `{(status['successful'] / total_time):.1f} msg/sec`
🎯 **Success Rate:** `{(status['successful'] / broadcast_data['current_index'] * 100) if broadcast_data['current_index'] > 0 else 0:.1f}%`

**Broadcast ID:** `{broadcast_id}`
"""
    
    try:
        await status_msg.edit_text(final_text, reply_markup=None)
    except Exception as e:
        print(f"Failed to update final status: {e}")
    
    # Clean up
    if broadcast_id in broadcast_manager.active_broadcasts:
        del broadcast_manager.active_broadcasts[broadcast_id]

# -------------------------------
# Stop Broadcast Command
# -------------------------------
@Client.on_message(filters.private & filters.command('stop_broadcast'))
async def stop_broadcast(client, message):
    admin_ids = client.admins
    user_id = message.from_user.id
    
    if user_id not in admin_ids:
        return await message.reply("❌ You are not authorized to use this command.")
    
    if not broadcast_manager.active_broadcasts:
        return await message.reply("❌ No active broadcasts found.")
    
    # Stop all active broadcasts
    stopped_count = 0
    for broadcast_id in list(broadcast_manager.active_broadcasts.keys()):
        if broadcast_manager.stop_broadcast(broadcast_id):
            stopped_count += 1
    
    await message.reply(f"🛑 Stopped {stopped_count} active broadcast(s).")

# -------------------------------
# Broadcast Status Command
# -------------------------------
@Client.on_message(filters.private & filters.command('broadcast_status'))
async def broadcast_status_cmd(client, message):
    admin_ids = client.admins
    user_id = message.from_user.id
    
    if user_id not in admin_ids:
        return await message.reply("❌ You are not authorized to use this command.")
    
    if not broadcast_manager.active_broadcasts:
        return await message.reply("📭 No active broadcasts found.")
    
    status_text = "📊 **Active Broadcasts**\n\n"
    
    for broadcast_id, data in broadcast_manager.active_broadcasts.items():
        status = data['status']
        progress_bar = generate_progress_bar(status['progress'])
        
        status_text += f"""
**Broadcast ID:** `{broadcast_id}`
**Type:** {'📌 Pinned' if data['is_pinned'] else '📢 Normal'}
{progress_bar} `{status['progress']:.1f}%`
**Progress:** `{format_number(data['current_index'])}/{format_number(status['total'])}`
**Speed:** `{status['speed']:.1f} msg/sec`
**ETA:** `{format_time(status['eta'])}`
────────────────────
"""
    
    keyboard = types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton("🛑 Stop All Broadcasts", "stop_all_broadcasts")]
    ])
    
    await message.reply(status_text, reply_markup=keyboard)

# -------------------------------
# Callback Query Handlers
# -------------------------------
@Client.on_callback_query(filters.regex(r"stop_(\d+)"))
async def stop_broadcast_callback(client, callback_query):
    broadcast_id = int(callback_query.matches[0].group(1))
    
    if broadcast_manager.stop_broadcast(broadcast_id):
        await callback_query.answer("Broadcast stopped successfully!")
        await callback_query.message.edit_text(
            f"🛑 Broadcast `{broadcast_id}` has been stopped by user.",
            reply_markup=None
        )
    else:
        await callback_query.answer("Broadcast not found or already completed!")

@Client.on_callback_query(filters.regex(r"refresh_(\d+)"))
async def refresh_status_callback(client, callback_query):
    broadcast_id = int(callback_query.matches[0].group(1))
    broadcast_data = broadcast_manager.get_broadcast_status(broadcast_id)
    
    if broadcast_data:
        await update_status_message(
            client, 
            callback_query.message, 
            broadcast_data, 
            broadcast_id, 
            broadcast_data['is_pinned']
        )
        await callback_query.answer("Status refreshed!")
    else:
        await callback_query.answer("Broadcast not found!")

@Client.on_callback_query(filters.regex("stop_all_broadcasts"))
async def stop_all_broadcasts_callback(client, callback_query):
    stopped_count = 0
    for broadcast_id in list(broadcast_manager.active_broadcasts.keys()):
        if broadcast_manager.stop_broadcast(broadcast_id):
            stopped_count += 1
    
    await callback_query.answer(f"Stopped {stopped_count} broadcasts!")
    await callback_query.message.edit_text(
        f"🛑 Stopped all active broadcasts ({stopped_count} total).",
        reply_markup=None
    )

# -------------------------------
# Broadcast Analytics Command
# -------------------------------
@Client.on_message(filters.private & filters.command('stats'))
async def broadcast_stats(client, message):
    admin_ids = client.admins
    user_id = message.from_user.id
    
    if user_id not in admin_ids:
        return await message.reply("❌ You are not authorized to use this command.")
    
    total_users = await client.mongodb.full_userbase()
    
    stats_text = f"""
📈 **Broadcast Analytics**

👥 **User Base:** `{format_number(len(total_users))}`
🔄 **Active Broadcasts:** `{len(broadcast_manager.active_broadcasts)}`

🚀 **Quick Actions:**
• `/broadcast` - Send broadcast
• `/pbroadcast` - Send pinned broadcast  
• `/broadcast_status` - Check progress
• `/stop_broadcast` - Stop broadcasts

💡 **Tips:**
• Use pinned broadcasts for important announcements
• Monitor speed to avoid FloodWait
• Stop broadcasts if needed using the button
"""
    
    await message.reply(stats_text)
