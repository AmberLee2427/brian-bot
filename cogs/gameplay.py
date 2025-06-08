# cogs/gameplay.py
import discord
from discord.ext import commands
import random
import json
import os

# --- Helper function to get a user's character file path ---
def get_character_path(user_id):
    return f"characters/{user_id}.json"

class Gameplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='roll')
    async def roll(self, ctx, *, dice_string: str):
        """Rolls dice. Format: !roll 1d20+3"""
        try:
            parts = dice_string.replace(' ', '').split('d')
            num_dice = int(parts[0]) if parts[0] else 1
            
            modifier = 0
            if '+' in parts[1]:
                die_parts = parts[1].split('+')
                die_size = int(die_parts[0])
                modifier = int(die_parts[1])
            elif '-' in parts[1]:
                die_parts = parts[1].split('-')
                die_size = int(die_parts[0])
                modifier = -int(die_parts[1])
            else:
                die_size = int(parts[1])

            rolls = [random.randint(1, die_size) for _ in range(num_dice)]
            total = sum(rolls) + modifier
            
            roll_details = f"Rolling: {dice_string}\nResult: `{rolls}` + ({modifier}) = **{total}**"
            await ctx.send(f"{ctx.author.mention}, {roll_details}")

        except Exception as e:
            await ctx.send("Gah! Wrong format. Try `!roll 1d20` or `!roll 2d6+3`.")

    @commands.command(name='sr')
    async def short_rest(self, ctx):
        """Performs a short rest for your character."""
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        # Here you would add logic to modify the JSON file
        # e.g., restore specific abilities or let user spend hit dice
        
        await ctx.send(f"{ctx.author.mention} takes a short rest. Ah, refreshing!")

    @commands.command(name='lr')
    async def long_rest(self, ctx):
        """Performs a long rest, restoring HP and abilities."""
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        with open(char_file, 'r+') as f:
            data = json.load(f)
            # Restore HP to max
            data['hit_points']['current'] = data['hit_points']['max']
            # You can add logic here to restore hit dice, spell slots, etc.
            
            f.seek(0) # Rewind to the start of the file
            json.dump(data, f, indent=4)
            f.truncate() # Remove trailing data if the new data is shorter

        await ctx.send(f"{ctx.author.mention} feels fully rested. All HP restored! Ready for more... snacks?")


# This setup function is required for the cog to be loaded
async def setup(bot):
    await bot.add_cog(Gameplay(bot))