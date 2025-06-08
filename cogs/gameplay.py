# cogs/gameplay.py
import discord
from discord.ext import commands
import random
import json
import os
import logging
import io

logger = logging.getLogger(__name__)

# --- Helper function to get a user's character file path ---
def get_character_path(user_id):
    # Use DATA_DIR environment variable if set, otherwise use 'characters'
    data_dir = os.getenv('DATA_DIR', 'characters')
    logger.info(f"Using data directory: {data_dir}")
    # Ensure the directory exists
    if not os.path.exists(data_dir):
        logger.info(f"Creating data directory: {data_dir}")
        os.makedirs(data_dir)
    file_path = os.path.join(data_dir, f"{user_id}.json")
    logger.info(f"Character file path: {file_path}")
    return file_path

def roll_dice(dice_string):
    """Rolls dice and returns the results.
    Format: "2d6+3" or "1d20"
    Returns: (rolls, modifier, total)
    """
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
        return rolls, modifier, total
    except Exception as e:
        logger.error(f"Error rolling dice '{dice_string}': {str(e)}")
        raise ValueError("Brain doesn't speak wingdings. Try '2d6+3' or '1d20'")

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
        # Ensure characters directory exists
        if not os.path.exists('characters'):
            os.makedirs('characters')

    async def _apply_hp_change(self, user_id: int, hp_change: int) -> str:
        """Internal helper to apply healing or damage, accounting for temporary HP."""
        char_file = get_character_path(user_id)
        if not os.path.exists(char_file):
            raise Exception("Can't find your character sheet, friend.")

        with open(char_file, 'r+') as f:
            data = json.load(f)
            hp = data.setdefault('hit_points', {})
            hp.setdefault('current', 0)
            hp.setdefault('max', 0)
            hp.setdefault('temporary', 0)

            if hp_change > 0: # Healing
                hp['current'] = min(hp['max'], hp['current'] + hp_change)
                action_str = f"Healed for {hp_change} HP."
            else: # Damage
                damage = abs(hp_change)
                action_str = f"Took {damage} damage."
                
                # Damage comes from temporary HP first
                if hp['temporary'] > 0:
                    temp_damage = min(damage, hp['temporary'])
                    hp['temporary'] -= temp_damage
                    damage -= temp_damage # Remaining damage
                    action_str += f" ({temp_damage} from Temp HP)"

                if damage > 0:
                    hp['current'] -= damage

            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        
        return f"{action_str} You are now at **{hp['current']}/{hp['max']} HP** (with {hp['temporary']} Temp HP)."

    async def _update_coin(self, user_id: int, amount: int, coin_type: str) -> str:
        """Internal helper to modify a user's coin balance with currency conversion."""
        char_file = get_character_path(user_id)
        try:
            if not os.path.exists(char_file):
                # Create a new character file if it doesn't exist
                initial_data = {
                    "currency": {
                        "gp": 0,
                        "sp": 0,
                        "cp": 0
                    }
                }
                with open(char_file, 'w') as f:
                    json.dump(initial_data, f, indent=4)

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
                    raise ValueError(f"You don't have enough coin for that, friend! Your total worth is only {gp}gp, {sp}sp, {cp}cp.")

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
        except Exception as e:
            logger.error(f"Error updating coins for user {user_id}: {str(e)}")
            raise Exception("Oops! Brain dropped your coin purse. Sorry, friend")

    @commands.command(name='coin', case_insensitive=True)
    async def coin(self, ctx, *, args: str = None):
        """Manages your coin purse.
        Usage:
        !coin -> Shows your balance.
        !coin 10gp -> Adds 10 gold.
        !coin -5sp -> Removes 5 silver.
        """
        try:
            if args is None:
                # Show status if no arguments are given
                char_file = get_character_path(ctx.author.id)
                logger.info(f"Checking character file: {char_file}")
                if not os.path.exists(char_file):
                    # Create new character file with zero balance
                    logger.info(f"Creating new character file for {ctx.author.name}")
                    initial_data = {
                        "currency": {
                            "gp": 0,
                            "sp": 0,
                            "cp": 0
                        }
                    }
                    with open(char_file, 'w') as f:
                        json.dump(initial_data, f, indent=4)
                    logger.info(f"Created new character file with initial data")

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
                embed.add_field(name="Copper (CP)", value=f"{cp}", inline=True)
                await ctx.send(embed=embed)
                return

            # --- Argument Parsing Logic ---
            amount, coin_type = polish_coins(args)
            
            if coin_type is None:
                await ctx.send("That not a real coin, friend. Try `gp`, `sp`, or `cp`.")
                return
            
            if amount is None:
                await ctx.send("That not a valid amount, friend. Try `10gp` or `-2sp`.")
                return
            
            # Call the internal helper to do the work
            response_message = await self._update_coin(ctx.author.id, amount, coin_type)
            await ctx.send(response_message)

        except Exception as e:
            logger.error(f"Error in coin command: {str(e)}")
            await ctx.send(f"Oops! Something went wrong: {str(e)}")

    @commands.command(name='roll')
    async def roll(self, ctx, *, dice_string: str):
        """Rolls dice. Format: !roll 1d20+3"""
        try:
            rolls, modifier, total = roll_dice(dice_string)
            
            roll_details = f"Rolling: {dice_string}\nResult: `{rolls}` + ({modifier}) = **{total}**"
            await ctx.send(f"{ctx.author.mention}, {roll_details}")

        except Exception as e:
            logger.error(f"Error in roll command: {str(e)}")
            await ctx.send("Gah! Wrong format. Try `!roll 1d20` or `!roll 2d6+3`.")

    @commands.command(name='hp', case_insensitive=True)
    async def hp(self, ctx, *, args: str = None):
        """Shows HP status or applies healing/damage.
        Usage: !hp, !hp 10 (heal), !hp -5 (damage)
        """
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        if args is None:
            # Show HP status
            with open(char_file, 'r') as f:
                hp = json.load(f).get('hit_points', {})
            current = hp.get('current', 0)
            max_hp = hp.get('max', 0)
            temp = hp.get('temporary', 0)
            await ctx.send(f"You are at **{current}/{max_hp} HP** with **{temp}** Temporary HP.")
            return
        
        try:
            amount = int(args)
            response = await self._apply_hp_change(ctx.author.id, amount)
            await ctx.send(response)
        except ValueError:
            await ctx.send("That not a number, friend. Use `!hp 10` or `!hp -5`.")
        except Exception as e:
            await ctx.send(str(e))

    @commands.command(name='temphp', case_insensitive=True)
    async def temp_hp(self, ctx, amount: int):
        """Adds temporary HP to your character."""
        if amount < 0:
            await ctx.send("Cannot add negative temporary HP, friend.")
            return

        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        with open(char_file, 'r+') as f:
            data = json.load(f)
            hp = data.setdefault('hit_points', {})
            # Per D&D rules, new temp HP replaces old if it's higher
            if amount > hp.get('temporary', 0):
                hp['temporary'] = amount
                action_str = f"You gain **{amount}** Temporary HP."
            else:
                action_str = f"Your new temporary HP ({amount}) is not higher than your current ({hp.get('temporary', 0)}). No change."

            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        
        await ctx.send(action_str)

    @commands.command(name='sr', aliases=['shortrest'])
    async def short_rest(self, ctx):
        """Tells you your available hit dice for a short rest."""
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        with open(char_file, 'r') as f:
            hd = json.load(f).get('hit_dice', {})
        total = hd.get('total', 0)
        spent = hd.get('spent', 0)
        available = total - spent
        die_type = hd.get('die_type', 'd?')

        await ctx.send(f"You can spend up to **{available}** of your **{total} {die_type}** hit dice. Use `!spendhd <number>` to heal.")

    @commands.command(name='spendhd')
    async def spend_hit_dice(self, ctx, num_to_spend: int = 1):
        """Spends hit dice to heal during a short rest."""
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            raise Exception("Can't find your character sheet.")

        with open(char_file, 'r+') as f:
            data = json.load(f)
            hd = data.setdefault('hit_dice', {})
            total_hd = hd.setdefault('total', 0)
            spent_hd = hd.setdefault('spent', 0)
            available_hd = total_hd - spent_hd
            
            if num_to_spend > available_hd:
                raise Exception(f"You only have {available_hd} hit dice to spend, friend.")

            # Get Constitution modifier for healing
            con_mod = data.get('ability_modifiers', {}).get('constitution_mod', 0)
            die_type_str = hd.get('die_type', 'd6')
            die_size = int(die_type_str.replace('d', ''))

            total_healed = 0
            rolls = []
            for _ in range(num_to_spend):
                roll = random.randint(1, die_size)
                rolls.append(roll)
                total_healed += (roll + con_mod)

            # Apply the healing
            hp = data.setdefault('hit_points', {})
            hp['current'] = min(hp.get('max', 0), hp.get('current', 0) + total_healed)

            # Update spent hit dice
            hd['spent'] += num_to_spend

            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        
        await ctx.send(f"You spend {num_to_spend} hit dice.\nRolls: `{rolls}` + {num_to_spend * con_mod} (CON) = **{total_healed}** HP recovered.\nYou are now at **{hp['current']}/{hp['max']}** HP.")


    @commands.command(name='lr', aliases=['longrest'])
    async def long_rest(self, ctx):
        """Performs a long rest, restoring HP and half hit dice."""
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            raise Exception("Can't find your character sheet. Snacks instead?")

        with open(char_file, 'r+') as f:
            data = json.load(f)
            
            # Restore HP and reset temp HP
            hp = data.setdefault('hit_points', {})
            hp['current'] = hp.get('max', 0)
            hp['temporary'] = 0

            # Restore half of the total hit dice (minimum of 1)
            hd = data.setdefault('hit_dice', {})
            total_hd = hd.get('total', 0)
            dice_to_recover = max(1, total_hd // 2)
            hd['spent'] = max(0, hd.get('spent', 0) - dice_to_recover)
            
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        
        await ctx.send(f"Wakey wakey! All {hp['max']}HP restored. You recover {dice_to_recover} hit dice. You have **{hd['spent']}** hit dice spent.")

    @commands.command(name='attr', aliases=['attribute', 'stat'])
    async def show_attribute(self, ctx, *, attribute_path: str = None):
        """Shows the value of a character attribute.
        Usage: !attr, !attr strength, !attr skills.athletics
        """
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        try:
            with open(char_file, 'r') as f:
                data = json.load(f)

            if attribute_path is None:
                # Show all top-level attributes
                embed = discord.Embed(
                    title=f"{ctx.author.display_name}'s Attributes",
                    color=discord.Color.blue()
                )
                for key, value in data.items():
                    if isinstance(value, dict):
                        # For nested objects, show a summary
                        embed.add_field(
                            name=key.title(),
                            value=f"{len(value)} properties",
                            inline=True
                        )
                    else:
                        # For simple values, show the value
                        embed.add_field(
                            name=key.title(),
                            value=str(value),
                            inline=True
                        )
                await ctx.send(embed=embed)
                return

            # Handle nested attributes using dot notation
            current = data
            path_parts = attribute_path.lower().split('.')
            
            for part in path_parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    await ctx.send(f"Can't find '{attribute_path}'. Try a different path.")
                    return

            if current is None:
                await ctx.send(f"Can't find '{attribute_path}'. Try a different path.")
                return

            # Format the response based on the type of value
            if isinstance(current, dict):
                embed = discord.Embed(
                    title=f"{attribute_path.title()}",
                    color=discord.Color.blue()
                )
                for key, value in current.items():
                    embed.add_field(
                        name=key.title(),
                        value=str(value),
                        inline=True
                    )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"**{attribute_path.title()}**: {current}")

        except Exception as e:
            logger.error(f"Error showing attribute: {str(e)}")
            await ctx.send("Oops! Brain got lost while looking up that attribute.")

    @commands.command(name='setattr', aliases=['setattribute', 'setstat'])
    async def set_attribute(self, ctx, attribute_path: str, *, value: str):
        """Sets the value of a character attribute.
        Usage: !setattr strength 16, !setattr skills.athletics 5
        """
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        try:
            # Try to convert value to number if possible
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                # If it's not a number, keep it as a string
                pass

            with open(char_file, 'r+') as f:
                data = json.load(f)
                
                # Handle nested attributes using dot notation
                current = data
                path_parts = attribute_path.lower().split('.')
                
                # Navigate to the parent object
                for part in path_parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Set the value
                current[path_parts[-1]] = value
                
                # Save the changes
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

            await ctx.send(f"Set **{attribute_path}** to **{value}**.")

        except Exception as e:
            logger.error(f"Error setting attribute: {str(e)}")
            await ctx.send("Oops! Brain got distracted while setting that attribute.")

    @commands.command(name='delattr', aliases=['delattribute', 'delstat'])
    async def delete_attribute(self, ctx, *, attribute_path: str):
        """Deletes a character attribute.
        Usage: !delattr strength, !delattr skills.athletics
        """
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet. How about we make a mess?")
            return

        try:
            with open(char_file, 'r+') as f:
                data = json.load(f)
                
                # Handle nested attributes using dot notation
                current = data
                path_parts = attribute_path.lower().split('.')
                
                # Navigate to the parent object
                for part in path_parts[:-1]:
                    if part not in current:
                        await ctx.send(f"Can't find '{attribute_path}'. Try a different path.")
                        return
                    current = current[part]

                # Delete the attribute
                if path_parts[-1] in current:
                    del current[path_parts[-1]]
                else:
                    await ctx.send(f"Can't find '{attribute_path}'. Try a different path.")
                    return
                
                # Save the changes
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

            await ctx.send(f"Deleted **{attribute_path}**.")

        except Exception as e:
            logger.error(f"Error deleting attribute: {str(e)}")
            await ctx.send("Oops! Brain got distracted while deleting that attribute.")

    @commands.command(name='sheet')
    async def show_sheet(self, ctx, as_file: str = None):
        """Shows your character sheet.
        Usage: !sheet - Shows the sheet in chat
        Usage: !sheet file - Sends the sheet as a JSON file
        """
        char_file = get_character_path(ctx.author.id)
        if not os.path.exists(char_file):
            await ctx.send("Can't find your character sheet, friend.")
            return

        try:
            with open(char_file, 'r') as f:
                data = json.load(f)

            if as_file and as_file.lower() == 'file':
                # Create a temporary file with the JSON data
                temp_file = discord.File(
                    fp=io.StringIO(json.dumps(data, indent=4)),
                    filename=f"{ctx.author.name}_character_sheet.json"
                )
                await ctx.send("Here's your character sheet:", file=temp_file)
            else:
                # Format the JSON for display in chat
                formatted_json = json.dumps(data, indent=2)
                
                # Split into chunks if too long
                if len(formatted_json) > 1900:  # Discord message limit is 2000
                    chunks = [formatted_json[i:i+1900] for i in range(0, len(formatted_json), 1900)]
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await ctx.send(f"```json\n{chunk}\n```")
                        else:
                            await ctx.send(f"```json\n{chunk}\n```")
                else:
                    await ctx.send(f"```json\n{formatted_json}\n```")

        except Exception as e:
            logger.error(f"Error showing character sheet: {str(e)}")
            await ctx.send("Oops! Brain ate your character sheet.")

    @commands.command(name='importsheet')
    async def import_sheet(self, ctx, *, json_data: str):
        """Imports a character sheet from JSON data.
        Usage: !importsheet {"your": "json data"}
        """
        char_file = get_character_path(ctx.author.id)
        try:
            # Parse the JSON data
            data = json.loads(json_data)
            
            # Save it to the character file
            with open(char_file, 'w') as f:
                json.dump(data, f, indent=4)
            
            await ctx.send("Character sheet imported successfully! Use `!sheet` to verify.")
            
        except json.JSONDecodeError:
            await ctx.send("That's not valid JSON data, friend. Make sure to format it correctly.")
        except Exception as e:
            logger.error(f"Error importing character sheet: {str(e)}")
            await ctx.send("Something went wrong while importing your character sheet.")

# This setup function is required for the cog to be loaded
async def setup(bot):
    await bot.add_cog(Gameplay(bot))