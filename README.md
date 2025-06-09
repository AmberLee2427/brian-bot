# Brian Bot

A helpful Discord assistant built with Python and OpenAI. Brian is designed to be a secure, efficient, and friendly bot that can help manage and interact with your Discord server.

![A cute imp wearing a nametag that says "Brian"](Brian1.png)

## Features

- **Natural Conversations**: Chat with Brian using natural language
- **Channel Summarization**: Get quick summaries of channel discussions
- **Message Search**: Find specific messages across configured channels
- **Security First**: Built with security best practices including rate limiting and input sanitization
- **Multi-bot Friendly**: Properly handles conversations with other bots

## Setup

### Prerequisites

1. **Create a Discord Bot:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name
   - Add the `Brain1.png` or `Brain2.png` image as Brian's profile pic
   - Go to the "Installation" tab and select `None` for the Install link
   - Go to the "Bot" tab and turn of the "PUBLIC BOT" toggle
   - Under "Privileged Gateway Intents", enable:
     - MESSAGE CONTENT INTENT
     - SERVER MEMBERS INTENT
   - Copy the bot token and save it somewhere secure (you'll need this for the `.env` file)
   - Go to OAuth2 > URL Generator
   - Select scopes: `bot` and `applications.commands`
   - Select bot permissions:
     - Read Messages/View Channels
     - Send Messages
     - Read Message History
     - Add Reactions
     - Use Slash Commands
   - Copy the generated URL and paste in into a new tab to invite the bot to your server

2. **Get an OpenAI API Key:**
   - Go to [OpenAI Platform](https://platform.openai.com)
   - Sign up or log in
   - Go to API Keys section
   - Click "Create new secret key"
   - Copy the API key (you'll need this for the `.env` file)
   - Note: The API key starts with "sk-" and is used for billing
   - Note: You will likely need to prepay for tokens. Add a small amount of credit e.g. $5. You may be able to sell you data to OpenAI for $120 of credits a month, but not until you are on the appropriate member tier. So pay for a few calls and then consider selling your D&D anticts for effectively unlimited API usage. 
   - Note: Monitor this account for unexpected activity and reset your tokens if you are suspicious.

### Local Development

1. **Fork and Clone the Repository:**
   Fork this repository to your GitHub account by clicking the "Fork" button at the top of the page.
   
   Clone the repo locally:
   ```bash
   git clone https://github.com/yourusername/brian-bot.git
   cd brian-bot
   ```
   We recommend you "Watch" the repo in order to be notified of updates
     - Click the "Watch" button at the top of the repository
     - Select "Custom" to configure notifications
     - Enable notifications for:
       - "Releases" (when new versions are published)
       - "Discussions" (for community support)
       - "Security alerts" (for important security updates)
     - Click "Apply" to save your preferences

3. **Create a `.env` file:**
   In the same directory, create a file named `.env` and add your secret keys:
   ```
   # Required
   DISCORD_TOKEN=your_discord_bot_token_goes_here
   OPENAI_API_KEY=your_openai_api_key_goes_here
   
   # Optional (with defaults)
   SESSION_NOTES_CHANNEL=your-session-notes-channel-name  # Default: session-notes
   DATA_DIR=characters  # Default: characters
   COMMAND_PREFIX=!  # Default: !
   MODEL_NAME=gpt-4  # Default: gpt-4
   MAX_TOKENS_FOR_RESPONSE=1500  # Default: 1500
   RATE_LIMIT_MENTIONS=5  # Default: 5 mentions per minute
   RATE_LIMIT_COMMANDS=10  # Default: 10 commands per minute
   RATE_LIMIT_WINDOW=60  # Default: 60 seconds
   
   # Channel and Role Configuration
   SEARCHABLE_CHANNEL_IDS=123456789012345678,876543210987654321  # Comma-separated list of channel IDs for !find command
   ALLOWED_ROLES=123456789012345678,876543210987654321  # Comma-separated list of role IDs that can use restricted commands
   ADMIN_ROLES=123456789012345678,876543210987654321  # Comma-separated list of role IDs with admin privileges
   ```

   After creating the `.env` file, secure it with:
   ```bash
   chmod 600 .env
   ```
   This ensures only your user can read and write to the file.

4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the Bot:**
   ```bash
   python main.py
   ```

### Railway Deployment

1. **Create Required Accounts:**
   - Sign up for a [GitHub account](https://github.com/signup) if you don't have one
   - Sign up at [Railway.app](https://railway.app)
   - Install the Railway CLI (optional)

2. **Fork and Clone:**
   - Fork this repository to your GitHub account by clicking the "Fork" button at the top of the page
   - We recommend you "Watch" the repo in order to be notified of updates
     - Click the "Watch" button at the top of the repository
     - Select "Custom" to configure notifications
     - Enable notifications for:
       - "Releases" (when new versions are published)
       - "Discussions" (for community support)
       - "Security alerts" (for important security updates)
     - Click "Apply" to save your preferences

3. **Deploy to Railway:**
   - Create a new project in Railway
   - Connect your GitHub account if not already connected
   - Select your forked repository
     - If the repo isn't showing up under the GitHub options: 
       - Scroll to the bottom of the page and select "Empty Project"
       - Select "Add a service" > "GitHub Repo" > "Configure GitHub App" > <your account>
       - You may need to Authenticate to continue
       - Under "Repository Access", select either:
         * "All repositiories" or 
         * "Only select repositories" and choose "brain-bot" from the dropdown list
      - "Save"
   - Add the following environment variables in Railway:
     - Where:
       - In "Architecture" view in your project space, click on the `brain-bot` box
       - Select the "Variables" tab
       - `New Variable`
       - Paste or type in the relevant content.
     - Required:
       - `DISCORD_TOKEN`: Your Discord bot token
       - `OPENAI_API_KEY`: Your OpenAI API key
     - Optional (with defaults):
       - `SESSION_NOTES_CHANNEL`: The name of your session notes channel (without the #)
       - `DATA_DIR`: (Optional, recommended) Custom directory for character sheets
       - `COMMAND_PREFIX`: Bot command prefix (default: !)
       - `MODEL_NAME`: OpenAI model to use (default: gpt-4)
       - `MAX_TOKENS_FOR_RESPONSE`: Maximum tokens for AI responses (default: 1500)
       - `RATE_LIMIT_MENTIONS`: Mentions allowed per minute (default: 5)
       - `RATE_LIMIT_COMMANDS`: Commands allowed per minute (default: 10)
       - `RATE_LIMIT_WINDOW`: Rate limit window in seconds (default: 60)
     - Channel and Role Configuration:
       - `SEARCHABLE_CHANNEL_IDS`: Comma-separated list of channel IDs for the !find command
       - `ALLOWED_ROLES`: Comma-separated list of role IDs that can use restricted commands
       - `ADMIN_ROLES`: Comma-separated list of role IDs with admin privileges
     - Secure the Token and API Key variables by selecting the triple dot and `Seal`, if the option is available.

4. **Configure the Bot:**
   - The bot will automatically deploy when you push to the main branch (this could take a few minutes)
   - Monitor the deployment in the Railway dashboard
   - Check the logs for any issues

5. **Updating the Bot:**
   - Push changes to your repository or "Sync Fork" with the main repo
   - Railway will automatically redeploy
   - Monitor the deployment status in the dashboard

### Setting Up Persistent Storage (Optional but Recommended)

To ensure your character sheets persist across deployments and restarts, you can set up a storage service on Railway:

1. **Add Storage Service:**
   - In your Railway project dashboard, click "New"
   - Select "Storage" from the service options
   - Choose a name for your storage service (e.g., "brian-storage")

2. **Configure Storage:**
   - Once created, Railway will provide a mount path
   - Add this environment variable to your bot service:
     ```
     DATA_DIR=/data/characters
     ```
   - This will store character sheets in the persistent storage volume

3. **Verify Setup:**
   - Deploy your bot
   - Create a character sheet using `!coin` or by mentioning Brian
   - Check the `/data/characters` directory in your storage service
   - Your character sheets should persist even if the bot restarts

Note: If you don't set up persistent storage, character sheets will be stored in the bot's ephemeral filesystem and will be lost when the bot restarts or redeploys.

## Usage

* **Chat:** Mention `@Brian` in a message to start a conversation
* **Summarize:** Use `!summarize #channel-name` to get a summary of that channel
* **Recap:** Use `!recap` for a quick summary of your session notes channel
* **Find:** Use `!find your search query` to look for messages in configured channels

## Security Features

- Rate limiting to prevent abuse
- Input sanitization for all user inputs
- Role-based access control
- API key validation
- Secure error handling
- Message length limits

## Troubleshooting

1. **Bot not responding:**
   - Check if the bot is online
   - Verify API keys in `.env` or Railway environment variables
   - Check bot permissions in Discord

2. **Commands not working:**
   - Ensure the bot has necessary permissions
   - Check if you have the required roles
   - Verify channel permissions

3. **Rate limiting:**
   - Wait 60 seconds before trying again
   - Contact server admin if persistent

4. **Railway Deployment Issues:**
   - Check Railway logs for errors
   - Verify environment variables are set correctly
   - Ensure the Procfile and runtime.txt are present
   - Check if the build process completed successfully

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Security

If you discover any security-related issues, please email [your-email] instead of using the issue tracker.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- OpenAI for the GPT API
- Discord.py for the Discord API wrapper
- All contributors who have helped improve Brian

## Release Notes

Initial release of Brian Bot, a Discord bot for D&D servers with the following features:

- Natural language conversations with OpenAI integration
- Character sheet management
- Dice rolling
- Channel summarization
- Message search
- Session notes tracking
- Rate limiting and security features

Key Features:
- Default character sheet template
- Persistent storage support
- Configurable through environment variables
- Railway deployment support
- Comprehensive documentation

This is the first stable release of Brian Bot. All features are fully functional and documented.
