import grequests
import discord
import dataset
import asyncio
import sys
import requests
import time
import random
import re
import dateutil.parser as parser
import tools
import commands
from chars import c

import logging

logger = logging.getLogger(__name__) 

logger.setLevel(logging.DEBUG) 

def debug(msg, *args, **kwargs): 
    try: 
        logger.debug(f'{msg}\n', *args, **kwargs) 
    except UnicodeEncodeError: 
        debug('', exc_info=True) 

def clear_file(file, should_log=True):
    file.seek(0)
    file.truncate(0)

    if should_log: 
        debug('cleared') 

def trim_file(file, max_size): 
    debug('trimming\n\n') 

    if not file.closed and file.seekable() and file.readable(): 
        file.seek(0, 2) 

        size = file.tell() 

        #debug(f'file is {size} bytes now') 

        if size > max_size: 
            extra_bytes = size - max_size

            file.seek(extra_bytes) 

            contents = file.read() 

            #trimmed_contents = contents[len(contents) - self.max_size - 1:] 

            #debug(len(contents)) 
            #debug(len(trimmed_contents)) 
            
            clear_file(file, should_log=False) 

            file.seek(0) 

            file.write(contents) 

            file.flush() 

class Dep_io_Stats(discord.Client): 
    DEFAULT_PREFIX = ',' 
    MAX_PREFIX = 5
    PREFIX_SENTINEL = 'none' 

    LINK_SENTINEL = 'remove' 
    LINK_HELP_IMG = 'https://cdn.discordapp.com/attachments/493952969277046787/796576600413175819/linking_instructions.png' 

    DATE_FORMAT = '%B %d, %Y' 

    MAX_TITLE = 256
    MAX_DESC = 2048
    MAX_FIELD_VAL = 1024
    TRAIL_OFF = '...' 
    MAX_LOG = 1000000
    MAX_SEARCH_TIME = 60

    OWNER_ID = 315682382147485697

    DATA_URL_TEMPLATE = 'https://api.deeeep.io/users/{}' 
    PFP_URL_TEMPLATE = 'https://deeeep.io/files/{}' 
    SERVER_LIST_URL = 'http://api.deeeep.io/hosts?beta=1' 
    MAP_URL_TEMPLATE = 'https://api.deeeep.io/maps/{}' 
    SKINS_LIST_URL = 'https://api.deeeep.io/skins' 

    def __init__(self, logs_file_name, storage_file_name): 
        self.db = dataset.connect(storage_file_name) 
        self.links_table = self.db.get_table('account_links') 
        self.prefixes_table = self.db.get_table('prefixes') 

        self.logs_file = open(logs_file_name, mode='w+') 

        handler = logging.StreamHandler(self.logs_file) 

        logger.addHandler(handler) 

        self.tasks = 0
        self.logging_out = False

        self.readied = False

        super().__init__() 
    
    def prefix(self, c): 
        p = self.prefixes_table.find_one(guild_id=c.guild.id) 
        
        if p: 
            return p['prefix'] 
        else: 
            return self.DEFAULT_PREFIX
    
    async def send(self, c, *args, **kwargs): 
        try: 
            await c.send(*args, **kwargs) 
        except discord.errors.Forbidden: 
            debug('that was illegal') 
    
    async def logout(self): 
        self.logs_file.close() 

        await super().logout() 
    
    async def edit_tasks(self, amount): 
        try: 
            self.tasks += amount

            debug(f'now running {self.tasks} tasks') 

            debug('g') 

            if self.tasks == 0: 
                debug('f') 

                trim_file(self.logs_file, self.MAX_LOG) 

                if self.logging_out: 
                    await self.logout() 
        except asyncio.CancelledError: 
            raise
        except: 
            debug('', exc_info=True) 
    
    def task(func): 
        async def task_func(self, *args, **kwargs): 
            await self.edit_tasks(1) 

            try: 
                await func(self, *args, **kwargs) 
            except: 
                debug('', exc_info=True) 
            
            await self.edit_tasks(-1) 
        
        return task_func
    
    def requires_owner(func): 
        async def req_owner_func(s, self, c, m, *args): 
            if m.author.id == self.OWNER_ID: 
                await func(s, self, c, m, *args) 
            else: 
                await self.send(c, content='no u (owner-only command) ', reference=m) 
        
        return req_owner_func
    
    def requires_perms(*perms): 
        def decorator(func): 
            async def req_perms_func(s, self, c, m, *args): 
                author_perms = c.permissions_for(m.author) 

                for perm in perms: 
                    if not getattr(author_perms, perm): 
                        perms_str = tools.format_iterable(perms, formatter='`{}`') 

                        await self.send(c, content=f'You need the following permissions to do this: {perms_str}', reference=m) 

                        break
                else: 
                    await func(s, self, c, m, *args) 
            
            return req_perms_func
        
        return decorator
    
    async def default_args_check(self, c, m, *args): 
        return True

    def command(name, usages): 
        def decorator(func): 
            command_obj = commands.Command(name, usages, func) 

            commands.COMMANDS[name] = command_obj

            return command_obj
        
        return decorator
    
    '''
    def command(name, req_params=(), optional_params=(), args_check=None): 
        total_params = len(req_params) + len(optional_params) 

        def decorator(func): 
            async def comm_func(self, c, m, *args): 
                if (len(req_params) <= len(args) <= total_params): 
                    await func(self, c, m, *args) 
                else: 
                    usage = self.prefix(c) + name

                    if total_params > 0: 
                        total_params_list = [f'({param})' for param in req_params] + [f'[{param}]' for param in optional_params] 

                        usage += ' ' + tools.format_iterable(total_params_list, sep=' ') 

                    await self.send(c, content=f"the correct way to use this command is `{usage}`. ") 
            
            COMMANDS[name] = comm_func

            return comm_func
        
        return decorator
    ''' 
    
    '''
    def sync_get(self, url): 
        json = None

        try: 
            data = requests.get(url) 

            #debug(data.text) 

            if data.ok and data.text: 
                json = data.json() 

            #debug('z') 
        except requests.ConnectionError: 
            debug('connection error') 

            debug('', exc_info=True) 
        
        return json
    ''' 
    
    def async_get(self, *urls): 
        requests_list = [grequests.get(url) for url in urls] 
        
        def handler(request, exception): 
            debug('connection error') 
            debug(exception) 

        datas = grequests.map(requests_list, exception_handler=handler) 

        #debug(datas) 

        jsons = [(data.json() if data.ok and data.text else None) for data in datas] 

        #debug(jsons) 

        return jsons
    
    def get_acc_data(self, acc_id): 
        url = self.DATA_URL_TEMPLATE.format(acc_id) 

        return self.async_get(url)[0] 
    
    def get_map_list(self, list_json): 
        #debug(list_json) 

        map_set = set() 
        
        if list_json: 
            iterator = (server['map_id'] for server in list_json) 

            map_set.update(iterator) 
        
        return map_set
    
    def get_map_datas(self, *map_ids): 
        urls = [self.MAP_URL_TEMPLATE.format(map_id) for map_id in map_ids] 
        
        return self.async_get(*urls) 
    
    def get_map_contribs(self, server_list, acc_id): 
        #debug(server_list) 

        map_list = self.get_map_list(server_list) 

        contrib_names = [] 

        map_jsons = self.get_map_datas(*map_list) 

        for map_json in map_jsons: 
            if map_json: 
                #debug(map_json['string_id']) 
                #debug(map_json['user_id']) 
                #debug(acc_id) 

                if str(map_json['user_id']) == acc_id: 
                    contrib_names.append(map_json['string_id']) 
        
        #debug(contrib_names) 
            
        return contrib_names
    
    def get_skin_contribs(self, skins_list, acc_id): 
        contrib_names = [] 

        if skins_list: 
            for skin in skins_list: 
                if str(skin['user_id']) == acc_id: 
                    contrib_names.append(skin['name']) 
        
        return contrib_names
    
    def get_contribs(self, acc, acc_id, server_list, skins_list): 
        contribs = [] 

        map_contribs = self.get_map_contribs(server_list, acc_id) 

        if map_contribs: 
            map_str = tools.format_iterable(map_contribs, formatter='`{}`') 

            contribs.append(f'Created map(s) {map_str}') 
        
        skin_contribs = self.get_skin_contribs(skins_list, acc_id) 

        if skin_contribs: 
            skin_str = tools.format_iterable(skin_contribs, formatter='`{}`') 

            contribs.append(f'Created skin(s) {skin_str}') 
        
        if acc: 
            if acc['beta']: 
                contribs.append(f'Beta tester') 
        
        #debug(contribs) 
        
        return contribs
    
    def get_all_acc_data(self, acc_id): 
        acc_url = self.DATA_URL_TEMPLATE.format(acc_id) 
        server_list_url = self.SERVER_LIST_URL
        skins_list_url = self.SKINS_LIST_URL

        acc_json, server_list, skins_list = self.async_get(acc_url, server_list_url, skins_list_url) 

        contribs = self.get_contribs(acc_json, acc_id, server_list, skins_list) 

        return acc_json, contribs
    
    def trim_maybe(self, string, limit): 
        if (len(string) > limit): 
            string = string[:limit - len(self.TRAIL_OFF)] + self.TRAIL_OFF
        
        return string
    
    def embed(self, acc_id): 
        acc, contribs = self.get_all_acc_data(acc_id) 

        color = discord.Color.random() 

        if acc: 
            title = f"{acc['name']} (@{acc['username']})"  

            title = self.trim_maybe(title, self.MAX_TITLE)

            desc = acc['description'] 
            
            desc = self.trim_maybe(desc, self.MAX_DESC) 
            
            pfp_url = self.PFP_URL_TEMPLATE.format(acc['picture']) 

            #debug(pfp_url) 
            
            kills = acc['kill_count'] 
            max_score = acc['highest_score'] 
            coins = acc['coins'] 

            #debug(hex(color)) 

            embed = discord.Embed(title=title, type='rich', description=desc, color=color) 

            embed.set_image(url=pfp_url) 

            embed.add_field(name=f"Kills {c['iseedeadfish']}", value=f'{kills:,}') 
            embed.add_field(name=f"Highscore {c['first_place']}", value=f'{max_score:,}') 
            embed.add_field(name=f"Coins {c['deeeepcoin']}", value=f'{coins:,}') 

            date_created = parser.isoparse(acc['date_created']) 
            date_last_played = parser.isoparse(acc['date_last_played']) 

            embed.add_field(name=f"Date created {c['baby']}", value=date_created.strftime(self.DATE_FORMAT)) 
            embed.add_field(name=f"Date last played {c['video_game']}", value=date_last_played.strftime(self.DATE_FORMAT)) 
        else: 
            embed = discord.Embed(title='Error', type='rich', description='An error occurred. ', color=color) 
        
        embed.set_footer(text=f'ID: {acc_id}') 

        if contribs: 
            contribs_str = tools.make_list(contribs) 

            contribs_str = self.trim_maybe(contribs_str, self.MAX_FIELD_VAL) 

            embed.add_field(name=f"Contributions {c['heartpenguin']}", value=contribs_str, inline=False) 

        return embed
    
    async def on_ready(self): 
        debug('ready') 

        self.readied = True
    
    def decode_mention(self, c, mention): 
        #debug(mention) 

        if mention.startswith('<@') and mention.endswith('>'): 
            stripped = mention[2:len(mention) - 1] 

            if stripped.startswith('!'): 
                stripped = stripped[1:] 
        else: 
            stripped = mention
            
        if stripped.isnumeric(): 
            member_id = int(stripped) 
            
            #debug(member_id) 

            m = self.get_user(member_id) 

            #debug(m) 

            return m
    
    async def prompt_for_message(self, c, member_id, choices=None, custom_check=lambda to_check: True, timeout=None,  timeout_warning=10, default_choice=None): 
        mention = '<@{}>'.format(member_id) 

        extension = '{}, reply to this message with '.format(mention) 

        # noinspection PyShadowingNames
        def check(to_check): 
            valid_choice = choices is None or any(((to_check.content.lower() == choice.lower()) for choice in choices)) 
            
            #debug(to_check.channel.id == channel.id) 
            #debug(to_check.author.id == member_id) 
            #debug(valid_choice) 
            #debug(custom_check(to_check)) 
            
            return to_check.channel.id == c.id and to_check.author.id == member_id and valid_choice and custom_check(to_check) 

        to_return = None

        try:
            message = await self.wait_for('message', check=check, timeout=timeout) 
        except asyncio.TimeoutError: 
            await self.send(c, content='{}, time limit exceeded, going with default. '.format(mention)) 

            to_return = default_choice
        else: 
            to_return = message.content
        
        return to_return
    
    @command('stats', {
        (): 'View your own stats', 
        ('@<user>',): "View `<user>`'s stats", 
        ('<user_ID>',): "Same as above except with Discord ID instead to avoid pings", 
    }) 
    async def check_stats(s, self, c, m, user=None): 
        if not user: 
            user_id = m.author.id
        elif not user.isnumeric(): 
            user = self.decode_mention(c, user) 

            #debug(user) 

            user_id = user.id if user else None
        else: 
            user_id = user
        
        #debug(user_id) 

        link = None

        if user_id: 
            link = self.links_table.find_one(user_id=user_id) 

        #debug('f') 

        if link: 
            acc_id = link['acc_id'] 

            await self.send(c, embed=self.embed(acc_id)) 
        elif user_id == m.author.id: 
            await self.send(c, content=f"You're not linked to an account. Type `{self.prefix(c)}link` to learn how to link an account. ", reference=m) 
        else: 
            await self.send(c, content=f"Either you entered the wrong user ID or this user isn't linked.", reference=m) 
    
    async def link_help(self, c, m): 
        await self.send(c, content=f'Click here for instructions on how to link your account. <{self.LINK_HELP_IMG}>', reference=m) 
    
    def get_acc_id(self, query): 
        acc_id = None

        if not query.isnumeric(): 
            m = re.compile('(?:https?://)?(?:www.)?deeeep.io/files/(?P<acc_id>[0-9]+)(?:-temp)?\.[0-9A-Za-z]+(?:\?.*)?\Z').match(query)

            if m: 
                acc_id = m.group('acc_id') 
        else: 
            acc_id = query
        
        return acc_id
    
    async def link_dep_acc(self, c, m, query): 
        if query != self.LINK_SENTINEL: 
            acc_id = self.get_acc_id(query) 

            success = False
            
            if acc_id: 
                acc_data = self.get_acc_data(acc_id) 

                if acc_data: 
                    name = acc_data['name'] 
                    username = acc_data['username'] 

                    if name == str(m.author): 
                        data = {
                            'user_id': m.author.id, 
                            'acc_id': acc_id, 
                        } 

                        self.links_table.upsert(data, ['user_id'], ensure=True) 

                        await self.send(c, content=f"Successfully linked to Deeeep.io account with username `{username}` and ID `{acc_id}`. \
You can change the account's name back now. ", reference=m) 
                    else: 
                        await self.send(c, content=f"You must set your Deeeep.io account's name to your discord tag (`{m.author!s}`) when linking. \
You only need to do this when linking; you can change it back afterward. Read <{self.LINK_HELP_IMG}> for more info. ", reference=m) 

                    success = True
            
            if not success: 
                await self.send(c, content=f'That is not a valid account. Read <{self.LINK_HELP_IMG}> for more info. ', reference=m) 
        else: 
            self.links_table.delete(user_id=m.author.id) 

            await self.send(c, content='Unlinked your account. ') 
    
    @command('link', {
        (): 'View help on linking accounts', 
        ('<account_ID>',): 'Link Deeeep.io account with ID `<account_ID>` to your account', 
        ('<account_profile_pic_URL>',): "Like above, but with the URL of the account's profile picture", 
        (LINK_SENTINEL,): 'Unlink your account', 
    }) 
    async def link(s, self, c, m, query=None): 
        if query: 
            await self.link_dep_acc(c, m, query) 
        else: 
            await self.link_help(c, m) 
    
    @command('statstest', {
        ('<account_ID>',): 'View Deeeep.io account with ID `<account_ID>`', 
        ('<account_profile_pic_URL>',): "Like above, but with the URL of the account's profile picture", 
    }) 
    @requires_owner
    async def cheat_stats(s, self, c, m, query): 
        acc_id = self.get_acc_id(query) 
        
        if acc_id: 
            await self.send(c, embed=self.embed(acc_id)) 
        else: 
            await self.send(c, content=f'That is not a valid account. ', reference=m) 
    
    @command('prefix', {
        ('<prefix>',): "Set the server-wide prefix for this bot to `<prefix>`", 
        (PREFIX_SENTINEL,): 'Reset the server prefix to default', 
    }) 
    @requires_perms('manage_guild') 
    async def set_prefix(s, self, c, m, prefix): 
        if prefix == self.PREFIX_SENTINEL: 
            self.prefixes_table.delete(guild_id=c.guild.id) 

            await self.send(c, content='Deleted custom prefix. ') 
        else: 
            if len(prefix) <= self.MAX_PREFIX: 
                data = {
                    'guild_id': c.guild.id, 
                    'prefix': prefix, 
                } 

                self.prefixes_table.upsert(data, ['guild_id'], ensure=True) 

                await self.send(c, content=f'Custom prefix is now `{prefix}`. ') 
            else: 
                await self.send(c, content=f'Prefix must not exceed {self.MAX_PREFIX} characters. ', reference=m) 
    
    @command('shutdown', {
        (): "Turn off the bot", 
    }) 
    @requires_owner
    async def shut_down(s, self, c, m): 
        await self.send(c, content='shutting down') 

        self.logging_out = True
    
    @command('help', {
        (): 'Get a list of all commands', 
        ('<command>',): 'Get help on `<command>`', 
    }) 
    async def send_help(s, self, c, m, command_name=None): 
        if command_name: 
            comm = commands.COMMANDS.get(command_name.lower(), None) 

            if comm: 
                usage_str = comm.usages_str(self, c, m) 

                await self.send(c, content=f'''How to use the `{command_name}` command: 

{usage_str}''') 
            else: 
                prefix = self.prefix(c) 

                await self.send(c, content=f"That's not a valid command name. Type `{prefix}{s.name}` for a list of commands. ", reference=m) 
        else: 
            com_list_str = tools.format_iterable(commands.COMMANDS.keys(), formatter='`{}`') 
            prefix = self.prefix(c) 

            await self.send(c, content=f'''All commands for this bot: {com_list_str}. 
Type `{prefix}{s.name} <command>` for help on a specified `<command>`''') 
    
    async def execute(self, comm, c, m, *args): 
        await comm.attempt_run(self, c, m, *args) 
    
    @task
    async def handle_command(self, m, c, prefix, words): 
        if not hasattr(c, 'guild'): 
            await self.send(c, content="You can't use me in a DM channel. ")  
        else: 
            permissions = c.permissions_for(c.guild.me) 
            
            if permissions.send_messages: 
                command, *args = words
                command = command[len(prefix):] 

                comm = commands.COMMANDS.get(command.lower(), None) 

                if comm: 
                    await self.execute(comm, c, m, *args) 
    
    async def on_message(self, msg): 
        c = msg.channel

        if hasattr(c, 'guild'): 
            prefix = self.prefix(c) 
            words = msg.content.split() 

            if len(words) >= 1 and words[0].startswith(prefix): 
                await self.handle_command(msg, c, prefix, words) 