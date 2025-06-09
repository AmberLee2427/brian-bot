# How to Use {BOT_NAME} Bot

{BOT_NAME} is your loyal, if chaotic, imp sidekick. They can help you manage your character sheet, roll dice, and recall information. Here's how to command them.

## Talking to {BOT_NAME}

To have a natural conversation, just mention them in a message.

* `@{BOT_NAME} how much gold do I have?`
* `@{BOT_NAME} what's my armor class?`
* `@{BOT_NAME} make a strength check for me`

They'll read your character sheet to answer questions and can even roll dice for you if you ask them to.

## Core Commands

These are direct commands that {BOT_NAME} will obey instantly.

### Character Sheet Management
* `!sheet`: Shows your full character sheet in a series of messages.
* `!sheet file`: Sends your character sheet as a downloadable `.json` file.
* `!importsheet`: Upload a new character sheet. You must attach a `.json` file to the message when you use this command.

### Health and HP
* `!hp`: Shows your current, max, and temporary HP.
* `!hp 10`: Heals you for 10 HP.
* `!hp -5`: Deals 5 damage to you. {BOT_NAME} will automatically subtract from temporary HP first.
* `!temphp 20`: Gives you 20 temporary HP. Note: New temp HP only applies if it's higher than your current temp HP.

### Resting and Recovery
* `!lr` or `!longrest`: Performs a long rest. This fully restores your HP and recovers half of your total hit dice.
* `!sr` or `!shortrest`: Performs a short rest. This will tell you how many hit dice you have available to spend.
* `!spendhd <number>`: Spends a number of hit dice to recover health. For example, `!spendhd 2` will spend two of your available hit dice.

### Currency Management
* `!coin`: Shows a summary of your coin purse (GP, SP, CP).
* `!coin 50gp`: Adds 50 gold.
* `!coin -10sp`: Subtracts 10 silver. {BOT_NAME} will automatically make change from higher-value coins if needed.

### Dice Rolling
* `!roll <dice>`: Rolls dice using standard notation (e.g., `!roll 2d6+3`).
* You can also put the roll command anywhere in your message, and {BOT_NAME} will find it: `I attack the goblin! !roll 1d20+5`

### Advanced Attribute Management
These commands use dot notation to access any value on your character sheet.

* `!attr skills.athletics`: Shows the value of your athletics skill.
* `!setattr name "Sir Reginald"`: Sets your character's name to "Sir Reginald".
* `!delattr flaws`: Deletes the "flaws" attribute from your sheet.

### Server Utilities
* `!find <query>`: Searches specified channels for a keyword or phrase.
* `!recap`: Gives a summary of your session notes channel. The channel name is configurable in the bot's environment variables.
* `!summarize #channel-name`: Gives a summary of any channel you specify.