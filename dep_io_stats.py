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

import logs
from logs import debug
import tools
import commands
from chars import c
import trimmed_embed
import report

class Dep_io_Stats(discord.Client): 
    DEFAULT_PREFIX = ',' 
    MAX_PREFIX = 5
    PREFIX_SENTINEL = 'none' 

    LINK_SENTINEL = 'remove' 
    LINK_HELP_IMG = 'https://cdn.discordapp.com/attachments/493952969277046787/796576600413175819/linking_instructions.png' 
    INVITE_LINK = 'https://discord.com/oauth2/authorize?client_id=796151711571116042&permissions=347136&scope=bot' 

    DATE_FORMAT = '%B %d, %Y' 

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

    SKIN_ASSET_URL_TEMPLATE = 'https://deeeep.io/assets/skins/{}' 
    CUSTOM_SKIN_ASSET_URL_ADDITION = 'custom/' 
    SKIN_URL_TEMPLATE = 'https://api.deeeep.io/skins/{}' 

    SKIN_REVIEW_LIST_URL = 'https://api.deeeep.io/skins/pending?t=review' 
    STATS_UNBALANCE_BLACKLIST = ['OT', 'TT', 'PT', 'ST', 'SS', 'HA'] 

    MAP_URL_ADDITION = 's/' 
    MAPMAKER_URL_TEMPLATE = 'https://mapmaker.deeeep.io/map/{}' 
    MAP_REGEX = '\A(?:(?:https?://)?(?:www.)?mapmaker.deeeep.io/map/)?(?P<map_string_id>[0-9_A-Za-z]+)\Z' 

    def __init__(self, logs_file_name, storage_file_name, email, password): 
        self.email = email
        self.password = password

        self.db = dataset.connect(storage_file_name) 
        self.links_table = self.db.get_table('account_links') 
        self.prefixes_table = self.db.get_table('prefixes') 

        self.logs_file = open(logs_file_name, mode='w+', encoding='utf-8') 

        handler = logging.StreamHandler(self.logs_file) 

        logs.logger.addHandler(handler) 

        #self.levels_file = open(levels_file_name, mode='r') 

        self.tasks = 0
        self.logging_out = False

        self.readied = False
        self.token = None

        super().__init__() 
    
    def prefix(self, c): 
        p = self.prefixes_table.find_one(guild_id=c.guild.id) 
        
        if p: 
            return p['prefix'] 
        else: 
            return self.DEFAULT_PREFIX
    
    async def send(self, c, *args, **kwargs): 
        try: 
            return await c.send(*args, **kwargs) 
        except discord.errors.Forbidden: 
            debug('that was illegal') 
    
    async def logout(self): 
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
    
    async def default_args_check(self, c, m, *args): 
        return True

    def command(name, definite_usages={}, indefinite_usages={}): 
        def decorator(func): 
            command_obj = commands.Command(func, name, definite_usages, indefinite_usages) 

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
        stat_changes = skin['attributes'] 

        if stat_changes: 
            counted_changes = [] 

            split_changes = stat_changes.split(';') 

            for change_str in split_changes: 
                stat, value = change_str.split('=') 

                counted_changes.append((stat, float(value))) 
    
    def reject_reasons(self, skin): 
        reasons = [] 

        debug(skin) 

        if not skin['reddit_link']: 
            reasons.append('lack of Reddit link') 
        
        return reasons
    
    def inspect_skins(self, review_list): 
        rejected = [] 
        reasons = [] 

        for skin in review_list: 
            rej_reasons = self.reject_reasons(skin) 

            if rej_reasons: 
                rejected.append(skin) 
                reasons.append(rej_reasons) 
        
        debug(rejected) 
        debug(reasons) 
        
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
    
    async def check_review(self, c): 
        r = report.Report(self, c) 

        self.get_review_token() 

        if self.token: 
            list_request = grequests.request('GET', self.SKIN_REVIEW_LIST_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            list_json = self.async_get(list_request)[0] 

            if list_json: 
                rejected, reasons = self.inspect_skins(list_json) 

                r.add(f'**{len(rejected)} out of {len(list_json)} failed**') 

                if rejected: 
                    r.add('') 

                    rejection_strs = [] 

                    for skin, reason in zip(rejected, reasons): 
                        reason_str = tools.format_iterable(reason, formatter='`{}`') 

                        skin_id = skin['id'] 

                        skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

                        rejection_str = f"**{skin['name']}** (link {skin_url}) has the following issues: {reason_str}" 

                        r.add(rejection_str) 
            elif list_json is None: 
                r.add('Error fetching skins.') 
            else: 
                r.add('There are no skins to check.') 
        else: 
            r.add('Error logging in to perform this task. ') 
        
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

        asset_url = self.SKIN_ASSET_URL_TEMPLATE.format(asset_name) + '?' + str(time.time()) #time part is to force a refresh

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

            creator = f'{user_name} (@{user_username})' 
            creator_inline = False
        else: 
            creator = designer_id
            creator_inline = True
        
        embed.add_field(name=f"Creator {c['palette']}", value=creator, inline=creator_inline) 

        embed.set_footer(text=f"ID: {ID}") 

        return embed
    
    def acc_embed(self, acc_id): 
        acc, contribs, roles = self.get_all_acc_data(acc_id) 

        color = discord.Color.random() 

        if acc: 
            title = f"{acc['name']} (@{acc['username']})"  

            desc = acc['description'] 
            
            pfp_url = self.PFP_URL_TEMPLATE.format(acc['picture']) + '?' + str(time.time()) #time part is to force a refresh

            #debug(pfp_url) 
            
            kills = acc['kill_count'] 
            max_score = acc['highest_score'] 
            coins = acc['coins'] 

            #debug(hex(color)) 

            embed = trimmed_embed.TrimmedEmbed(title=title, type='rich', description=desc, color=color) 

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

        embed.add_field(name=f"Creator {c['carpenter']}", value=creator_str, inline=False) 

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
    
    async def on_ready(self): 
        self.readied = True
        
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
    
    @command('rev', definite_usages={
        (): 'Not even Fede knows of the mysterious function of this command...', 
    }) 
    @requires_owner
    async def fake_review(self, c, m): 
        await self.check_review(c) 
    
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
    }) 
    @requires_owner
    async def cheat_stats(self, c, m, query): 
        acc_id = self.get_acc_id(query) 
        
        if acc_id: 
            await self.send(c, embed=self.acc_embed(acc_id)) 
        else: 
            return True
    
    @command('prefix', definite_usages={
        ('<prefix>',): "Set the server-wide prefix for this bot to `<prefix>`", 
        (PREFIX_SENTINEL,): 'Reset the server prefix to default', 
    }) 
    @requires_perms(req_one=('manage_messages', 'manage_roles')) 
    async def set_prefix(self, c, m, prefix): 
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
    
    @command('shutdown', definite_usages={
        (): "Turn off the bot", 
    }) 
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
            com_list_str = tools.format_iterable(commands.Command.all_commands(), formatter='`{}`') 
            prefix = self.prefix(c) 

            await self.send(c, content=f'''All commands for this bot: {com_list_str}. 
Type `{prefix}{self.send_help.name} <command>` for help on a specified `<command>`''') 

    @command('invite', definite_usages={
        (): 'Display the invite link for the bot', 
    }) 
    async def send_invite(self, c, m): 
        await self.send(c, content=f'Invite link is <{self.INVITE_LINK}>. ', reference=m)
    
    @task
    async def execute(self, comm, c, m, *args): 
        await comm.attempt_run(self, c, m, *args) 
    
    async def handle_command(self, m, c, prefix, words): 
        message_str = f'''Message content: {m.content}
Message author: {m.author}
Message channel: {c}
Message guild: {m.guild}''' 

        debug(message_str) 

        permissions = c.permissions_for(c.guild.me) 
        
        if permissions.send_messages: 
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