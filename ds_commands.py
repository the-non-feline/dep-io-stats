import typing
import discord
from discord import app_commands
from typing import Literal
import dep_io_stats
import ds_constants
import reports
import tools
import chars
import habitat
from logs import debug

def ds_slash(tree: app_commands.CommandTree, name: str, desc: str):
    return tree.command(name=name, description=desc)

async def gen_commands(client: dep_io_stats.DS):
    tree = client.tree

    @tree.error
    async def error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if type(error) is app_commands.MissingPermissions:
            missing = error.missing_permissions
            missing_str = tools.format_iterable(missing, formatter='`{}`')

            await interaction.response.send_message(content=f'To use this command, you need these permissions: {missing_str}.')
        elif type(error) is app_commands.CheckFailure:
            await interaction.response.send_message(content='I cringe at your lack of skill, peasant.')
        else:
            message = f'{interaction.user.mention} something went wrong; please notify <@{client.OWNER_ID}> about this.'

            if interaction.response.is_done():
                await interaction.followup.send(content=message)
            else:
                await interaction.response.send_message(content=message)
            
            try:
                raise error
            except:
                debug(f'error in {interaction}', exc_info=True)
    
    def owner_check(interaction: discord.Interaction):
        return interaction.user.id == interaction.client.OWNER_ID

    async def check_stats(interaction: discord.Interaction, user: discord.User): 
        bot = interaction.client
        user_id = user.id

        await interaction.response.defer()
        
        #debug(user_id) 

        link = None

        blacklisted = bot.blacklisted(interaction.guild_id, 'user', user_id)

        links = bot.links_table.find(user_id=user_id)
        main = bot.mains_table.find_one(user_id=user_id)

        sorted_links = sorted(links, key=lambda link: -1 if main and main['acc_id'] == link['acc_id'] else \
            int(link['acc_id']))

        if sorted_links:
            acc_ids = map(lambda link: link['acc_id'], sorted_links)

            await bot.full_profile_book(interaction, user, *acc_ids, blacklist=blacklisted)
        elif user_id == interaction.user.id: 
            await interaction.followup.send(content=f"You're not connected to any accounts. Use the `connecthelp` \
command to learn how to connect accounts.") 
        else: 
            await interaction.followup.send(content=f"This user isn't connected to any accounts.")

    @ds_slash(tree, 'profiles', "Displays the Deeeep.io profiles of the specified user, or yourself")
    @app_commands.describe(user='The member whose stats to check. Defaults to yourself if unspecified')
    async def other_profile(interaction: discord.Interaction, user: discord.User=None):
        return await check_stats(interaction, user or interaction.user)
    
    @tree.context_menu(name='View profiles')
    async def profile_menu_option(interaction: discord.Interaction, user: typing.Union[discord.User, discord.Member]):
        return await check_stats(interaction, user)
    
    @ds_slash(tree, 'skin', 'Displays the stats of a skin')
    @app_commands.describe(skin_query='The name of the skin if looking up by name, or ID if by ID', how_to_lookup='Where to \
search, or "id" to search by ID. Defaults to "approved".')
    @app_commands.describe(version='The version of the skin to view; only used with "id". Defaults to latest approved version.')
    async def skin_command(interaction: discord.Interaction, skin_query: str, 
    how_to_lookup: typing.Literal['id', 'approved', 'pending', 'upcoming']='approved', version: app_commands.Range[int, 1]=0):
        bot = interaction.client

        if how_to_lookup == 'id': 
            return await bot.skin_by_id(interaction, skin_query, version)
        else:
            if version:
                await interaction.response.send_message(content="You can only specify a version if looking up by ID.")
            elif how_to_lookup == 'upcoming' and not bot.is_sb_channel(interaction.channel_id):
                await interaction.response.send_message(content='You can only look up upcoming skins in Artistry Guild/Skin Board \
channels.')
            else:
                return await bot.skin_by_name(interaction, skin_query, how_to_lookup)
    
    @ds_slash(tree, 'participation', "Displays a summary of Artistry members' votes")
    async def participation_display(interaction: discord.Interaction):
        bot = interaction.client

        if bot.is_sb_channel(interaction.channel_id):
            await bot.send_motion_participation(interaction)
        else:
            await interaction.response.send_message(content='You can only view participation in Artistry Guild channels.')
    
    @ds_slash(tree, 'motions', "Displays active and recent motions")
    async def motions_display(interaction: discord.Interaction):
        bot = interaction.client

        if bot.is_sb_channel(interaction.channel_id):
            await bot.motions_book(interaction)
        else:
            await interaction.response.send_message(content='You can only view motions in Artistry Guild channels.')
        
    async def animal_autocomplete(interaction: discord.Interaction, current: str):
        bot = interaction.client

        possibilities = []

        lowered_and_stripped = current.lower().replace(' ', '')

        for animal in bot.animal_stats:
            if lowered_and_stripped in animal['name']:
                possibilities.append(animal['name'])

                if len(possibilities) == 25:
                    break

        choices = [app_commands.Choice(name=poss, value=poss) for poss in possibilities]

        return choices
    
    @ds_slash(tree, 'animal', 'Displays information about the specified animal')
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def display_animal_stats(interaction: discord.Interaction, animal: str): 
        merged_query = animal.replace(' ', '')

        bot = interaction.client
         
        await bot.display_animal(interaction, merged_query)
    
    @ds_slash(tree, 'hackprofile', 'Displays the beta profile corresponding to the username')
    @app_commands.describe(search_mode='How to find the account')
    @app_commands.describe(query='The account username or ID')
    async def display_profile(interaction: discord.Interaction, search_mode: typing.Literal["username", "id"], query: str):
        if search_mode == 'username':
            await interaction.client.display_account_by_username(interaction, query)
        else:
            if query.isnumeric():
                num = int(query)

                if num > 0:
                    await interaction.client.display_account_by_id(interaction, query)

                    return
            
            await interaction.response.send_message(content="That's not a valid account ID.")
    
    @ds_slash(tree, 'map', 'Displays information about the specified map.')
    @app_commands.describe(map='The "string ID" of the map (e.g. nac_ffa), \
or its link')
    @app_commands.describe(find_by="Whether you're searching by numerical ID or string ID. \
Note that numerical is much faster.")
    async def check_map(interaction: discord.Interaction, map: str, find_by: typing.Literal["string_id", "num_id"]="string_id"): 
        bot = interaction.client
        map_url = None

        if find_by == 'string_id':
            map_string_id = bot.get_map_string_id(map) 

            if map_string_id: 
                map_string_id = bot.MAP_URL_ADDITION + map_string_id
                
                map_url = bot.MAP_URL_TEMPLATE.format(map_string_id)
            else:
                await interaction.response.send_message(content=f"`map` should be a string ID (`nac_ffa`) or a Mapmaker link (`https://mapmaker.deeeep.io/map/fishy_ffa`)")
        else:
            if map.isnumeric():
                map_url = bot.MAP_URL_TEMPLATE.format(map)
            else:
                await interaction.response.send_message(content="That's not a map ID.")
        
        if map_url:
            debug(map_url)
            
            await interaction.response.defer()

            map_json = bot.async_get(map_url)[0] 

            if map_json: 
                ID = map_json['id'] 

                if not bot.blacklisted(interaction.guild_id, 'map', ID): 
                    await interaction.followup.send(embed=bot.map_embed(map_json)) 
                else: 
                    await interaction.followup.send(content=f'This map (ID {ID}) is blacklisted from being displayed on this server. ')
            else: 
                await interaction.followup.send(embed=bot.map_error_embed())

    @ds_slash(tree, 'info', 'Displays information about the bot')
    async def send_info(interaction: discord.Interaction): 
        bot = interaction.client

        await interaction.response.send_message(embed=await bot.self_embed()) 

    async def pending_search(bot, interaction: discord.Interaction, filters_str, filters): 
        channel = interaction.channel

        '''
        if bot.is_sb_channel(channel.id): 
            # await bot.pending_display(report, filters_str, filters) 
            pass
        else: 
        '''
        
        await bot.approved_display(interaction, 'pending', filters_str, filters)

    async def approved_search(bot, interaction: discord.Interaction, filters_str, filters): 
        await bot.approved_display(interaction, 'approved', filters_str, filters)
    
    async def upcoming_search(bot, interaction: discord.Interaction, filters_str, filters):
        if bot.is_sb_channel(interaction.channel_id):
            await bot.approved_display(interaction, 'upcoming', filters_str, filters)
        else:
            await interaction.followup.send(content="You can only search upcoming skins in Artistry Guild (Skin Board) channels.")
    
    @ds_slash(tree, 'skins', 'Find all skins that fit the given criteria. You can specify multiple filters.')
    @app_commands.autocomplete(animal=animal_autocomplete)
    @app_commands.describe(where_to_search='What section of the Creators Center to search. Defaults to "approved".')
    @app_commands.describe(category='Show only realistic, seasonal, etc.')
    @app_commands.describe(acceptability="Filter by whether or not they have problems")
    @app_commands.describe(stat_change="Filter by whether they change their animal's stats")
    @app_commands.describe(price="Filter by whether they're free or not")
    @app_commands.describe(reskin="Filter by whether they're edits to existing approved skins")
    @app_commands.describe(animal="Show only skins for a specific animal")
    @app_commands.describe(name_contains='Show only skins whose name contains certain words')
    async def skin_search(interaction: discord.Interaction, 
    where_to_search: typing.Literal["approved", "pending", "upcoming"]='approved',
    category: ds_constants.DS_Constants.AVAILABILITY_FILTERS=None, 
    acceptability: ds_constants.DS_Constants.ACCEPTABILITY_FILTERS=None,
    stat_change: ds_constants.DS_Constants.STAT_CHANGE_FILTERS=None,
    price: ds_constants.DS_Constants.PRICE_FILTERS=None,
    reskin: ds_constants.DS_Constants.PENDING_FILTERS=None,
    animal: str=None, name_contains: str=None):
        await interaction.response.defer()
        
        bot = interaction.client

        filters = category, acceptability, stat_change, price, reskin
        
        # debug(filters)

        mapped_filters = filter(None, filters)
        mapped_filters_2 = filter(None, filters)

        filter_strs = list(map(lambda filter_obj: filter_obj.name, mapped_filters))
        filter_funcs = list(map(lambda filter_obj: filter_obj.value, mapped_filters_2))

        # debug(filter_funcs)

        if animal:
            animal_obj = bot.find_animal_by_name(animal)

            if not animal_obj:
                await interaction.followup.send(content="You gave an invalid animal.")

                return
            else:
                filter_strs.append(animal)
                filter_funcs.append(lambda self, skin: skin['fish_level'] == animal_obj['fishLevel'])
        
        if name_contains:
            filter_strs.append(name_contains)

            lowered = name_contains.lower()

            filter_funcs.append(lambda self, skin: lowered in skin['name'].lower())

        if where_to_search == 'approved': 
            displayer = approved_search

            # filters = filters[1:] 
        elif where_to_search == 'pending': 
            displayer = pending_search

            # filters = filters[1:] 
        elif where_to_search == 'upcoming':
            displayer = upcoming_search
        
        else:
            raise RuntimeError(f'Invalid list for skin search: {where_to_search}')

        filter_names_str = tools.format_iterable(filter_strs, formatter='`{}`') 
        # filter_names_str = filter
        
        await displayer(bot, interaction, filter_names_str, filter_funcs) 
    
    @ds_slash(tree, 'test', 'test command')
    async def test_command(interaction: discord.Interaction):
        await interaction.client.link_help(interaction)
    
    @ds_slash(tree, 'connect', 'Connect your Discord account to a Deeeep.io account')
    @app_commands.describe(account='username (not_a_cat) or profile URL (https://beta.deeeep.io/u/not_a_cat)')
    async def link_account(interaction: discord.Interaction, account: str):
        await interaction.client.link_dep_acc(interaction, account)
    
    @ds_slash(tree, 'connecthelp', 'View instructions on how to connect your account')
    async def connect_help(interaction: discord.Interaction):
        await interaction.client.send_connect_help(interaction)
    
    @ds_slash(tree, 'shutdown', 'Turn off the bot')
    @app_commands.check(owner_check)
    async def shut_down(interaction: discord.Interaction): 
        await interaction.response.send_message(content='shutting down') 

        await interaction.client.logout()

        '''
        self.logging_out = True

        await self.change_presence(status=discord.Status.dnd, activity=discord.Game(name='shutting down'))
        '''
    
    @ds_slash(tree, 'blacklist', 'Manage the server-level blacklist')
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(action='Whether to add or remove from the blacklist', target_type='The type of thing to blacklist',
    deeeepio_id='The ID of the Deeeep.io account or map to blacklist. Not for blacklisting Discord users.', 
    discord_user='The Discord user to blacklist. Not for blacklisting in-game things.')
    @app_commands.guild_only
    async def edit_blacklist(interaction: discord.Interaction, action: typing.Literal['add', 'remove'], 
    target_type: typing.Literal['user', 'account', 'map'], deeeepio_id: app_commands.Range[int, 1]=0, 
    discord_user: discord.User=None):
        bot = interaction.client
        guild_id = interaction.guild_id

        error = ''

        if action == 'add':
            action_str = 'blacklist'
        else:
            action_str = 'unblacklist'

        if deeeepio_id and discord_user:
            error = "You can't specify both `deeeepio_id` and `discord_user`."
        elif target_type == 'user':
            if not discord_user:
                error = f"You need to provide a Discord user to {action_str}."
        elif not deeeepio_id:
            error = f'You need to provide a Deeeep.io {target_type} ID to {action_str}.'
        
        if not error:
            if discord_user:
                deeeepio_id = discord_user.id
            
            if action == 'add':
                data = {
                    'type': target_type, 
                    'guild_id': guild_id, 
                    'target': deeeepio_id, 
                }

                bot.blacklists_table.upsert(data, ['type', 'guild_id', 'target'], ensure=True) 

                await interaction.response.send_message(content=f'{action_str.capitalize()}ed {target_type} with ID `{deeeepio_id}` on this \
server.')
            else:
                bot.blacklists_table.delete(type=target_type, guild_id=guild_id, target=deeeepio_id)

                await interaction.response.send_message(content=f'{action_str.capitalize()}ed {target_type} with ID \
`{deeeepio_id}` on this server.')
        else:
            await interaction.response.send_message(content=error)
    
    @ds_slash(tree, 'tree', 'Displays the evolution tree')
    async def evo_tree(interaction: discord.Interaction):
        with open(interaction.client.TREE, mode='rb') as tree_file:
            discord_file = discord.File(tree_file)

            await interaction.response.send_message(content=f"""The current evolution tree.

If this is outdated, updated evolution trees are appreciated! 
{chars.void}""", file=discord_file)

    @ds_slash(tree, 'habitat', 'Translates a habitat number into a set of habitat flags')
    @app_commands.describe(habitat_num=f'A number that represents a set of habitat requirements')
    async def convert_habitat(interaction: discord.Interaction, 
    habitat_num: app_commands.Range[int, 0, habitat.Habitat.MAX]): 
        hab = habitat.Habitat(habitat_num) 

        await interaction.response.send_message(content=f'`{habitat_num}` translates to `{hab}`.')
    
    @ds_slash(tree, 'error', 'It works by not working')
    @app_commands.check(owner_check)
    async def crash(interaction: discord.Interaction):
        raise RuntimeError("You've been troled")
    
    @ds_slash(tree, 'clear', 'Clear all commands from the tree')
    @app_commands.check(owner_check)
    async def clear_commands(interaction: discord.Interaction):
        bot = interaction.client

        await interaction.response.defer()

        tree.clear_commands(guild=None)
        tree.clear_commands(guild=discord.Object(bot.DEEPCORD_ID))

        tree.add_command(shut_down, guild=discord.Object(bot.DEEPCORD_ID))
        tree.add_command(clear_commands, guild=discord.Object(bot.DEEPCORD_ID))

        await tree.sync()
        await tree.sync(guild=discord.Object(bot.DEEPCORD_ID))

        await interaction.followup.send('Cleared all commands')

    result = await tree.sync()
    guild_result = await tree.sync(guild=discord.Object(client.DEEPCORD_ID))
    
    print(f'global sync: {result}')
    print(f'guild sync: {guild_result}')