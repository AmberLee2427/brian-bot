import discord
from discord.ext import commands
import openai
import os
import json # <-- Required for character sheet logic
from dotenv import load_dotenv
import asyncio
import re
import tiktoken
from collections import defaultdict
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import string
from openai import OpenAI # Make sure to add this at the top with other imports
from cogs.gameplay import roll_dice


# --- Logging Setup ---
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler('logs/brian_bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

logger = setup_logging()

# --- Load Environment Variables ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# --- OpenAI & Bot Initialization ---
if not OPENAI_API_KEY or not DISCORD_TOKEN:
    logger.critical("FATAL: DISCORD_TOKEN or OPENAI_API_KEY not found in .env file!")
    exit()

try:
    logger.info("Initializing OpenAI client...")
    client = OpenAI(api_key=OPENAI_API_KEY, timeout=30)
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    exit()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Configuration & Global State ---
BRIAN_SYSTEM_PROMPT = ""
INSTRUCTIONS_FILE_NAME = "brian_instructions.txt"
MODEL_NAME = "gpt-4"
MAX_TOKENS_FOR_RESPONSE = 1500

# Security settings
ALLOWED_ROLES = []  # Add role IDs that are allowed to use certain commands
ADMIN_ROLES = []    # Add role IDs that have admin privileges

# --- Rate Limiting Setup ---
class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = defaultdict(list)
    
    def is_rate_limited(self, user_id: int) -> bool:
        now = datetime.now()
        user_requests = self.requests[user_id]
        
        # Remove old requests
        user_requests = [req_time for req_time in user_requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        self.requests[user_id] = user_requests
        
        if len(user_requests) >= self.max_requests:
            return True
        
        user_requests.append(now)
        return False

# Initialize rate limiters
mention_limiter = RateLimiter(max_requests=5, time_window=60)  # 5 requests per minute
command_limiter = RateLimiter(max_requests=10, time_window=60)  # 10 commands per minute

# --- Input Validation ---
def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks while preserving conversation context.
    
    This function:
    - Removes only potentially harmful control characters
    - Preserves all valid Discord formatting (markdown, mentions, emojis)
    - Preserves all printable characters including spaces and punctuation
    - Limits length to prevent abuse while keeping normal conversation intact
    """
    if not text:
        return ""
        
    # Remove only potentially harmful control characters while preserving formatting
    # This preserves: markdown, mentions, emojis, and all normal conversation elements
    text = ''.join(char for char in text if char in string.printable or char in '\n\r\t')
    
    # Limit length to prevent abuse while keeping normal conversation intact
    # Discord's message limit is 2000, we use 1000 to leave room for bot's response formatting
    return text[:1000]

def validate_channel_name(name: str) -> bool:
    """Validate channel name format."""
    # Discord channel names can only contain lowercase letters, numbers, and hyphens
    return bool(re.match(r'^[a-z0-9-]+$', name.lower()))

def has_permission(member: discord.Member, required_roles: list) -> bool:
    """Check if a member has the required roles."""
    if not required_roles:  # If no roles are specified, allow everyone
        return True
    return any(role.id in required_roles for role in member.roles)

def validate_api_key(api_key: str) -> bool:
    """Validate the format of API keys."""
    if not api_key:
        return False
    # OpenAI API keys start with 'sk-' and are 51 characters long
    if api_key.startswith('sk-') and len(api_key) == 51:
        return True
    # Discord tokens are typically longer and don't have a specific prefix
    if len(api_key) >= 59:  # Discord tokens are typically 59+ characters
        return True
    return False

# Channels for the !find command
SEARCHABLE_CHANNEL_IDS = [
    # ADD YOUR CHANNEL IDS HERE
    # 123456789012345678, # example-channel-1
    # 876543210987654321, # example-channel-2
]


# --- Helper Functions ---
def perform_roll(dice_string: str):
    """A simple dice roller that returns a formatted string."""
    try:
        rolls, modifier, total = roll_dice(dice_string)
        
        mod_str = f" + {modifier}" if modifier > 0 else f" - {abs(modifier)}" if modifier < 0 else ""
        return f"Brian rolls `{dice_string}`...\n**Result:** `{rolls}`{mod_str} = **{total}**"

    except Exception:
        return f"Brian confused by `{dice_string}`. Is not good dice."


# --- Bot Events ---
@bot.event
async def on_ready():
    try:
        logger.info("=== Bot Starting Up ===")
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
        logger.info(f"Connected to {len(bot.guilds)} guilds:")
        for guild in bot.guilds:
            logger.info(f"- {guild.name} (ID: {guild.id})")
        
        # Load personality
        global BRIAN_SYSTEM_PROMPT
        try:
            logger.info(f"Attempting to load instructions from '{INSTRUCTIONS_FILE_NAME}'")
            if not os.path.exists(INSTRUCTIONS_FILE_NAME):
                raise FileNotFoundError(f"File not found: {INSTRUCTIONS_FILE_NAME}")
            
            with open(INSTRUCTIONS_FILE_NAME, 'r', encoding='utf-8') as f:
                BRIAN_SYSTEM_PROMPT = f.read()
            logger.info(f"Successfully loaded instructions from '{INSTRUCTIONS_FILE_NAME}'")
        except Exception as e:
            logger.error(f"FATAL: Error reading '{INSTRUCTIONS_FILE_NAME}': {str(e)}")
            raise
        
        logger.info("=== Bot is ready to receive messages ===")
        print(f"Logged in as {bot.user}. Brian is operational.")
    except Exception as e:
        logger.error(f"FATAL ERROR in on_ready: {str(e)}", exc_info=True)
        raise

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # First, process commands that start with the prefix
    await bot.process_commands(message)

    # If a command was already processed, don't do anything else
    if message.content.startswith(bot.command_prefix):
        return

    # --- FIX 1: Allow users to use !roll mid-sentence ---
    # We check for the command manually if it's not at the start
    roll_in_message = re.search(r'!roll\s+((?:\d+d\d+|\d+)(?:[+\-]\d+)?)', message.content, re.IGNORECASE)
    if roll_in_message:
        dice_string = roll_in_message.group(1)
        roll_command = bot.get_command('roll')
        if roll_command:
            logger.info(f"Found mid-message roll from {message.author.name}: {dice_string}")
            # Manually invoke the command from the cog
            ctx = await bot.get_context(message)
            gameplay_cog = bot.get_cog('Gameplay')
            if gameplay_cog:
                await roll_command.callback(gameplay_cog, ctx, dice_string=dice_string)
        return # Stop processing to avoid treating it as a mention

    # --- FIX 2: Handle AI conversations and the @ROLL_DICE action ---
    if bot.user.mentioned_in(message):
        if mention_limiter.is_rate_limited(message.author.id):
            await message.reply("I'm getting too many requests right now. Please wait a moment.")
            return

        async with message.channel.typing():
            # (The logic for adding character sheet context stays the same here)
            system_prompt_content = BRIAN_SYSTEM_PROMPT
            char_file_path = f"characters/{message.author.id}.json"
            if os.path.exists(char_file_path):
                # ... (the character sheet loading logic you already have)
                with open(char_file_path, 'r', encoding='utf-8') as f:
                    character_data = json.load(f)
                character_json_string = json.dumps(character_data, indent=2)
                system_prompt_content += f"\n# YOUR FRIEND'S DATA\nYou are talking to {message.author.display_name}. This is their character sheet. Use it to answer any questions they have about their stats, items, or abilities.\n\n```json\n{character_json_string}\n```"

            history_messages = []
            async for hist_msg in message.channel.history(limit=10):
                role = "user"
                if hist_msg.author.bot:
                    role = "assistant" if hist_msg.author.id == bot.user.id else "user"
                history_messages.append({"role": role, "content": f"{hist_msg.author.display_name}: {sanitize_input(hist_msg.content)}"})
            history_messages.reverse()

            payload = [{"role": "system", "content": system_prompt_content}, *history_messages]
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME, messages=payload, max_tokens=MAX_TOKENS_FOR_RESPONSE, temperature=0.7
                )
                final_reply_to_send = response.choices[0].message.content
                
                # --- Handle Secret Actions ---
                roll_result_str = None
                
                # Check for @ROLL_DICE
                roll_match = re.search(r"@ROLL_DICE='(.*?)'", final_reply_to_send)
                if roll_match:
                    final_reply_to_send = final_reply_to_send.replace(roll_match.group(0), "").strip()
                    dice_to_roll = roll_match.group(1).strip()
                    logger.info(f"AI wants to roll dice: {dice_to_roll}")
                    roll_result_str = perform_roll(dice_to_roll)

                # Check for @REACT_EMOJI (existing logic)
                react_match = re.search(r"@REACT_EMOJI='(.*?)'", final_reply_to_send)
                if react_match:
                    final_reply_to_send = final_reply_to_send.replace(react_match.group(0), "").strip()
                    emoji_to_react_with = react_match.group(1).strip()
                    if emoji_to_react_with:
                        await message.add_reaction(emoji_to_react_with)

                # --- Send the final message ---
                if final_reply_to_send:
                    await message.reply(final_reply_to_send)

                # If there was a roll, send it as a follow-up message
                if roll_result_str:
                    await message.channel.send(roll_result_str)

            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}", exc_info=True)
                await message.reply("I am currently experiencing an issue with my neural interface. Please try again later.")


# --- Bot Commands ---
@bot.command(name='find')
async def find_message(ctx, *, query: str):
    """Searches across specified channels for a query."""
    if command_limiter.is_rate_limited(ctx.author.id):
        await ctx.send("You're using this command too frequently. Please wait a moment before trying again.")
        return

    query = sanitize_input(query)
    
    async with ctx.typing():
        if not SEARCHABLE_CHANNEL_IDS:
            await ctx.send(f"{ctx.author.mention}, the `SEARCHABLE_CHANNEL_IDS` list in the script is empty. The bot owner needs to configure this.")
            return

        async def search_channel(channel, query_str):
            found_in_channel = []
            if not channel or not channel.permissions_for(ctx.guild.me).read_message_history:
                return []
            try:
                async for msg in channel.history(limit=200):
                    if not msg.author.bot and query_str.lower() in msg.content.lower():
                        found_in_channel.append((channel.name, msg.author.display_name, sanitize_input(msg.content), msg.jump_url))
                return found_in_channel
            except discord.Forbidden:
                return []

        channels_to_search = [ctx.guild.get_channel(ch_id) for ch_id in SEARCHABLE_CHANNEL_IDS]
        tasks = [search_channel(ch, query) for ch in channels_to_search if ch]
        
        list_of_results = await asyncio.gather(*tasks)
        all_found_messages = [msg for sublist in list_of_results for msg in sublist]

        if not all_found_messages:
            await ctx.send(f"I found no results for **'{query}'** in the archives.")
            return

        response = f"{ctx.author.mention}, I found these results for **'{query}'**:\n\n"
        for i, (ch_name, author, content, url) in enumerate(all_found_messages[:5]):
            trimmed_content = content[:150] + "..." if len(content) > 150 else content
            response += f"**#{ch_name}** by **{author}**: \"*{trimmed_content}*\" [Jump to Message]({url})\n"
        
        await ctx.send(response)


async def summarize_logic(ctx, channel_name: str):
    """Shared logic for summarizing any channel."""
    if command_limiter.is_rate_limited(ctx.author.id):
        await ctx.send("You're using this command too frequently. Please wait a moment before trying again.")
        return

    if not validate_channel_name(channel_name):
        await ctx.send("Invalid channel name format. Channel names can only contain lowercase letters, numbers, and hyphens.")
        return

    target_channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if not target_channel:
        await ctx.send(f"I could not find the channel `#{channel_name}`.")
        return
    
    if not target_channel.permissions_for(ctx.guild.me).read_message_history:
        await ctx.send(f"I do not have permission to view the history of `#{channel_name}`.")
        return

    try:
        logger.info(f"Fetching messages from channel {channel_name}")
        messages = [msg async for msg in target_channel.history(limit=100)]
        content = "\n".join(f"{msg.author.display_name}: {sanitize_input(msg.content)}" for msg in messages if msg.content and not msg.author.bot)
        
        if not content:
            await ctx.send(f"`#{channel_name}` has no recent text to summarize.")
            return

        prompt = f"Summarize the key points and decisions from the following Discord conversation from the '{channel_name}' channel. Be concise and clear:\n\n{content}"
        
        try:
            # --- REQUIRED FIX: Using the correct new client for the API call ---
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": "You are a summarization expert."}, {"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4
            )
            
            summary = response.choices[0].message.content
            embed = discord.Embed(title=f"Summary of #{target_channel.name}", description=summary, color=discord.Color.blue())
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"OpenAI API error during summarization: {str(e)}", exc_info=True)
            await ctx.send("I had trouble summarizing the channel. Please try again later.")

    except Exception as e:
        logger.error(f"Summarize command failed for channel '{channel_name}': {str(e)}", exc_info=True)
        await ctx.send("An error occurred while trying to summarize. Please try again later.")


@bot.command(name='summarize')
async def summarize_command(ctx, channel: discord.TextChannel):
    """Summarizes the last 100 messages of a given channel."""
    async with ctx.typing():
        await summarize_logic(ctx, channel.name)


@bot.command(name='recap')
async def recap_command(ctx):
    """Provides a summary of the 'session-notes' channel."""
    async with ctx.typing():
        await summarize_logic(ctx, "session-notes")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required argument. Please check the command usage.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("Channel not found. Please check the channel name and try again.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("I don't have the necessary permissions to perform this action.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
    else:
        logger.error(f"An unexpected command error occurred: {error}", exc_info=True)
        await ctx.send("An unexpected error occurred. Please try again later.")

async def main():
    # Load Cogs
    if not os.path.exists('cogs'):
        os.makedirs('cogs')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f"Successfully loaded cog: {filename}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename}: {e}")

    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        # --- REQUIRED FIX: Removed old, redundant startup code that would cause errors ---
        if not os.path.exists('characters'):
            os.makedirs('characters')
        
        logger.info("Starting bot...")
        asyncio.run(main())

    except Exception as e:
        logger.critical(f"FATAL ERROR during bot startup: {str(e)}", exc_info=True)
        exit(1)
