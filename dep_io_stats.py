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
import json
import logging
import math

import logs
from logs import debug
import tools
import commands
from chars import c
import trimmed_embed
import report

class Dep_io_Stats(discord.Client): 
    REV_CHANNEL_SENTINEL = 'none' 
    REV_CHANNEL_KEY = 'rev_channel' 
    REV_INTERVAL_KEY = 'rev_interval' 
    REV_LAST_CHECKED_KEY = 'rev_last_checked' 

    DEFAULT_PREFIX = ',' 
    MAX_PREFIX = 5
    PREFIX_SENTINEL = 'none' 

    LINK_SENTINEL = 'remove' 
    LINK_HELP_IMG = 'https://cdn.discordapp.com/attachments/493952969277046787/796576600413175819/linking_instructions.png' 
    INVITE_LINK = 'https://discord.com/oauth2/authorize?client_id=796151711571116042&permissions=347136&scope=bot' 

    DATE_FORMAT = '%B %d, %Y' 
    REV_LOG_TIME_FORMAT = '%m-%d-%Y at %I:%M:%S %p'

    MAX_TITLE = 256
    MAX_DESC = 2048
    MAX_FIELD_VAL = 1024
    TRAIL_OFF = '...' 
    MAX_LOG = 1000000
    MAX_SEARCH_TIME = 60
    MAX_SKIN_SUGGESTIONS = 10

    OWNER_ID = 315682382147485697

    MENTION_REGEX = '\A<@!?(?P<member_id>[0-9]+)>\Z' 

    DATA_URL_TEMPLATE = 'https://api.deeeep.io/users/{}' 
    PFP_URL_TEMPLATE = 'https://deeeep.io/files/{}' 
    SERVER_LIST_URL = 'http://api.deeeep.io/hosts?beta=1' 
    MAP_URL_TEMPLATE = 'https://api.deeeep.io/maps/{}' 
    SKINS_LIST_URL = 'https://api.deeeep.io/skins' 
    LOGIN_URL = 'https://api.deeeep.io/auth/local/signin' 
    SKIN_BOARD_MEMBERS_URL = 'https://api.deeeep.io/users/boardMembers' 
    LOGOUT_URL = 'https://api.deeeep.io/auth/logout' 
    PFP_REGEX = '\A(?:https?://)?(?:www.)?deeeep.io/files/(?P<acc_id>[0-9]+)(?:-temp)?\.[0-9A-Za-z]+(?:\?.*)?\Z' 

    DEFAULT_PFP = 'https://deeeep.io/new/assets/placeholder.png' 

    SKIN_ASSET_URL_TEMPLATE = 'https://deeeep.io/assets/skins/{}' 
    CUSTOM_SKIN_ASSET_URL_ADDITION = 'custom/' 
    SKIN_URL_TEMPLATE = 'https://api.deeeep.io/skins/{}' 
    SKIN_REVIEW_TEMPLATE = 'https://api.deeeep.io/skins/{}/review' 

    SKIN_REVIEW_LIST_URL = 'https://api.deeeep.io/skins/pending?t=review' 
    STATS_UNBALANCE_BLACKLIST = ['OT', 'TT', 'PT', 'ST', 'SS', 'HA'] 
    FLOAT_CHECK_REGEX = '\A(?P<abs_val>[0-9]*\.?[0-9]*)\Z' 

    MAP_URL_ADDITION = 's/' 
    MAPMAKER_URL_TEMPLATE = 'https://mapmaker.deeeep.io/map/{}' 
    MAP_REGEX = '\A(?:(?:https?://)?(?:www.)?mapmaker.deeeep.io/map/)?(?P<map_string_id>[0-9_A-Za-z]+)\Z' 

    PENDING_SKINS_LIST_URL = 'https://api.deeeep.io/skins/pending' 

    def __init__(self, logs_file_name, storage_file_name, email, password): 
        self.email = email
        self.password = password

        self.db = dataset.connect(storage_file_name) 
        self.links_table = self.db.get_table('account_links') 
        self.prefixes_table = self.db.get_table('prefixes') 
        self.rev_data_table = self.db.get_table('rev_data') 

        self.logs_file = open(logs_file_name, mode='w+', encoding='utf-8') 

        handler = logging.StreamHandler(self.logs_file) 

        logs.logger.addHandler(handler) 

        #self.levels_file = open(levels_file_name, mode='r') 

        self.tasks = 0
        self.logging_out = False

        self.readied = False
        self.token = None

        self.auto_rev_process = None

        super().__init__() 
    
    def prefix(self, c): 
        p = self.prefixes_table.find_one(guild_id=c.guild.id) 
        
        if p: 
            return p['prefix'] 
        else: 
            return self.DEFAULT_PREFIX
    
    def rev_channel(self): 
        c_entry = self.rev_data_table.find_one(key=self.REV_CHANNEL_KEY) 

        if c_entry: 
            c_id = c_entry['channel_id'] 

            c = self.get_channel(c_id) 

            return c
    
    async def send(self, c, *args, **kwargs): 
        try: 
            return await c.send(*args, **kwargs) 
        except discord.errors.Forbidden: 
            debug('that was illegal') 
    
    async def logout(self): 
        if self.auto_rev_process: 
            self.auto_rev_process.cancel() 
        
        self.logs_file.close() 
        #self.levels_file.close() 

        await super().logout() 
    
    def log_out_acc(self): 
        if self.token: 
            former_token = self.token

            self.token = None

            debug(f'relinquished token ({former_token})') 

        ''' 
        logout_request = grequests.request('GET', self.LOGOUT_URL, headers={
            'Authorization': f'Bearer {self.token}', 
        }) 

        result = self.async_get(logout_request)[0] 

        debug(f'logout of Deeeep.io account status: {result}')
        ''' 
    
    async def edit_tasks(self, amount): 
        try: 
            self.tasks += amount

            debug(f'now running {self.tasks} tasks') 

            debug('g') 

            if self.tasks == 0: 
                debug('f') 

                self.log_out_acc() 

                logs.trim_file(self.logs_file, self.MAX_LOG) 

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
        async def req_owner_func(self, c, m, *args): 
            if m.author.id == self.OWNER_ID: 
                return await func(self, c, m, *args) 
            else: 
                await self.send(c, content='no u (owner-only command) ', reference=m) 
        
        return req_owner_func
    
    @staticmethod
    def has_perms(req_all, req_one, perms): 
        for perm in req_all: 
            if not getattr(perms, perm): 
                return False
        
        if req_one: 
            for perm in req_one: 
                if getattr(perms, perm): 
                    return True
            else: 
                return False
        else: 
            return True
    
    def requires_perms(req_all=(), req_one=()): 
        def decorator(func): 
            async def req_perms_func(self, c, m, *args): 
                author_perms = c.permissions_for(m.author) 

                if self.has_perms(req_all, req_one, author_perms): 
                    return await func(self, c, m, *args) 
                else: 
                    req_all_str = f"all of the following permissions: {tools.format_iterable(req_all, formatter='`{}`')}" 
                    req_one_str = f"at least one of the following permissions: {tools.format_iterable(req_one, formatter='`{}`')}" 

                    if req_one and req_all: 
                        req_str = req_all_str + ' and ' + req_one_str
                    elif req_all: 
                        req_str = req_all_str
                    else: 
                        req_str = req_one_str
                    
                    await self.send(c, content=f'You need {req_str} to use this command', reference=m) 
            
            return req_perms_func
        
        return decorator
    
    def requires_sb_channel(func): 
        async def req_channel_func(self, c, m, *args): 
            sb_channel = self.rev_channel() 

            if sb_channel and c.id == sb_channel.id: 
                return await func(self, c, m, *args) 
            else: 
                await self.send(c, content="This command is reserved for Skin Board channels.", reference=m) 
        
        return req_channel_func
    
    async def default_args_check(self, c, m, *args): 
        return True

    def command(name, definite_usages={}, indefinite_usages={}, public=True): 
        def decorator(func): 
            command_obj = commands.Command(func, name, definite_usages, indefinite_usages, public) 

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
    
    def async_get(self, *all_requests): 
        requests_list = [] 

        for request in all_requests: 
            if type(request) is str: # plain url
                to_add = grequests.get(request) 
            elif type(request) is tuple: # (method, url) 
                to_add = grequests.request(*request) 
            else: 
                to_add = request
            
            requests_list.append(to_add) 
        
        def handler(request, exception): 
            debug('connection error') 
            debug(exception) 

        datas = grequests.map(requests_list, exception_handler=handler) 

        #debug(datas) 

        jsons = [] 

        for data in datas: 
            to_append = None
            
            if data: 
                if data.ok and data.text: 
                    to_append = data.json() 
                else: 
                    debug(data.text) 
            else: 
                debug('connection error, no data') 

            jsons.append(to_append) 

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
    
    def get_map_urls(self, *map_ids): 
        urls = [self.MAP_URL_TEMPLATE.format(map_id) for map_id in map_ids] 
        
        return urls
    
    def get_map_contribs(self, map_jsons, acc_id): 
        #debug(server_list) 

        contrib_names = [] 

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
    
    def get_skin_board_role(self, members_list, acc_id): 
        role = None

        if members_list: 
            prev_member_id = None
            reached_manager = False

            for member in members_list: 
                member_id = member['id'] 

                #debug(member_id) 

                if prev_member_id and prev_member_id > member_id: 
                    reached_manager = True
                
                if str(member_id) == acc_id: 
                    position = 'Manager' if reached_manager else 'Member' 
                    role = f'Skin Board {position}' 

                    break
                
                prev_member_id = member_id
        
        return role
    
    def get_contribs(self, acc, acc_id, map_list, skins_list): 
        contribs = [] 

        map_contribs = self.get_map_contribs(map_list, acc_id) 

        if map_contribs: 
            map_str = tools.format_iterable(map_contribs, formatter='`{}`') 

            contribs.append(f'Created map(s) {map_str}') 
        
        skin_contribs = self.get_skin_contribs(skins_list, acc_id) 

        if skin_contribs: 
            skin_str = tools.format_iterable(skin_contribs, formatter='`{}`') 

            contribs.append(f'Created skin(s) {skin_str}') 
        
        #debug(contribs) 
        
        return contribs
    
    def get_roles(self, acc, acc_id, members_list): 
        roles = [] 

        skin_board_role = self.get_skin_board_role(members_list, acc_id) 

        if skin_board_role: 
            roles.append(skin_board_role) 
        
        if acc: 
            if acc['beta']: 
                roles.append(f'Beta Tester') 
        
        return roles
    
    def get_all_acc_data(self, acc_id): 
        acc_url = self.DATA_URL_TEMPLATE.format(acc_id) 
        server_list_url = self.SERVER_LIST_URL
        skins_list_url = self.SKINS_LIST_URL

        if not self.token: 
            login_url = self.LOGIN_URL

            login_request = grequests.request('POST', login_url, data={
                'email': self.email, 
                'password': self.password, 
            }) 

            acc_json, server_list, skins_list, login_json = self.async_get(acc_url, server_list_url, skins_list_url, login_request) 

            if login_json: 
                if not self.token: 
                    self.token = login_json['token'] 

                    debug(f'fetched token ({self.token})') 
                else: 
                    debug(f'seems like another process got the token ({self.token}) already') 
            else: 
                debug(f'error fetching token, which is currently ({self.token})') 
        else: 
            debug(f'already have token ({self.token})') 

            acc_json, server_list, skins_list = self.async_get(acc_url, server_list_url, skins_list_url) 

        map_list = self.get_map_list(server_list) 
        map_urls = self.get_map_urls(*map_list) 
        
        round_2_urls = map_urls.copy() 

        members_list = None

        if self.token: 
            members_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            round_2_urls.append(members_request) 

            *map_jsons, members_list = self.async_get(*round_2_urls) 

            #debug(members_list) 
        else: 
            map_jsons = self.async_get(*round_2_urls) 

        contribs = self.get_contribs(acc_json, acc_id, map_jsons, skins_list) 
        roles = self.get_roles(acc_json, acc_id, members_list) 

        return acc_json, contribs, roles
        
    def get_reskins(self): 
        pending_list = self.async_get(self.PENDING_SKINS_LIST_URL)[0] 

        if pending_list: 
            unnoticed_pending = [] 
            upcoming_pending = [] 

            for pending in pending_list: 
                if pending['parent']: 
                    if pending['upcoming']: 
                        upcoming_pending.append(pending) 
                    else: 
                        unnoticed_pending.append(pending) 
        else: 
            unnoticed_pending = None
            upcoming_pending = None
        
        return unnoticed_pending, upcoming_pending
    
    def get_skin(self, skins_list, query): 
        suggestions = [] 

        for skin in skins_list: 
            skin_name = skin['name'] 

            lowered_name = skin_name.lower() 
            lowered_query = query.lower() 

            #debug(lowered_name) 
            #debug(lowered_query) 

            if lowered_name == lowered_query: 
                return skin
            elif lowered_query in lowered_name or lowered_name in lowered_query: 
                suggestions.append(skin) 
        else: 
            return suggestions
    
    def unbalanced_stats(self, skin): 
        broken = False
        unbalanced = False

        stat_changes = skin['attributes'] 

        if stat_changes: 
            unbalanced = True

            split_changes = stat_changes.split(';') 

            prev_sign = None

            for change_str in split_changes: 
                stat, value = change_str.split('=') 

                sign = value[0] 
                abs_value = value[1:] 

                m = re.compile(self.FLOAT_CHECK_REGEX).match(abs_value) 

                if m: 
                    abs_val = m.group('abs_val') 

                    try: 
                        float(abs_val) 
                    except ValueError: 
                        broken = True

                        debug(f'{abs_value} passed regex but is not a float') 
                else: 
                    broken = True

                    debug(f'{abs_value} failed regex') 

                if stat not in self.STATS_UNBALANCE_BLACKLIST: 
                    if prev_sign and prev_sign != sign: 
                        unbalanced = False
                    
                    prev_sign = sign
        
        unbalance_sign = prev_sign if unbalanced else None

        debug(broken) 
        debug(unbalance_sign) 

        return broken, unbalance_sign
    
    def reject_reasons(self, skin): 
        reasons = [] 

        skin_id = skin['id'] 

        skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

        debug(skin_url) 

        if not skin['reddit_link']: 
            reasons.append('lack of Reddit link') 
        
        broken, unbalance_sign = self.unbalanced_stats(skin) 

        if broken: 
            reasons.append(f'undefined stat changes') 
        
        if unbalance_sign: 
            reasons.append(f'unbalanced stat changes ({unbalance_sign})') 
        
        return reasons
    
    def inspect_skins(self, review_list): 
        rejected = [] 
        reasons = [] 

        for skin in review_list: 
            rej_reasons = self.reject_reasons(skin) 

            if rej_reasons: 
                rejected.append(skin) 
                reasons.append(rej_reasons) 
        
        #debug(rejected) 
        #debug(reasons) 
        
        return rejected, reasons
    
    def get_review_token(self): 
        if not self.token: 
            login_url = self.LOGIN_URL

            login_request = grequests.request('POST', login_url, data={
                'email': self.email, 
                'password': self.password, 
            }) 

            login_json = self.async_get(login_request)[0] 

            if login_json: 
                if not self.token: 
                    self.token = login_json['token'] 

                    debug(f'fetched token ({self.token})') 
                else: 
                    debug(f'seems like another process got the token ({self.token}) already') 
            else: 
                debug(f'error fetching token, which is currently ({self.token})') 
        else: 
            debug(f'already have token ({self.token})') 
    
    def fake_check(self, r, rejected, reasons, list_json, silent_fail): 
        r.add(f'**{len(rejected)} out of {len(list_json)} failed**') 

        if rejected: 
            r.add('') 

            for skin, reason in zip(rejected, reasons): 
                reason_str = tools.format_iterable(reason, formatter='`{}`') 

                skin_id = skin['id'] 

                skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 

                rejection_str = f"**{skin['name']}** (link {skin_url}) by {c_name} ({c_username}) has the following issues: {reason_str}" 

                r.add(rejection_str) 
    
    def real_check(self, r, rejected, reasons, list_json, silent_fail): 
        message = f'**{len(rejected)} out of {len(list_json)} failed**' 

        if not silent_fail: 
            r.add(message) 
        else: 
            debug(message) 

        if rejected: 
            r.add('') 

            rejection_requests = [] 

            for skin in rejected: 
                skin_id = skin['id'] 
                skin_version = skin['version'] 

                url = self.SKIN_REVIEW_TEMPLATE.format(skin_id) 

                rej_req = grequests.request('POST', url, headers={
                    'Authorization': f'Bearer {self.token}', 
                }, data={
                    "version": skin_version, 
                }) 

                rejection_requests.append(rej_req) 
            
            debug(rejection_requests) 
            
            rej_results = self.async_get(*rejection_requests) 

            debug(rej_results) 

            for result, skin, reason in zip(rej_results, rejected, reasons): 
                if result is not None: 
                    rej_type = "Rejection" 
                    color = 0xff0000
                else: 
                    rej_type = "Rejection Attempt" 
                    color = 0xffff00
                
                reason_str = tools.make_list(reason) 

                skin_name = skin['name'] 
                skin_id = skin['id'] 
                skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

                skin_link = skin['reddit_link'] 

                if skin_link: 
                    desc = f'[Reddit link]({skin_link})' 
                else: 
                    desc = None

                asset_name = skin['asset'] 

                if asset_name[0].isnumeric(): 
                    asset_name = self.CUSTOM_SKIN_ASSET_URL_ADDITION + asset_name

                asset_url = tools.salt_url(self.SKIN_ASSET_URL_TEMPLATE.format(asset_name)) 

                debug(asset_url) 
                
                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 
                c_str = f'{c_name} (@{c_username})' 

                embed = trimmed_embed.TrimmedEmbed(title=skin_name, type='rich', description=desc, url=skin_url, color=color) 

                embed.set_author(name=f'Skin {rej_type}') 

                embed.set_thumbnail(url=asset_url) 

                embed.add_field(name=f"Creator {c['carpenter']}", value=c_str, inline=False) 
                embed.add_field(name=f"Rejection reasons {c['scroll']}", value=reason_str, inline=False) 

                embed.set_footer(text=f'ID: {skin_id}') 

                r.add(embed) 

                ''' 
                start = f"Rejected {c['x']}" if result is not None else f"Attemped to reject {c['warning']}" 

                reason_str = tools.format_iterable(reason, formatter='`{}`') 

                skin_id = skin['id'] 
                skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 
                
                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 

                rejection_str = f"{start} **{skin['name']}** (link {skin_url}) by {c_name} ({c_username}) for the following reasons: {reason_str}" 

                r.add(rejection_str) 
                ''' 
    
    async def check_review(self, c, processor, silent_fail=False): 
        r = report.Report(self, c) 

        self.get_review_token() 

        if self.token: 
            list_request = grequests.request('GET', self.SKIN_REVIEW_LIST_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            list_json = self.async_get(list_request)[0] 

            if list_json: 
                rejected, reasons = self.inspect_skins(list_json) 

                processor(r, rejected, reasons, list_json, silent_fail) 
            elif list_json is None: 
                message = 'Error fetching skins.' 

                if not silent_fail: 
                    r.add(message) 
                else: 
                    debug(message) 
            else: 
                message = 'There are no skins to check.'

                if not silent_fail: 
                    r.add(message) 
                else: 
                    debug(message) 
        else: 
            message = 'Error logging in to perform this task. ' 

            if not silent_fail: 
                r.add(message) 
            else: 
                debug(message) 
        
        await r.send_self() 
    
    '''
    def get_animal(self, animal_id): 
        try: 
            obj = json.load(self.levels_file) 
        except json.JSONDecodeError: 
            debug('Error reading levels file', exc_info=True) 
        else: 
            index = int(animal_id) 

            if index < len(obj): 
                animal_obj = obj[int(animal_id)] 

                return animal_obj['name'] 
            else: 
                return animal_id
    ''' 

    async def self_embed(self, channel): 
        prefix = self.prefix(channel) 
        com_list_str = tools.format_iterable(commands.Command.all_commands(public_only=True), formatter='`{}`') 

        guilds = self.guilds
        guild_count = len(guilds) 

        user_count = self.links_table.count() 

        self_user = self.user

        color = discord.Color.random() 

        if self_user: 
            avatar_url = self_user.avatar_url
            discord_tag = str(self_user) 
        else: 
            avatar_url = None
            discord_tag = "Couldn't fetch Discord tag" 
        
        invite_hyperlink = f'[Invite link]({self.INVITE_LINK})' 
        
        embed = trimmed_embed.TrimmedEmbed(title=discord_tag, description=invite_hyperlink, color=color) 

        if avatar_url: 
            url = str(avatar_url) 
            
            salted = tools.salt_url(url) 

            debug(salted) 

            embed.set_thumbnail(url=salted) 

        owner = await self.fetch_user(self.OWNER_ID) 

        if owner: 
            owner_tag = str(owner) 

            embed.add_field(name=f"Creator {c['carpenter']}", value=owner_tag) 
        
        com_list = f'''{com_list_str}

Type `{prefix}{self.send_help.name} <command>` for help on a specified `<command>`''' 

        embed.add_field(name=f"Commands {c['scroll']}", value=com_list, inline=False) 

        embed.set_footer(text=f'Used by {user_count} users across {guild_count} guilds') 

        return embed
    
    def skin_embed(self, skin): 
        color = discord.Color.random() 

        stat_changes = skin['attributes'] 
        when_created = skin['created_at'] 
        designer_id = skin['designer_id'] 
        animal_id = skin['fish_level'] 
        ID = skin['id'] 
        price = skin['price'] 
        sales = skin['sales'] 
        last_updated = skin['updated_at'] 
        user_name = skin['user_name'] 
        version = skin['version'] 

        desc = None
        reddit_link = None
        category = None
        season = None
        usable = None

        skin_url = self.SKIN_URL_TEMPLATE.format(ID) 

        skin_json = self.async_get(skin_url)[0] 

        if skin_json: 
            desc = skin_json['description'] 

            #debug(desc) 

            reddit_link = skin_json['reddit_link'] 
            category = skin_json['category'] 
            season = skin_json['season'] 
            usable = skin_json['usable'] 

        #debug(desc) 

        embed = trimmed_embed.TrimmedEmbed(title=skin['name'], description=desc, color=color, url=reddit_link) 

        asset_name = skin['asset'] 

        if asset_name[0].isnumeric(): 
            asset_name = self.CUSTOM_SKIN_ASSET_URL_ADDITION + asset_name

        asset_url = tools.salt_url(self.SKIN_ASSET_URL_TEMPLATE.format(asset_name)) 

        debug(asset_url) 

        embed.set_image(url=asset_url) 

        #animal_name = self.get_animal(animal_id) 

        embed.add_field(name=f"Animal {c['fish']}", value=animal_id) 
        embed.add_field(name=f"Price {c['deeeepcoin']}", value=f'{price:,}') 
        embed.add_field(name=f"Sales {c['stonkalot']}", value=f'{sales:,}') 

        if stat_changes: 
            stat_changes_str = tools.make_list(stat_changes.split(';')) 

            embed.add_field(name=f"Stat changes {c['change']}", value=stat_changes_str, inline=False) 
        
        if category: 
            embed.add_field(name=f"Category {c['folder']}", value=category) 

        if season: 
            embed.add_field(name=f"Season {c['calendar']}", value=season) 
        
        if usable: 
            embed.add_field(name=f"Usable {c['check']}", value=usable) 
        
        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {c['tools']}", value=date_created.strftime(self.DATE_FORMAT)) 

        version_str = str(version) 
        version_inline = True

        if last_updated: 
            date_updated = parser.isoparse(last_updated) 

            version_str += f' (updated {date_updated.strftime(self.DATE_FORMAT)})' 
            version_inline = False
        
        embed.add_field(name=f"Version {c['wrench']}", value=version_str, inline=version_inline) 

        if user_name: 
            user_username = skin['user_username'] 
            user_pfp = skin['user_picture'] 

            creator = f'{user_name} (@{user_username})' 

            if not user_pfp: 
                user_pfp = self.DEFAULT_PFP
            else: 
                user_pfp = self.PFP_URL_TEMPLATE.format(user_pfp)
            
            pfp_url = tools.salt_url(user_pfp) 

            debug(pfp_url) 

            embed.set_author(name=creator, icon_url=pfp_url) 

        embed.set_footer(text=f"ID: {ID}") 

        return embed
    
    def acc_embed(self, acc_id): 
        acc, contribs, roles = self.get_all_acc_data(acc_id) 

        color = discord.Color.random() 

        if acc: 
            title = f"{acc['name']} (@{acc['username']})"  

            desc = acc['description'] 

            pfp = acc['picture'] 

            #debug(pfp_url) 
            
            kills = acc['kill_count'] 
            max_score = acc['highest_score'] 
            coins = acc['coins'] 

            #debug(hex(color)) 

            embed = trimmed_embed.TrimmedEmbed(title=title, type='rich', description=desc, color=color) 
            
            if not pfp: 
                pfp = self.DEFAULT_PFP
            else: 
                pfp = self.PFP_URL_TEMPLATE.format(pfp) 
            
            pfp_url = tools.salt_url(pfp) 

            debug(pfp_url) 
            
            embed.set_image(url=pfp_url) 

            embed.add_field(name=f"Kills {c['iseedeadfish']}", value=f'{kills:,}') 
            embed.add_field(name=f"Highscore {c['first_place']}", value=f'{max_score:,}') 
            embed.add_field(name=f"Coins {c['deeeepcoin']}", value=f'{coins:,}') 

            when_created = acc['date_created'] 
            when_last_played = acc['date_last_played'] 

            if when_created: 
                date_created = parser.isoparse(when_created) 

                embed.add_field(name=f"Date created {c['baby']}", value=date_created.strftime(self.DATE_FORMAT)) 

            if when_last_played: 
                date_last_played = parser.isoparse(when_last_played) 

                embed.add_field(name=f"Date last played {c['video_game']}", value=date_last_played.strftime(self.DATE_FORMAT)) 
        else: 
            embed = trimmed_embed.TrimmedEmbed(title='Error fetching account statistics', type='rich', description="There was an error fetching account statistics. ", color=color) 

            embed.add_field(name="Why?", value="This usually happens when the game isn't working. ") 
            embed.add_field(name="What now?", value="Don't spam this command. Just try again when the game works again. ") 
        
        embed.set_footer(text=f'ID: {acc_id}') 

        if contribs: 
            contribs_str = tools.make_list(contribs) 

            embed.add_field(name=f"Contributions {c['heartpenguin']}", value=contribs_str, inline=False) 
        
        if roles: 
            roles_str = tools.format_iterable(roles) 

            embed.add_field(name=f"Roles {c['cooloctopus']}", value=roles_str, inline=False)

        return embed
    
    def count_objects(self, objs): 
        class Counter: 
            total_obj = 0
            total_points = 0
            counters = {} 

            def __init__(self, layer_name, display_name=None): 
                self.layer_name = layer_name
                self.display_name = display_name

                self.obj = 0
                self.points = 0

                self.counters[layer_name] = self
            
            def add(self, element): 
                points = 1

                if 'points' in element: 
                    points = len(element['points']) 

                self.obj += 1
                self.__class__.total_obj +=1

                self.points += points
                self.__class__.total_points += points
            
            def get_display_name(self): 
                if self.display_name: 
                    return self.display_name
                else: 
                    return self.layer_name.replace('-', ' ') 
            
            @classmethod
            def add_element(cls, element): 
                layer_id = element['layerId'] 

                if layer_id in cls.counters: 
                    counter = cls.counters[layer_id] 
                else: 
                    counter = cls(layer_id) 
                
                counter.add(element) 

        [Counter.add_element(element) for element in objs] 

        result_list = [f'{counter.obj:,} {counter.get_display_name()} ({counter.points:,} points)' for counter in Counter.counters.values()] 

        result_list.insert(0, f'**{Counter.total_obj:,} total objects ({Counter.total_points:,} points)**') 

        return result_list
    
    def map_embed(self, map_json): 
        color = discord.Color.random() 

        title = map_json['title'] 
        ID = map_json['id'] 
        string_id = map_json['string_id'] 
        desc = map_json['description'] 
        likes = map_json['likes'] 
        objects = map_json['objects'] 
        clone_of = map_json['cloneof_id'] 

        when_created = map_json['created_at'] 
        when_updated = map_json['updated_at'] 

        map_data = json.loads(map_json['data']) 
        tags = map_json['tags'] 
        creator = map_json['user'] 

        tags_list = [tag['id'] for tag in tags] 
        creator_name = creator['name'] 
        creator_username = creator['username'] 
        creator_pfp = creator['picture'] 

        world_size = map_data['worldSize'] 
        width = world_size['width'] 
        height = world_size['height'] 

        objs = map_data['screenObjects'] 

        map_link = self.MAPMAKER_URL_TEMPLATE.format(string_id) 

        embed = trimmed_embed.TrimmedEmbed(title=title, description=desc, color=color, url=map_link) 

        embed.add_field(name=f"Likes {c['thumbsup']}", value=f'{likes:,}') 
        
        embed.add_field(name=f"Dimensions {c['triangleruler']}", value=f'{width} x {height}') 

        if 'settings' in map_data: 
            settings = map_data['settings'] 
            gravity = settings['gravity'] 

            embed.add_field(name=f"Gravity {c['down']}", value=f'{gravity:,}') 

        obj_count_list = self.count_objects(objs) 

        obj_count_str = tools.make_list(obj_count_list) 

        embed.add_field(name=f"Object count {c['scroll']}", value=obj_count_str, inline=False) 

        creator_str = f'{creator_name} (@{creator_username})'

        if not creator_pfp: 
            creator_pfp = self.DEFAULT_PFP
        else: 
            creator_pfp = self.PFP_URL_TEMPLATE.format(creator_pfp) 
        
        pfp_url = tools.salt_url(creator_pfp) 

        debug(pfp_url) 

        embed.set_author(name=creator_str, icon_url=pfp_url) 

        if clone_of: 
            clone_url = self.MAP_URL_TEMPLATE.format(clone_of) 

            clone_json = self.async_get(clone_url)[0] 

            if clone_json: 
                clone_title = clone_json['title'] 
                clone_string_id = clone_json['string_id'] 

                clone_link = self.MAPMAKER_URL_TEMPLATE.format(clone_string_id) 

                embed.add_field(name=f"Cloned from {c['notes']}", value=f'[{clone_title}]({clone_link})') 
        
        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {c['tools']}", value=date_created.strftime(self.DATE_FORMAT)) 
        
        if when_updated: 
            date_updated = parser.isoparse(when_updated) 

            embed.add_field(name=f"Date last updated {c['wrench']}", value=date_updated.strftime(self.DATE_FORMAT)) 

        if tags_list: 
            tags_str = tools.format_iterable(tags_list, formatter='`{}`') 

            embed.add_field(name=f"Tags {c['label']}", value=tags_str, inline=False) 

        embed.set_footer(text=f'''ID: {ID}
String ID: {string_id}''') 

        return embed
    
    def reskins_embed(self): 
        color = discord.Color.random() 

        pending, upcoming = self.get_reskins() 

        embed = trimmed_embed.TrimmedEmbed(type='rich', title='Pending Reskins', description='Unreleased reskins in Creators Center', color=color) 

        if pending is None: 
            pending_str = 'There was an error fetching skins.' 
        elif pending: 
            pending_list = map(lambda skin: skin['name'], pending) 

            pending_str = tools.make_list(pending_list) 
        else: 
            pending_str = 'There are no unnoticed reskins.' 
        
        embed.add_field(name=f"Unnoticed reskins {c['ghost']}", value=pending_str, inline=False) 

        if upcoming is None: 
            upcoming_str = 'There was an error fetching skins.' 
        elif upcoming: 
            upcoming_list = map(lambda skin: skin['name'], upcoming) 

            upcoming_str = tools.make_list(upcoming_list) 
        else: 
            upcoming_str = 'There are no upcoming reskins.' 
        
        embed.add_field(name=f"Upcoming reskins {c['clock']}", value=upcoming_str, inline=False) 

        return embed
    
    def time_exceeded(self): 
        last_checked_row = self.rev_data_table.find_one(key=self.REV_LAST_CHECKED_KEY) 

        if last_checked_row: 
            interval_row = self.rev_data_table.find_one(key=self.REV_INTERVAL_KEY) 

            if interval_row: 
                last_checked = last_checked_row['time'] 
                interval = interval_row['interval'] 

                current_time = time.time() 

                return current_time - last_checked >= interval
            else: 
                debug('No interval set') 
        else: 
            debug('No last_checked') 

            return True
    
    async def auto_rev(self): 
        time_str = time.strftime(self.REV_LOG_TIME_FORMAT) 

        debug(f'Checked at {time_str}') 

        rev_channel = self.rev_channel() 

        if rev_channel: 
            await self.check_review(rev_channel, self.real_check, silent_fail=True) 
        else: 
            debug('No rev channel set') 
    
    def write_new_time(self): 
        data = {
            'key': self.REV_LAST_CHECKED_KEY, 
            'time': time.time(), 
        } 

        self.rev_data_table.upsert(data, ['key'], ensure=True) 
    
    @task
    async def auto_rev_task(self): 
        await self.auto_rev() 

        self.write_new_time() 
    
    async def auto_rev_loop(self): 
        while True: 
            try: 
                if self.time_exceeded(): 
                    await self.auto_rev_task() 
                
                await asyncio.sleep(1) 
            except asyncio.CancelledError: 
                raise
            except: 
                debug('', exc_info=True) 
    
    async def on_ready(self): 
        self.readied = True

        if not self.auto_rev_process: 
            self.auto_rev_process = self.loop.create_task(self.auto_rev_loop()) 

            debug('created auto rev process') 
        
        debug('ready') 
    
    def decode_mention(self, c, mention): 
        member_id = None

        if not mention.isnumeric(): 
            m = re.compile(self.MENTION_REGEX).match(mention)

            if m: 
                member_id = m.group('member_id') 
        else: 
            member_id = mention
        
        #debug(member_id) 
        
        return int(member_id) if member_id else None
    
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
    
    @command('stats', definite_usages={
        (): 'View your own stats', 
        ('@<user>',): "View `<user>`'s stats", 
        ('<user_ID>',): "Same as above except with Discord ID instead to avoid pings", 
    }) 
    async def check_stats(self, c, m, user=None): 
        if not user: 
            user_id = m.author.id
        else: 
            user_id = self.decode_mention(c, user) 
        
        #debug(user_id) 

        link = None

        if user_id: 
            link = self.links_table.find_one(user_id=user_id) 

            #debug('f') 

            if link: 
                acc_id = link['acc_id'] 

                await self.send(c, embed=self.acc_embed(acc_id)) 
            elif user_id == m.author.id: 
                await self.send(c, content=f"You're not linked to an account. Type `{self.prefix(c)}link` to learn how to link an account. ", reference=m) 
            else: 
                await self.send(c, content=f"This user isn't linked.", reference=m) 
        else: 
            return True
    
    @command('skin', indefinite_usages={
        ('<skin name>',): "View the stats of skin with `<skin name>`.", 
    }) 
    async def check_skin(self, c, m, *skin_query): 
        skin_name = ' '.join(skin_query) 

        skins_list_url = self.SKINS_LIST_URL

        skins_list = self.async_get(skins_list_url)[0] 
        
        if skins_list: 
            skin_data = self.get_skin(skins_list, skin_name) 

            skin_json = None

            if type(skin_data) is list: 
                if len(skin_data) == 1: 
                    skin_json = skin_data[0] 
                else: 
                    text = "That's not a valid skin name. " 

                    if 0 < len(skin_data) <= self.MAX_SKIN_SUGGESTIONS: 
                        skin_names = (skin['name'] for skin in skin_data) 

                        suggestions_str = tools.format_iterable(skin_names, formatter='`{}`') 

                        text += f"Maybe you meant one of these? {suggestions_str}" 

                    await self.send(c, content=text, reference=m) 
            else: 
                skin_json = skin_data

            if skin_json: 
                await self.send(c, embed=self.skin_embed(skin_json)) 
        else: 
            await self.send(c, content=f"Can't fetch skins. Most likely the game is down and you'll need to wait until it's fixed. ") 
    
    def get_map_string_id(self, query): 
        m = re.compile(self.MAP_REGEX).match(query)

        if m: 
            map_string_id = m.group('map_string_id') 

            return map_string_id
        
        #debug(map_id) 
    
    @command('map', definite_usages={
        ('<map_string_ID>',): "View the stats of the map with the given `<map_string_ID>` (e.g. `sushuimap_v1`)", 
        ('<map_link>',): "Like above, but using the Mapmaker link of the map instead of the name (e.g. `https://mapmaker.deeeep.io/map/ffa_morty`)"
    }) 
    async def check_map(self, c, m, map_query): 
        map_string_id = self.get_map_string_id(map_query) 

        if map_string_id: 
            map_string_id = self.MAP_URL_ADDITION + map_string_id
            
            map_url = self.MAP_URL_TEMPLATE.format(map_string_id) 

            map_json = self.async_get(map_url)[0] 

            if map_json: 
                await self.send(c, embed=self.map_embed(map_json)) 
            else: 
                await self.send(c, content=f"That's not a valid map. ", reference=m) 
        else: 
            return True
    
    @command('fakerev', definite_usages={
        (): 'Not even Fede knows of the mysterious function of this command...', 
    }, public=False) 
    @requires_owner
    async def fake_review(self, c, m): 
        await self.check_review(c, self.fake_check) 
    
    @command('rev', definite_usages={
        (): 'Not even Fede knows of the mysterious function of this command...', 
    }, public=False) 
    @requires_owner
    async def real_review(self, c, m): 
        rev_channel = self.rev_channel() 

        if rev_channel: 
            await self.check_review(rev_channel, self.real_check, silent_fail=True) 
        else: 
            await self.send(c, content='Not set', reference=m) 
    
    async def link_help(self, c, m): 
        await self.send(c, content=f'Click here for instructions on how to link your account. <{self.LINK_HELP_IMG}>', reference=m) 
    
    def get_acc_id(self, query): 
        acc_id = None

        if not query.isnumeric(): 
            m = re.compile(self.PFP_REGEX).match(query)

            if m: 
                acc_id = m.group('acc_id') 
        else: 
            acc_id = query
        
        return acc_id
    
    async def link_dep_acc(self, c, m, query): 
        if query != self.LINK_SENTINEL: 
            acc_id = self.get_acc_id(query) 
            
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
                else: 
                    return True
            else: 
                return True
        else: 
            self.links_table.delete(user_id=m.author.id) 

            await self.send(c, content='Unlinked your account. ') 
    
    @command('link', definite_usages={
        (): 'View help on linking accounts', 
        ('<account_ID>',): 'Link Deeeep.io account with ID `<account_ID>` to your account', 
        ('<account_profile_pic_URL>',): "Like above, but with the URL of the account's profile picture", 
        (LINK_SENTINEL,): 'Unlink your account', 
    }) 
    async def link(self, c, m, query=None): 
        if query: 
            return await self.link_dep_acc(c, m, query) 
        else: 
            await self.link_help(c, m) 
    
    @command('statstest', definite_usages={
        ('<account_ID>',): 'View Deeeep.io account with ID `<account_ID>`', 
        ('<account_profile_pic_URL>',): "Like above, but with the URL of the account's profile picture", 
    }, public=False) 
    @requires_owner
    async def cheat_stats(self, c, m, query): 
        acc_id = self.get_acc_id(query) 
        
        if acc_id: 
            await self.send(c, embed=self.acc_embed(acc_id)) 
        else: 
            return True
    
    @command('prefix', definite_usages={
        ('<prefix>',): "Set the server-wide prefix for this bot to `<prefix>`", 
        (PREFIX_SENTINEL,): f'Reset the server prefix to the default, `{DEFAULT_PREFIX}`', 
    }) 
    @requires_perms(req_one=('manage_messages', 'manage_roles')) 
    async def set_prefix(self, c, m, prefix): 
        if prefix == self.PREFIX_SENTINEL: 
            self.prefixes_table.delete(guild_id=c.guild.id) 

            await self.send(c, content=f'Reset to default prefix `{self.DEFAULT_PREFIX}`') 
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
    
    @command('revc', definite_usages={
        (): "Perform actions", 
        (REV_CHANNEL_SENTINEL,): 'Perform different actions', 
    }, public=False) 
    @requires_owner
    async def set_rev_channel(self, c, m, flag=None): 
        if flag == self.REV_CHANNEL_SENTINEL: 
            self.rev_data_table.delete(key=self.REV_CHANNEL_KEY) 

            await self.send(c, content="Channel removed as the logging channel.") 
        elif flag is None: 
            data = {
                'key': self.REV_CHANNEL_KEY, 
                'channel_id': c.id, 
            } 

            self.rev_data_table.upsert(data, ['key'], ensure=True) 

            await self.send(c, content=f'Set this channel as the logging channel for skin review.') 
        else: 
            return True

    @command('revi', definite_usages={
        ('<i>',): 'Does something', 
    }, public=False) 
    @requires_owner
    async def set_rev_interval(self, c, m, interval): 
        if interval.isnumeric(): 
            seconds = int(interval) 

            data = {
                'key': self.REV_INTERVAL_KEY, 
                'interval': seconds, 
            } 

            self.rev_data_table.upsert(data, ['key'], ensure=True) 

            await self.send(c, content=f'Set interval to {seconds} seconds. ') 
        else: 
            return True
    
    @command('reskins', definite_usages={
        (): 'Get a list of all pending reskins in Creators Center', 
    }) 
    @requires_sb_channel
    async def display_reskins(self, c, m): 
        await self.send(c, embed=self.reskins_embed()) 
    
    @command('shutdown', definite_usages={
        (): "Turn off the bot", 
    }, public=False) 
    @requires_owner
    async def shut_down(self, c, m): 
        await self.send(c, content='shutting down') 

        self.logging_out = True
    
    @command('help', definite_usages={
        (): 'Get a list of all commands', 
        ('<command>',): 'Get help on `<command>`', 
    }) 
    async def send_help(self, c, m, command_name=None): 
        if command_name: 
            comm = commands.Command.get_command(command_name)  

            if comm: 
                usage_str = comm.usages_str(self, c, m) 

                await self.send(c, content=f'''How to use the `{command_name}` command: 

{usage_str}''') 
            else: 
                prefix = self.prefix(c) 

                await self.send(c, content=f"That's not a valid command name. Type `{prefix}{self.send_help.name}` for a list of commands. ", reference=m) 
        else: 
            com_list_str = tools.format_iterable(commands.Command.all_commands(public_only=True), formatter='`{}`') 
            prefix = self.prefix(c) 

            await self.send(c, content=f'''All commands for this bot: {com_list_str}. 
Type `{prefix}{self.send_help.name} <command>` for help on a specified `<command>`''') 
    
    @command('info', definite_usages={
        (): 'Display info about this bot', 
    }) 
    async def send_info(self, c, m): 
        await self.send(c, embed=await self.self_embed(c)) 
    
    @task
    async def execute(self, comm, c, m, *args): 
        message_str = f'''Message content: {m.content}
Message author: {m.author}
Message channel: {c}
Message guild: {m.guild}''' 

        debug(message_str)  

        permissions = c.permissions_for(c.guild.me) 

        if permissions.send_messages: 
            await comm.attempt_run(self, c, m, *args) 
        else: 
            await self.send(m.author, f"I can't send messages in {c.mention}! ")
    
    async def handle_command(self, m, c, prefix, words): 
        command, *args = words
        command = command[len(prefix):] 

        comm = commands.Command.get_command(command) 

        if comm: 
            await self.execute(comm, c, m, *args) 
    
    async def on_message(self, msg): 
        c = msg.channel

        if hasattr(c, 'guild'): 
            prefix = self.prefix(c) 
            words = msg.content.split(' ') 

            if len(words) >= 1 and words[0].startswith(prefix): 
                await self.handle_command(msg, c, prefix, words) 