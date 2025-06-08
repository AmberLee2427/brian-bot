# cogs/gameplay.py
import discord
from discord.ext import commands
import random
import json
import os

# --- Helper function to get a user's character file path ---
def get_character_path(user_id):
    return f"characters/{user_id}.json"

def roll_dice(dice_string):
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
    return rolls, modifier, total

async def _update_coin(self, user_id: int, amount: int, coin_type: str) -> str:
    """Internal helper to modify a user's coin balance with currency conversion."""
    char_file = get_character_path(user_id)
    if not os.path.exists(char_file):
        raise Exception("Can't find your character sheet, friend.")

    # --- New Conversion Logic ---
    conversion_rates = {'gp': 100, 'sp': 10, 'cp': 1}
    transaction_in_cp = amount * conversion_rates[coin_type]

    with open(char_file, 'r+') as f:
        data = json.load(f)
        currency = data.setdefault('currency', {})
        gp = currency.setdefault('gp', 0)
        sp = currency.setdefault('sp', 0)
        cp = currency.setdefault('cp', 0)

        # Calculate the total balance in the smallest unit (copper)
        total_balance_in_cp = (gp * 100) + (sp * 10) + cp

        # Check if there are enough funds for a withdrawal
        if transaction_in_cp < 0 and abs(transaction_in_cp) > total_balance_in_cp:
            raise Exception(f"You don't have enough coin for that, friend! Your total worth is only {gp}gp, {sp}sp, {cp}cp.")

        # Apply the transaction
        new_total_balance_in_cp = total_balance_in_cp + transaction_in_cp
        
        # Convert the new total back into gp, sp, and cp for storage
        new_gp = new_total_balance_in_cp // 100
        remainder = new_total_balance_in_cp % 100
        new_sp = remainder // 10
        new_cp = remainder % 10

        # Update the data dictionary with the new normalized values
        currency['gp'] = new_gp
        currency['sp'] = new_sp
        currency['cp'] = new_cp
        
        # Save the updated data back to the file
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()
    
    action = "Added" if amount > 0 else "Removed"
    transaction_str = f"{abs(amount)} {coin_type.upper()}"
    new_balance_str = f"You now have **{new_gp} GP, {new_sp} SP, and {new_cp} CP**."
    
    return f"Okay, friend! {action} {transaction_str}. {new_balance_str}"

def polish_coins(string):
    """Polish the coin string to make it easier to parse."""

    # Remove and white space
    string = string.lower().replace(' ', '')

    coin_types = ['gp', 'sp', 'cp']
    coin_type = string[-2:]
    coin_type = coin_type.lower()

    if coin_type not in coin_types:
        return 0, None
    
    # Remove and white space from the amount
    amount = string[:-2]

    # Try to convert the amount to an integer
    try:
        amount = int(amount)
    except ValueError:
        return None, 'gp'
    
    return amount, coin_type

class Gameplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='coin', case_insensitive=True)
    async def coin(self, ctx, *, args: str = None):
        """Manages your coin purse.
        Usage:
        !coin -> Shows your balance.
        !coin 10gp -> Adds 10 gold.
        !coin -5sp -> Removes 5 silver.
        """
        if args is None:
            # Show status if no arguments are given
            char_file = get_character_path(ctx.author.id)
            if not os.path.exists(char_file):
                await ctx.send("Can't find your character sheet, friend.")
                return

            with open(char_file, 'r') as f:
                data = json.load(f)
                currency = data.get('currency', {})
                gp = currency.get('gp', 0)
                sp = currency.get('sp', 0)
                cp = currency.get('cp', 0)

            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Coin Purse",
                color=discord.Color.gold()
            )
            embed.add_field(name="Gold (GP)", value=f"{gp} 💰", inline=True)
            embed.add_field(name="Silver (SP)", value=f"{sp} 🪙", inline=True)
            embed.add_field(name="Copper (CP)", value=f"{cp}", inline=True) # Assuming no emoji for copper
            await ctx.send(embed=embed)
            return

        # --- Argument Parsing Logic ---
        try:
            # Clean up the argument string
            amount, coin_type = polish_coins(args)
            
            if coin_type is None:
                await ctx.send("That not a real coin, friend. Try `gp`, `sp`, or `cp`.")
                return
            
            if amount is None:
                await ctx.send("That not a valid amount, friend. Try `10gp` or `-2sp`.")
                return
            
            # Call the internal helper to do the work
            try:
                response_message = await self._update_coin(ctx.author.id, amount, coin_type)
                await ctx.send(response_message)
            except Exception as e:
                await ctx.send(f"Error: {e}")

        except (ValueError, IndexError):
            await ctx.send("Gah! Wrong format. Try `!coin 10gp` or `!coin -2sp`.")


    @commands.command(name='roll')
    async def roll(self, ctx, *, dice_string: str):
        """Rolls dice. Format: !roll 1d20+3"""
        try:
            rolls, modifier, total = roll_dice(dice_string)
            
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