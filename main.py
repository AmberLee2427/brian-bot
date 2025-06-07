import discord
from discord.ext import commands
import openai
import os
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
MAX_CONTEXT_TOKENS_INPUT = 8000
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
def count_tokens(text):
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except:
        return len(text.split())

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
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Directory contents: {os.listdir('.')}")
            
            if not os.path.exists(INSTRUCTIONS_FILE_NAME):
                logger.error(f"File does not exist: {INSTRUCTIONS_FILE_NAME}")
                logger.error(f"Current directory contents: {os.listdir('.')}")
                raise FileNotFoundError(f"File not found: {INSTRUCTIONS_FILE_NAME}")
            
            with open(INSTRUCTIONS_FILE_NAME, 'r', encoding='utf-8') as f:
                BRIAN_SYSTEM_PROMPT = f.read()
            logger.info(f"Successfully loaded instructions from '{INSTRUCTIONS_FILE_NAME}'")
            logger.info(f"Instructions length: {len(BRIAN_SYSTEM_PROMPT)} characters")
            logger.info(f"First 100 characters of instructions: {BRIAN_SYSTEM_PROMPT[:100]}")
        except FileNotFoundError as e:
            logger.error(f"FATAL: Instruction file '{INSTRUCTIONS_FILE_NAME}' not found!")
            logger.error(f"Current directory contents: {os.listdir('.')}")
            raise
        except Exception as e:
            logger.error(f"FATAL: Error reading '{INSTRUCTIONS_FILE_NAME}': {str(e)}")
            raise
        
        logger.info("=== Bot is ready to receive messages ===")
        print(f"Logged in as {bot.user}. Brian is operational.")
    except Exception as e:
        logger.error(f"FATAL ERROR in on_ready: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Process commands first
    await bot.process_commands(message)

    # Log all messages for debugging
    logger.info(f"Received message from {message.author.name}: {message.content}")

    # Respond to mentions if it's not a command
    if bot.user.mentioned_in(message) and not message.content.startswith(bot.command_prefix):
        logger.info(f"Bot was mentioned by {message.author.name}")
        
        # Check rate limit
        if mention_limiter.is_rate_limited(message.author.id):
            logger.info(f"Rate limit hit for user {message.author.name}")
            await message.reply("I'm getting too many requests right now. Please wait a moment before trying again.")
            return

        async with message.channel.typing():
            logger.info(f"Preparing response for {message.author.name}")
            
            # Sanitize the message content
            sanitized_content = sanitize_input(message.content)
            logger.info(f"Sanitized content: {sanitized_content}")
            
            history_messages = []
            try:
                async for hist_msg in message.channel.history(limit=10):
                    if hist_msg.author.bot:
                        # Only mark Brian's messages as assistant, other bots as user
                        role = "assistant" if hist_msg.author.id == bot.user.id else "user"
                        history_messages.append({
                            "role": role,
                            "content": f"{hist_msg.author.display_name}: {sanitize_input(hist_msg.content)}"
                        })
                    else:
                        history_messages.append({
                            "role": "user",
                            "content": f"{hist_msg.author.display_name}: {sanitize_input(hist_msg.content)}"
                        })
                logger.info(f"Collected {len(history_messages)} messages from history")
            except Exception as e:
                logger.error(f"Error fetching history: {str(e)}")

            history_messages.reverse() # Oldest first

            payload = [
                {"role": "system", "content": BRIAN_SYSTEM_PROMPT},
                *history_messages
            ]
            
            try:
                logger.info("Sending request to OpenAI")
                logger.info(f"Using model: {MODEL_NAME}")
                logger.info(f"Payload length: {len(str(payload))} characters")
                logger.info(f"System prompt length: {len(BRIAN_SYSTEM_PROMPT)} characters")
                
                response = openai.ChatCompletion.create(
                    model=MODEL_NAME,
                    messages=payload,
                    max_tokens=MAX_TOKENS_FOR_RESPONSE,
                    temperature=0.7
                )
                
                final_reply_to_send = response.choices[0].message.content
                logger.info(f"Received response from OpenAI: {final_reply_to_send[:100]}...")

                # Check for @REACT_EMOJI command from the persona file
                react_match = re.search(r"@REACT_EMOJI='(.*?)'", final_reply_to_send)
                if react_match:
                    # Remove the command from the public reply
                    final_reply_to_send = final_reply_to_send.replace(react_match.group(0), "").strip()
                    emoji_to_react_with = react_match.group(1).strip()
                    
                    if emoji_to_react_with:
                        logger.info(f"Brian wants to react to message {message.id} with: {emoji_to_react_with}")
                        try:
                            # Apply the reaction to the user's triggering message
                            await message.add_reaction(emoji_to_react_with)
                        except discord.HTTPException as e:
                            logger.warning(f"Failed to add reaction '{emoji_to_react_with}': {str(e)}")

                if final_reply_to_send: # Make sure there's something to say
                    logger.info("Sending reply to Discord")
                    await message.reply(final_reply_to_send)
                    logger.info("Reply sent successfully")

            except Exception as e:
                logger.error(f"OpenAI API call failed: {str(e)}")
                logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                await message.reply("I am currently experiencing an issue with my neural interface. Please try again later.")


# --- Bot Commands ---

@bot.command(name='find')
async def find_message(ctx, *, query: str):
    """Searches across specified channels for a query."""
    # Check rate limit
    if command_limiter.is_rate_limited(ctx.author.id):
        await ctx.send("You're using this command too frequently. Please wait a moment before trying again.")
        return

    # Sanitize query
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
        for i, (ch_name, author, content, url) in enumerate(all_found_messages[:5]): # Limit to top 5 results
            trimmed_content = content[:150] + "..." if len(content) > 150 else content
            response += f"**#{ch_name}** by **{author}**: \"*{trimmed_content}*\" [Jump to Message]({url})\n"
        
        await ctx.send(response)


async def summarize_logic(ctx, channel_name: str):
    """Shared logic for summarizing any channel."""
    # Check rate limit
    if command_limiter.is_rate_limited(ctx.author.id):
        await ctx.send("You're using this command too frequently. Please wait a moment before trying again.")
        return

    # Validate channel name
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
        logger.info(f"Found {len(messages)} messages in channel {channel_name}")
        
        content = "\n".join(f"{msg.author.display_name}: {sanitize_input(msg.content)}" 
                          for msg in messages if msg.content and not msg.author.bot)
        
        if not content:
            logger.info(f"No content found in channel {channel_name}")
            await ctx.send(f"`#{channel_name}` has no recent text to summarize.")
            return

        logger.info(f"Preparing summary for channel {channel_name}")
        prompt = f"Summarize the key points and decisions from the following Discord conversation from the '{channel_name}' channel. Be concise and clear:\n\n{content}"
        
        try:
            logger.info("Sending request to OpenAI for summarization")
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": "You are a summarization expert."}, {"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4
            )
            
            summary = response.choices[0].message.content
            logger.info(f"Received summary from OpenAI: {summary[:100]}...")
            
            embed = discord.Embed(
                title=f"Summary of #{target_channel.name}",
                description=summary,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            logger.info("Summary sent successfully")

        except Exception as e:
            logger.error(f"OpenAI API error during summarization: {str(e)}")
            await ctx.send("I had trouble summarizing the channel. Please try again later.")

    except Exception as e:
        logger.error(f"Summarize command failed for channel '{channel_name}': {str(e)}")
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
        logger.error(f"An unexpected command error occurred: {error}")
        await ctx.send("An unexpected error occurred. Please try again later.")

def check_message_length(content: str) -> bool:
    """Check if a message is within Discord's length limits."""
    return len(content) <= MAX_MESSAGE_LENGTH

if __name__ == "__main__":
    try:
        print("=== Starting Brian Bot ===")
        print("Checking environment variables...")
        if not OPENAI_API_KEY:
            print("ERROR: OPENAI_API_KEY not found!")
        else:
            print("OPENAI_API_KEY found")
        if not DISCORD_TOKEN:
            print("ERROR: DISCORD_TOKEN not found!")
        else:
            print("DISCORD_TOKEN found")
        
        print("Initializing OpenAI client...")
        try:
            openai.api_key = OPENAI_API_KEY
            print("OpenAI client initialized successfully")
        except Exception as e:
            print(f"ERROR: Failed to initialize OpenAI client: {str(e)}")
            raise
        
        print("Starting bot...")
        try:
            bot.run(DISCORD_TOKEN)
        except Exception as e:
            print(f"ERROR: Bot failed to start: {str(e)}")
            raise
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        exit(1)