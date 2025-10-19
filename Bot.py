import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
YOUR_USER_ID = int(os.getenv('YOUR_USER_ID'))

# Validate environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not YOUR_USER_ID:
    raise ValueError("YOUR_USER_ID environment variable is required")

# Storage files
CHANNELS_FILE = "channels.json"
MESSAGES_FILE = "messages.json"

# Store scheduled messages and channels
scheduled_messages = {}
channels = {}

def load_data():
    """Load channels and messages from files"""
    global channels, scheduled_messages
    
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, 'r') as f:
                channels = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading channels: {e}")
            channels = {}
    
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, 'r') as f:
                saved_messages = json.load(f)
                # Convert back to ScheduledMessage objects
                for msg_id, msg_data in saved_messages.items():
                    scheduled_messages[msg_id] = ScheduledMessage(
                        message_id=msg_id,
                        chat_id=msg_data['chat_id'],
                        text=msg_data['text'],
                        scheduled_time=datetime.fromisoformat(msg_data['scheduled_time']),
                        channel=msg_data['channel'],
                        active=msg_data['active']
                    )
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading messages: {e}")
            scheduled_messages = {}

def save_data():
    """Save channels and messages to files"""
    try:
        with open(CHANNELS_FILE, 'w') as f:
            json.dump(channels, f, indent=2)
        
        # Convert ScheduledMessage objects to serializable format
        messages_to_save = {}
        for msg_id, msg_data in scheduled_messages.items():
            messages_to_save[msg_id] = {
                'chat_id': msg_data.chat_id,
                'text': msg_data.text,
                'scheduled_time': msg_data.scheduled_time.isoformat(),
                'channel': msg_data.channel,
                'active': msg_data.active
            }
        
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages_to_save, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

class ScheduledMessage:
    def __init__(self, message_id, chat_id, text, scheduled_time, channel, job=None, active=True):
        self.message_id = message_id
        self.chat_id = chat_id
        self.text = text
        self.scheduled_time = scheduled_time
        self.channel = channel
        self.job = job
        self.active = active

async def check_authorized(update: Update) -> bool:
    """Check if the user is authorized (only you)"""
    if update.effective_user.id != YOUR_USER_ID:
        if update.message:
            await update.message.reply_text("❌ Unauthorized access. This bot is private.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    if not await check_authorized(update):
        return
    
    await update.message.reply_text(
        "🤖 Welcome to Your Personal Schedule Bot!\n\n"
        "📋 Available commands:\n"
        "/addchannel <channel_id> <name> - Add a channel\n"
        "/listchannels - List all channels\n"
        "/schedule <channel_name> <time_minutes> <message> - Schedule a message\n"
        "/listschedule - List all scheduled messages\n"
        "/deletechannel <channel_name> - Delete a channel\n"
        "/help - Show this help message"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    if not await check_authorized(update):
        return
    
    help_text = """
🤖 **Your Personal Schedule Bot**

**Commands:**
• `/addchannel <channel_id> <name>` - Add a channel
• `/listchannels` - List all channels  
• `/deletechannel <name>` - Delete a channel
• `/schedule <channel> <minutes> <message>` - Schedule a message
• `/listschedule` - List scheduled messages
• `/help` - Show this help

**Examples:**
• `/addchannel -100123456789 my_channel`
• `/schedule my_channel 30 Hello! Check https://example.com`
• `/schedule my_channel 60 Daily update with URL`

**Note:** Make sure the bot is admin in your channels!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a channel to the bot."""
    if not await check_authorized(update):
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: `/addchannel <channel_id> <channel_name>`\n"
            "Example: `/addchannel -100123456789 my_channel`",
            parse_mode='Markdown'
        )
        return
    
    channel_id = context.args[0]
    channel_name = context.args[1].lower()
    
    # Validate channel ID format
    if not channel_id.startswith('-100'):
        await update.message.reply_text(
            "❌ Invalid channel ID. Channel IDs should start with `-100`\n"
            "Make sure to use the channel ID, not username!",
            parse_mode='Markdown'
        )
        return
    
    # Check if channel name already exists
    if channel_name in channels:
        await update.message.reply_text(
            f"❌ Channel name '{channel_name}' already exists. Choose a different name."
        )
        return
    
    # Add channel
    channels[channel_name] = channel_id
    save_data()
    
    await update.message.reply_text(
        f"✅ Channel added successfully!\n\n"
        f"📝 Name: `{channel_name}`\n"
        f"🆔 ID: `{channel_id}`",
        parse_mode='Markdown'
    )

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all added channels."""
    if not await check_authorized(update):
        return
    
    if not channels:
        await update.message.reply_text("📭 No channels added yet.")
        return
    
    message = "📋 Your Channels:\n\n"
    for name, channel_id in channels.items():
        message += f"🔹 `{name}`: `{channel_id}`\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a channel."""
    if not await check_authorized(update):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/deletechannel <channel_name>`", parse_mode='Markdown')
        return
    
    channel_name = context.args[0].lower()
    
    if channel_name not in channels:
        await update.message.reply_text(f"❌ Channel `{channel_name}` not found.", parse_mode='Markdown')
        return
    
    # Check if there are any scheduled messages for this channel
    channel_has_messages = any(msg.channel == channel_name for msg in scheduled_messages.values())
    
    if channel_has_messages:
        await update.message.reply_text(
            f"⚠️ Channel `{channel_name}` has scheduled messages. "
            f"Please delete them first using `/listschedule`",
            parse_mode='Markdown'
        )
        return
    
    del channels[channel_name]
    save_data()
    
    await update.message.reply_text(f"✅ Channel `{channel_name}` deleted successfully!", parse_mode='Markdown')

async def schedule_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedule a message to be sent to a specific channel."""
    if not await check_authorized(update):
        return
    
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ Usage: `/schedule <channel_name> <time_minutes> <message>`\n"
            "Example: `/schedule my_channel 30 Hello world! https://example.com`",
            parse_mode='Markdown'
        )
        return

    try:
        channel_name = context.args[0].lower()
        time_minutes = int(context.args[1])
        message_text = ' '.join(context.args[2:])
        
        # Check if channel exists
        if channel_name not in channels:
            await update.message.reply_text(
                f"❌ Channel `{channel_name}` not found. Use `/listchannels` to see available channels.",
                parse_mode='Markdown'
            )
            return
        
        if time_minutes <= 0:
            await update.message.reply_text("❌ Please provide a positive time value in minutes.")
            return

        if len(message_text) > 4000:
            await update.message.reply_text("❌ Message is too long. Maximum 4000 characters.")
            return

        # Calculate scheduled time
        scheduled_time = datetime.now() + timedelta(minutes=time_minutes)
        
        # Create message ID
        message_id = f"msg_{int(datetime.now().timestamp())}"

        # Store the scheduled message
        scheduled_messages[message_id] = ScheduledMessage(
            message_id=message_id,
            chat_id=update.effective_chat.id,
            text=message_text,
            scheduled_time=scheduled_time,
            channel=channel_name
        )

        # Schedule the job
        job = context.job_queue.run_once(
            send_scheduled_message,
            time_minutes * 60,
            data=message_id,
            name=message_id
        )
        
        scheduled_messages[message_id].job = job
        save_data()

        # Create control buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ ON", callback_data=f"enable_{message_id}"),
                InlineKeyboardButton("❌ OFF", callback_data=f"disable_{message_id}")
            ],
            [
                InlineKeyboardButton("🗑️ DELETE", callback_data=f"delete_{message_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Message scheduled successfully!\n\n"
            f"📝 Message: {message_text}\n"
            f"📢 Channel: `{channel_name}`\n"
            f"⏰ Time: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🆔 ID: `{message_id}`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number for time.")

async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    """Send the scheduled message to the channel."""
    job = context.job
    message_id = job.data
    
    if message_id in scheduled_messages:
        message_data = scheduled_messages[message_id]
        
        if message_data.active and message_data.channel in channels:
            try:
                channel_id = channels[message_data.channel]
                
                # Send message to channel
                await context.bot.send_message(
                    chat_id=channel_id,
                    text=message_data.text,
                    disable_web_page_preview=False
                )
                logger.info(f"Message {message_id} sent to channel {message_data.channel}")
                
                # Notify the user
                await context.bot.send_message(
                    chat_id=message_data.chat_id,
                    text=f"✅ Scheduled message sent to `{message_data.channel}`!\n\n{message_data.text}",
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Error sending message to channel: {e}")
                await context.bot.send_message(
                    chat_id=message_data.chat_id,
                    text=f"❌ Error sending message to `{message_data.channel}`: {str(e)}",
                    parse_mode='Markdown'
                )
        
        # Clean up
        if message_id in scheduled_messages:
            del scheduled_messages[message_id]
            save_data()

async def list_scheduled_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all scheduled messages."""
    if not await check_authorized(update):
        return
    
    if not scheduled_messages:
        await update.message.reply_text("📭 No scheduled messages.")
        return

    message_text = "📋 Scheduled Messages:\n\n"
    
    for msg_id, msg_data in scheduled_messages.items():
        status = "✅ ACTIVE" if msg_data.active else "❌ INACTIVE"
        time_remaining = msg_data.scheduled_time - datetime.now()
        minutes_remaining = max(0, int(time_remaining.total_seconds() / 60))
        
        message_text += (
            f"🆔 `{msg_id}`\n"
            f"📢 Channel: `{msg_data.channel}`\n"
            f"📝 {msg_data.text[:50]}...\n"
            f"⏰ {msg_data.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏳ In: {minutes_remaining} minutes\n"
            f"📊 {status}\n"
            f"────────────────────\n"
        )

    await update.message.reply_text(message_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    if not await check_authorized(update):
        return
    
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("enable_"):
        message_id = data[7:]
        if message_id in scheduled_messages:
            scheduled_messages[message_id].active = True
            save_data()
            await query.edit_message_text(
                f"✅ Message enabled!\n\n{scheduled_messages[message_id].text}",
                reply_markup=create_control_keyboard(message_id)
            )
    
    elif data.startswith("disable_"):
        message_id = data[8:]
        if message_id in scheduled_messages:
            scheduled_messages[message_id].active = False
            save_data()
            await query.edit_message_text(
                f"❌ Message disabled!\n\n{scheduled_messages[message_id].text}",
                reply_markup=create_control_keyboard(message_id)
            )
    
    elif data.startswith("delete_"):
        message_id = data[7:]
        if message_id in scheduled_messages:
            # Cancel the job
            if scheduled_messages[message_id].job:
                scheduled_messages[message_id].job.schedule_removal()
            # Remove from storage
            del scheduled_messages[message_id]
            save_data()
            await query.edit_message_text("🗑️ Message deleted!")

def create_control_keyboard(message_id):
    """Create control keyboard for a message."""
    keyboard = [
        [
            InlineKeyboardButton("✅ ON", callback_data=f"enable_{message_id}"),
            InlineKeyboardButton("❌ OFF", callback_data=f"disable_{message_id}")
        ],
        [
            InlineKeyboardButton("🗑️ DELETE", callback_data=f"delete_{message_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def main():
    """Start the bot."""
    # Load existing data
    load_data()
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addchannel", add_channel))
    application.add_handler(CommandHandler("listchannels", list_channels))
    application.add_handler(CommandHandler("deletechannel", delete_channel))
    application.add_handler(CommandHandler("schedule", schedule_message))
    application.add_handler(CommandHandler("listschedule", list_scheduled_messages))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Start the Bot
    logger.info("Bot is starting...")
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
