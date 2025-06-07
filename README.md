# Brian Bot

A helpful Discord assistant built with Python and OpenAI. Brian is designed to be a secure, efficient, and friendly bot that can help manage and interact with your Discord server.

## Features

- **Natural Conversations**: Chat with Brian using natural language
- **Channel Summarization**: Get quick summaries of channel discussions
- **Message Search**: Find specific messages across configured channels
- **Security First**: Built with security best practices including rate limiting and input sanitization
- **Multi-bot Friendly**: Properly handles conversations with other bots

## Setup

### Local Development

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/brian-bot.git
   cd brian-bot
   ```

2. **Create a `.env` file:**
   In the same directory, create a file named `.env` and add your secret keys:
   ```
   DISCORD_TOKEN=your_discord_bot_token_goes_here
   OPENAI_API_KEY=your_openai_api_key_goes_here
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the Bot:**
   - Open `main.py`
   - Add channel IDs to `SEARCHABLE_CHANNEL_IDS` for the `!find` command
   - Configure `ALLOWED_ROLES` and `ADMIN_ROLES` for permission control
   - Adjust rate limits if needed (default: 5 mentions/minute, 10 commands/minute)

5. **Run the Bot:**
   ```bash
   python main.py
   ```

### Railway Deployment

1. **Create a Railway Account:**
   - Sign up at [Railway.app](https://railway.app)
   - Install the Railway CLI (optional)

2. **Deploy to Railway:**
   - Fork this repository
   - Create a new project in Railway
   - Connect your GitHub repository
   - Add the following environment variables in Railway:
     - `DISCORD_TOKEN`
     - `OPENAI_API_KEY`

3. **Configure the Bot:**
   - The bot will automatically deploy when you push to the main branch
   - Monitor the deployment in the Railway dashboard
   - Check the logs for any issues

4. **Updating the Bot:**
   - Push changes to your repository
   - Railway will automatically redeploy
   - Monitor the deployment status in the dashboard

## Usage

* **Chat:** Mention `@Brian` in a message to start a conversation
* **Summarize:** Use `!summarize #channel-name` to get a summary of that channel
* **Recap:** Use `!recap` for a quick summary of the `#session-notes` channel
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