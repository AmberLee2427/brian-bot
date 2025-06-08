import discord
from discord.ext import commands
import openai
import os
import json # You need this for the character sheets
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
from openai import OpenAI


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
MAX_MESSAGE_LENGTH = 2000  # Discord's message length limit

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
        
        user_requests = [req_time for req_time in user_requests if now - req_time < timedelta(seconds=self.time_window)]
        self.requests[user_id] = user_requests
        
        if len(user_requests) >= self.max_requests:
            return True
        
        user_requests.append(now)
        return False

mention_limiter = RateLimiter(max_requests=5, time_window=60)
command_limiter = RateLimiter(max_requests=10, time_window=60)

# --- Input Validation ---
def sanitize_input(text: str) -> str:
    if not text:
        return ""
    text = ''.join(char for char in text if char in string.printable or char in '\n\r\t')
    return text[:1000]

def validate_channel_name(name: str) -> bool:
    return bool(re.match(r'^[a-z0-9-]+$', name.lower()))

def has_permission(member: discord.Member, required_roles: list) -> bool:
    if not required_roles:
        return True
    return any(role.id in required_roles for role in member.roles)

# Channels for the !find command
SEARCHABLE_CHANNEL_IDS = []

# --- Bot Events ---
@bot.event
async def on_ready():
    try:
        logger.info("=== Bot Starting Up ===")
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
        logger.info(f"Connected to {len(bot.guilds)} guilds:")
        for guild in bot.guilds:
            logger.info(f"- {guild.name} (ID: {guild.id})")
        
        global BRIAN_SYSTEM_PROMPT
        try:
            with open(INSTRUCTIONS_FILE_NAME, 'r', encoding='utf-8') as f:
                BRIAN_SYSTEM_PROMPT = f.read()
            logger.info(f"Successfully loaded instructions from '{INSTRUCTIONS_FILE_NAME}'")
        except Exception as e:
            logger.error(f"FATAL: Could not read '{INSTRUCTIONS_FILE_NAME}': {e}")
            raise
        
        logger.info("=== Bot is ready to receive messages ===")
        print(f"Logged in as {bot.user}. Brian is operational.")
    except Exception as e:
        logger.error(f"FATAL ERROR in on_ready: {e}", exc_info=True)
        raise

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if bot.user.mentioned_in(message) and not message.content.startswith(bot.command_prefix):
        if mention_limiter.is_rate_limited(message.author.id):
            logger.warning(f"Rate limit hit for user {message.author.name} ({message.author.id})")
            await message.reply("I'm getting too many requests right now. Please wait a moment.")
            return

        async with message.channel.typing():
            logger.info(f"Preparing response for mention by {message.author.name}")

            # --- Start: Add Character Sheet Context ---
            system_prompt_content = BRIAN_SYSTEM_PROMPT
            char_file_path = f"characters/{message.author.id}.json"

            if os.path.exists(char_file_path):
                logger.info(f"Found character sheet for {message.author.name}")
                with open(char_file_path, 'r', encoding='utf-8') as f:
                    character_data = json.load(f)
                
                character_json_string = json.dumps(character_data, indent=2)
                contextual_prompt_addition = f"""
# YOUR FRIEND'S DATA
You are talking to {message.author.display_name}. This is their character sheet. Use it to answer any questions they have about their stats, items, or abilities. Be helpful.

```json
{character_json_string}
```
"""
                system_prompt_content += contextual_prompt_addition
            else:
                logger.info(f"No character sheet found for {message.author.name}")
            # --- End: Add Character Sheet Context ---

            history_messages = []
            try:
                async for hist_msg in message.channel.history(limit=10):
                    role = "user"
                    if hist_msg.author.bot:
                        role = "assistant" if hist_msg.author.id == bot.user.id else "user"
                    
                    history_messages.append({
                        "role": role,
                        "content": f"{hist_msg.author.display_name}: {sanitize_input(hist_msg.content)}"
                    })
                history_messages.reverse()
            except Exception as e:
                logger.error(f"Error fetching message history: {e}")

            payload = [
                {"role": "system", "content": system_prompt_content},
                *history_messages
            ]
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=payload,
                    max_tokens=MAX_TOKENS_FOR_RESPONSE,
                    temperature=0.7
                )
                final_reply_to_send = response.choices[0].message.content

                react_match = re.search(r"@REACT_EMOJI='(.*?)'", final_reply_to_send)
                if react_match:
                    final_reply_to_send = final_reply_to_send.replace(react_match.group(0), "").strip()
                    emoji_to_react_with = react_match.group(1).strip()
                    if emoji_to_react_with:
                        try:
                            await message.add_reaction(emoji_to_react_with)
                        except discord.HTTPException as e:
                            logger.warning(f"Failed to add reaction '{emoji_to_react_with}': {e}")

                if final_reply_to_send:
                    await message.reply(final_reply_to_send)

            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}", exc_info=True)
                await message.reply("I am currently experiencing an issue with my neural interface. Please try again later.")

# --- Bot Commands ---
@bot.command(name='find')
async def find_message(ctx, *, query: str):
    """Searches across specified channels for a query."""
    if command_limiter.is_rate_limited(ctx.author.id):
        await ctx.send("You're using this command too frequently. Please wait.")
        return

    query = sanitize_input(query)
    
    async with ctx.typing():
        if not SEARCHABLE_CHANNEL_IDS:
            await ctx.send(f"{ctx.author.mention}, the `SEARCHABLE_CHANNEL_IDS` list is empty.")
            return

        # Simplified search logic for brevity
        all_found_messages = []
        channels_to_search = [ctx.guild.get_channel(ch_id) for ch_id in SEARCHABLE_CHANNEL_IDS if ctx.guild.get_channel(ch_id)]
        
        for channel in channels_to_search:
            try:
                async for msg in channel.history(limit=200):
                    if not msg.author.bot and query.lower() in msg.content.lower():
                        all_found_messages.append((channel.name, msg.author.display_name, sanitize_input(msg.content), msg.jump_url))
            except discord.Forbidden:
                logger.warning(f"No permission to read history in {channel.name}")
                continue

        if not all_found_messages:
            await ctx.send(f"I found no results for **'{query}'** in the archives.")
            return

        response = f"{ctx.author.mention}, I found these results for **'{query}'**:\n\n"
        for ch_name, author, content, url in all_found_messages[:5]:
            trimmed_content = content[:150] + "..." if len(content) > 150 else content
            response += f"**#{ch_name}** by **{author}**: \"*{trimmed_content}*\" [Jump to Message]({url})\n"
        
        await ctx.send(response)

# --- Summarize Logic and Commands ---
async def summarize_logic(ctx, channel_name: str):
    # This function's implementation can stay as it was, but let's ensure it uses the new client
    target_channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if not target_channel or not target_channel.permissions_for(ctx.guild.me).read_message_history:
        await ctx.send(f"I can't see or find the `#{channel_name}` channel.")
        return

    content = ""
    messages = [msg async for msg in target_channel.history(limit=100)]
    content = "\n".join(f"{msg.author.display_name}: {sanitize_input(msg.content)}" for msg in messages if msg.content and not msg.author.bot)

    if not content:
        await ctx.send(f"`#{channel_name}` has no recent text to summarize.")
        return

    prompt = f"Summarize the key points and decisions from the following Discord conversation from the '{channel_name}' channel. Be concise and clear:\n\n{content}"
    
    try:
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
        logger.error(f"Summarize command failed for channel '{channel_name}': {e}")
        await ctx.send("I had trouble summarizing the channel. Please try again later.")

@bot.command(name='summarize')
async def summarize_command(ctx, channel: discord.TextChannel):
    """Summarizes the last 100 messages of a given channel."""
    await summarize_logic(ctx, channel.name)

@bot.command(name='recap')
async def recap_command(ctx):
    """Provides a summary of the 'session-notes' channel."""
    await summarize_logic(ctx, "session-notes")

# --- Error Handling ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You missed an argument for that command.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("I couldn't find that channel.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
    else:
        logger.error(f"An unexpected command error occurred: {error}", exc_info=True)
        await ctx.send("An unexpected error occurred.")

# --- Bot Startup ---
async def main():
    if not os.path.exists('cogs'):
        os.makedirs('cogs')
    if not os.path.exists('characters'):
        os.makedirs('characters')
        
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f"Successfully loaded cog: {filename}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)

    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"FATAL ERROR during bot startup: {e}", exc_info=True)
        exit(1)
