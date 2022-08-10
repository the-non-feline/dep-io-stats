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
            raise error
    
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

    @ds_slash(tree, 'profile', "Displays the Deeeep.io profile of the specified user, or yourself")
    @app_commands.describe(user='The member whose stats to check. Defaults to yourself if unspecified')
    async def other_profile(interaction: discord.Interaction, user: discord.User=None):
        return await check_stats(interaction, user or interaction.user)
    
    @ds_slash(tree, 'skin', 'Displays the stats of a skin')
    @app_commands.describe(skin_query='The name of the skin if looking up by name, or ID if by ID', search_type='How I should \
look up the skin. Defaults to `name` if unspecified')
    async def skin_command(interaction: discord.Interaction, skin_query: str, search_type: typing.Literal['id', 'name']='name'): 
        bot = interaction.client

        if search_type == 'id': 
            displayer = bot.skin_by_id
        elif search_type == 'name': 
            displayer = bot.skin_by_name

        print(skin_query)
        
        if skin_query: 
            return await displayer(interaction, skin_query) 
        else: 
            return True
    
    async def animal_autocomplete(interaction: discord.Interaction, current: str):
        bot = interaction.client

        bot.set_animal_stats()

        assert type(current) is str

        possibilities = [filter for filter in bot.ANIMAL_FILTERS if current.lower() in filter]
        possibilities = possibilities[:25]

        choices = [app_commands.Choice(name=choice, value=choice) for choice in possibilities]

        print(choices)

        return choices
    
    @ds_slash(tree, 'animal', 'Displays information about the specified animal')
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def display_animal_stats(interaction: discord.Interaction, animal: str): 
        merged_query = animal.replace(' ', '')

        bot = interaction.client
         
        await bot.display_animal(interaction, merged_query)
    
    @ds_slash(tree, 'hackprofile', 'Displays the beta profile corresponding to the username')
    @app_commands.describe(username='The username of the account to display (e.g. not_a_cat)')
    async def display_profile(interaction: discord.Interaction, username: str):
        await interaction.client.display_account_by_username(interaction, username)
    
    @ds_slash(tree, 'map', 'Displays information about the specified map.')
    @app_commands.describe(map='The "string ID" of the map (e.g. nac_ffa), \
or its link')
    async def check_map(interaction: discord.Interaction, map: str): 
        bot = interaction.client

        map_string_id = bot.get_map_string_id(map) 

        if map_string_id: 
            await interaction.response.defer()

            map_string_id = bot.MAP_URL_ADDITION + map_string_id
            
            map_url = bot.MAP_URL_TEMPLATE.format(map_string_id) 

            map_json = bot.async_get(map_url)[0] 

            if map_json: 
                ID = map_json['id'] 

                if not bot.blacklisted(interaction.guild_id, 'map', ID): 
                    await interaction.followup.send(embed=bot.map_embed(map_json)) 
                else: 
                    await interaction.followup.send(content=f'This map (ID {ID}) is blacklisted from being displayed on this server. ')
            else: 
                await interaction.followup.send(content=f"That's not a valid map (or Mapmaker could be broken).") 
        else: 
            await interaction.response.send_message(content=f"`map` should be a string ID (`nac_ffa`) or a link (`https://mapmaker.deeeep.io/map/fishy_ffa`)")

    @ds_slash(tree, 'info', 'Displays information about the bot')
    async def send_info(interaction: discord.Interaction): 
        bot = interaction.client

        await interaction.response.send_message(embed=await bot.self_embed()) 

    async def pending_search(bot, report: reports.Report, filters_str, filters): 
        channel = report.interaction.channel

        if bot.is_sb_channel(channel.id): 
            await bot.pending_display(report, filters_str, filters) 
        else: 
            await bot.approved_display(report, 'pending', filters_str, filters) 

            report.add(f'***Use this command in a Skin Board channel to get more detailed information.***')

    async def approved_search(bot, report: reports.Report, filters_str, filters): 
        await bot.approved_display(report, 'approved', filters_str, filters)
    
    async def animal_autocomplete(interaction: discord.Interaction, current: str):
        bot = interaction.client

        possibilities = []

        lowered = current.lower()

        for animal in bot.animal_stats:
            if lowered in animal['name']:
                possibilities.append(animal['name'])

                if len(possibilities) == 25:
                    break

        choices = [app_commands.Choice(name=poss, value=poss) for poss in possibilities]

        return choices
    
    @ds_slash(tree, 'skins', 'Displays the list of all skins that fit the given criteria')
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def skin_search(interaction: discord.Interaction, list_name: typing.Literal["approved", "pending"]='approved',
    availability: ds_constants.DS_Constants.AVAILABILITY_FILTERS=None, 
    acceptability: ds_constants.DS_Constants.ACCEPTABILITY_FILTERS=None,
    stat_change: ds_constants.DS_Constants.STAT_CHANGE_FILTERS=None,
    price: ds_constants.DS_Constants.PRICE_FILTERS=None,
    reskin: ds_constants.DS_Constants.PENDING_FILTERS=None,
    animal: str=None):
        await interaction.response.defer()
        
        bot = interaction.client

        filters = availability, acceptability, stat_change, price, reskin
        
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

        if list_name == 'approved': 
            displayer = approved_search

            # filters = filters[1:] 
        elif list_name == 'pending': 
            displayer = pending_search

            # filters = filters[1:] 
        else: 
            displayer = approved_search

        report = reports.Report(interaction)

        if filter: 
            filter_names_str = tools.format_iterable(filter_strs, formatter='`{}`') 
            # filter_names_str = filter
        else: 
            filter_names_str = '(none)' 
        
        await displayer(bot, report, filter_names_str, filter_funcs) 

        await report.send_self()
    
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