from typing import Type
from urllib import parse
import grequests
import discord
import dataset
import asyncio
import sys
import time
import random
import re
import dateutil.parser as parser
import json
import logging
import math
import json
import enum

import logs
from logs import debug
import tools
import commands
import chars 
import embed_utils
import reports
import habitat
import ds_constants
import credman
import discord.ui
import ui
import slash_util
from discord.ext import commands

class DS(ds_constants.DS_Constants, commands.Bot): 
    def __init__(self, logs_file_name: str, storage_file_name: str, animals_file_name: str, email: str, password: str): 
        self.email = email
        self.password = password

        self.active_token_requests = 0
        self.token = None

        # self.credman = credman.CredMan(self, self.credentials) 

        self.db = dataset.connect(storage_file_name) 
        self.links_table = self.db.get_table('account_links') 
        self.prefixes_table = self.db.get_table('prefixes') 
        self.rev_data_table = self.db.get_table('rev_data') 
        self.blacklists_table = self.db.get_table('blacklists') 
        self.sb_channels_table = self.db.get_table('sb_channels') 
        self.mains_table = self.db.get_table('main_accounts')

        self.logs_file = open(logs_file_name, mode='w+', encoding='utf-8') 
        self.animals_file_name = animals_file_name

        self.ANIMAL_FILTERS = {} 

        self.animal_stats = []

        self.set_animal_stats() 

        handler = logging.StreamHandler(self.logs_file) 

        logs.logger.addHandler(handler) 

        #self.levels_file = open(levels_file_name, mode='r') 

        self.tasks = 0
        self.logging_out = False

        self.readied = False

        self.auto_rev_process = None
        self.ALL_FILTERS = {}

        super().__init__(',', intents=discord.Intents(), activity=discord.Game(name='starting up'), status=discord.Status.dnd) 
    
    def get_animal_stats(self) -> list[dict]: 
        with open(self.animals_file_name, mode='r') as file: 
            return json.load(file) 
    
    @staticmethod
    def animal_check(target_id): 
        def check(self, skin): 
            animal = skin['fish_level'] 

            return animal == target_id
        
        return check
    
    def set_animal_stats(self):
        self.animal_stats = self.get_animal_stats()

        print('set animal stats') 
    
    def find_animal_by_id(self, animal_id: int): 
        stats = self.animal_stats

        return stats[animal_id]
    
    def find_animal_by_name(self, animal_name: str):
        stats = self.animal_stats

        for animal in stats:
            if animal['name'] == animal_name.lower():
                return animal
        
        return None
    
    def prefix(self, c): 
        p = self.prefixes_table.find_one(guild_id=c.guild.id) 
        
        if p: 
            return p['prefix'] 
        else: 
            return self.DEFAULT_PREFIX
    
    def blacklisted(self, guild_id, blacklist_type, target): 
        if guild_id:
            b_entry = self.blacklists_table.find_one(guild_id=guild_id, type=blacklist_type, target=target) 

            return b_entry
        else:
            return False
    
    def rev_channel(self): 
        c_entry = self.rev_data_table.find_one(key=self.REV_CHANNEL_KEY) 

        if c_entry: 
            c_id = c_entry['channel_id'] 

            c = self.get_channel(c_id) 

            return c
    
    def is_sb_channel(self, channel_id): 
        if channel_id:
            c_entry = self.sb_channels_table.find_one(channel_id=channel_id) 

            return c_entry
        else:
            return False
    
    async def send(self, c, *args, **kwargs): 
        try: 
            return await c.send(*args, **kwargs) 
        except discord.errors.Forbidden: 
            debug('that was illegal') 
    
    async def logout(self): 
        try:
            if self.auto_rev_process: 
                self.auto_rev_process.cancel() 
            
            '''
            self.tree.clear_commands(guild=discord.Object(273213133731135500))
            await self.tree.sync(guild=discord.Object(273213133731135500))
            '''

            await ui.TrackedView.close_all()
            
            await self.change_presence(status=discord.Status.offline)
            
            self.logs_file.close() 
            #self.levels_file.close()
        finally:
            await super().close() 
    
    '''
    def get_token(self, index): 
        return self.credman.tokens[index] 
    '''
    
    def fetch_token(self):
        if not self.token:
            debug(self.email)
            debug(self.password)

            request = grequests.request('POST', self.LOGIN_URL, data={
                'email': self.email, 
                'password': self.password, 
            }, headers={
                'origin': 'https://creators.deeeep.io'
            })

            result = self.async_get(request)[0]

            if result:
                token = result['token']

                self.token = token
                
                debug(f'Token fetched: {self.token}')
            else:
                debug('Error fetching token')
        else:
            debug(f'Cached token: {self.token}')
    
    def del_token(self):
        former_token = self.token

        self.token = None

        debug(f'Forgor token {former_token}')
    
    def borrow_token(self):
        class TokenManager:
            def __init__(self, client: DS):
                self.client = client
            
            def __enter__(self):
                self.client.active_token_requests += 1

                self.client.fetch_token()

                return self.client.token
            
            def __exit__(self, exc_type, exc_value, traceback):
                self.client.active_token_requests -= 1

                if not self.client.active_token_requests:
                    self.client.del_token()
        
        return TokenManager(self)

    '''
    def log_out_acc(self): 
        self.credman.clear_tokens() 

        logout_request = grequests.request('GET', self.LOGOUT_URL, headers={
            'Authorization': f'Bearer {self.token}', 
        }) 

        result = self.async_get(logout_request)[0] 

        debug(f'logout of Deeeep.io account status: {result}')
    ''' 
    
    async def first_task_start(self): 
        self.set_animal_stats() 
    
    async def last_task_end(self): 
        debug('f') 

        self.log_out_acc() 

        logs.trim_file(self.logs_file, self.MAX_LOG) 

        if self.logging_out: 
            await self.logout() 
    
    async def edit_tasks(self, amount): 
        try: 
            if self.tasks == 0: 
                await self.first_task_start() 
            
            self.tasks += amount

            debug(f'now running {self.tasks} tasks') 

            debug('g') 

            if self.tasks == 0: 
                await self.last_task_end() 
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
                await self.send(c, content='no u (owner-only command) ') 
        
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
                    
                    await self.send(c, content=f'You need {req_str} to use this command') 
            
            return req_perms_func
        
        return decorator
    
    def requires_sb_channel(func): 
        async def req_channel_func(self, c, m, *args): 
            if self.is_sb_channel(c.id): 
                return await func(self, c, m, *args) 
            else: 
                await self.send(c, content="This command is reserved for Skin Board channels.") 
        
        return req_channel_func
    
    async def default_args_check(self, c, m, *args): 
        return True
    
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
            map_displays = [f'[{name}]({self.MAPMAKER_URL_TEMPLATE.format(name)})' for name in map_contribs] 

            #debug(map_displays) 

            map_str = tools.format_iterable(map_displays) 

            contribs.append(f'**Maps**: {map_str}') 
        
        skin_contribs = self.get_skin_contribs(skins_list, acc_id) 

        if skin_contribs: 
            skin_str = tools.format_iterable(skin_contribs) 

            contribs.append(f'**Skins**: {skin_str}') 
        
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
        skins_list_url = self.APPROVED_SKINS_LIST_URL

        self.fetch_tokens(1) 

        acc_json, server_list, skins_list = self.async_get(acc_url, server_list_url, skins_list_url) 

        map_list = self.get_map_list(server_list) 
        map_urls = self.get_map_urls(*map_list) 
        
        round_2_urls = map_urls.copy() 

        members_list = None

        token = self.get_token(0) 

        if token: 
            members_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {token}', 
            }) 

            round_2_urls.append(members_request) 

            *map_jsons, members_list = self.async_get(*round_2_urls) 

            #debug(members_list) 
        else: 
            map_jsons = self.async_get(*round_2_urls) 

        contribs = self.get_contribs(acc_json, acc_id, map_jsons, skins_list) 
        roles = self.get_roles(acc_json, acc_id, members_list) 

        return acc_json, contribs, roles
    
    def get_profile_by_username(self, username): 
        username = self.get_true_username(username)

        debug(username)

        acc_url = self.PROFILE_TEMPLATE.format(username)

        acc_json = self.async_get(acc_url)[0]

        if acc_json:
            acc_id = acc_json['id']

            socials_url = self.SOCIALS_URL_TEMPLATE.format(acc_id)
            rankings_url = self.RANKINGS_TEMPLATE.format(acc_id)
            skin_contribs_url = self.SKIN_CONTRIBS_TEMPLATE.format(acc_id)
            map_creations_url = self.MAP_CONTRIBS_TEMPLATE.format(acc_id)

            socials, rankings, skin_contribs, map_creations = self.async_get(socials_url, rankings_url, skin_contribs_url, map_creations_url)
        else:
            socials = rankings = skin_contribs = map_creations = ()

        return acc_json, socials, rankings, skin_contribs, map_creations
    
    def get_profile_by_id(self, id):
        acc_url = self.DATA_URL_TEMPLATE.format(id)
        social_url = self.SOCIALS_URL_TEMPLATE.format(id)
        rankings_url = self.RANKINGS_TEMPLATE.format(id)
        skin_contribs_url = self.SKIN_CONTRIBS_TEMPLATE.format(id)
        map_creations_url = self.MAP_CONTRIBS_TEMPLATE.format(id)

        return self.async_get(acc_url, social_url, rankings_url, skin_contribs_url, map_creations_url)
    
    @staticmethod
    def compile_ids_from_motions(motions_list, motion_filter=lambda motion: True): 
        motioned_ids = {} 

        for motion in motions_list: 
            motion_type = motion['target_type'] 

            if motion_type == 'skin' and motion_filter(motion): 
                target_id = motion['target_id'] 
                target_version = motion['target_version'] 

                if target_id in motioned_ids: 
                    motioned_ids[target_id].append(target_version) 
                else: 
                    motioned_ids[target_id] = [target_version] 
        
        return motioned_ids
    
    def filter_skins(self, skins_list, *filters) -> list[dict]: 
        passed_skins = []

        for skin in skins_list: 
            for skin_filter in filters:
                # debug(skin_filter)

                if not skin_filter(self, skin): 
                    break
            else: 
                passed_skins.append(skin) 
        
        return passed_skins
        
    def get_pending_skins(self, *filters): 
        self.fetch_tokens(1) 

        pending_motions = rejected_motions = None

        token = self.get_token(0) 
        
        if token: 
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {token}', 
            }) 
            rejected_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {token}', 
            }) 

            pending_list, pending_motions, rejected_motions = self.async_get(self.PENDING_SKINS_LIST_URL, pending_motions_request, rejected_motions_request) 
        else: 
            pending_list = self.async_get(self.PENDING_SKINS_LIST_URL)[0] 

        unnoticed_pending = None
        upcoming_pending = None
        motioned_pending = None
        rejected_pending = None
        trimmed_string = None

        if pending_list is not None: 
            unnoticed_pending = [] 
            upcoming_pending = [] 

            pending_ids = {} 
            rejected_ids = {} 

            if pending_motions is not None: 
                motioned_pending = [] 
                pending_ids = self.compile_ids_from_motions(pending_motions) 
            
            if rejected_motions is not None: 
                rejected_pending = [] 
                rejected_ids = self.compile_ids_from_motions(rejected_motions, motion_filter=lambda motion: motion['rejected']) 
            
            filtered_skins, trimmed_string = self.filter_skins(pending_list, *filters) 

            for pending in filtered_skins: 
                unnoticed = True

                upcoming = pending['upcoming'] 

                if upcoming: 
                    upcoming_pending.append(pending) 

                    unnoticed = False
                
                skin_id = pending['id'] 
                skin_version = pending['version'] 

                if skin_id in pending_ids: 
                    motioned_versions = pending_ids[skin_id] 

                    if skin_version in motioned_versions: 
                        motioned_pending.append(pending)  

                        unnoticed = False
                
                if skin_id in rejected_ids: 
                    motioned_versions = rejected_ids[skin_id] 

                    if skin_version in motioned_versions: 
                        rejected_pending.append(pending)  

                        unnoticed = False
                
                if unnoticed: 
                    unnoticed_pending.append(pending) 
        
        return unnoticed_pending, upcoming_pending, motioned_pending, rejected_pending, trimmed_string
    
    def skins_from_list(self, list_name: str) -> list[dict]:
        need_token = False

        if list_name == 'approved': 
            url = self.APPROVED_SKINS_LIST_URL

        elif list_name == 'pending': 
            url = self.PENDING_SKINS_LIST_URL
        
        elif list_name == 'upcoming':
            url = self.UPCOMING_LIST_URL
            need_token = True

        if need_token:
            with self.borrow_token() as token:
                req = grequests.request('GET', url, headers={
                    'authorization': f'Bearer {token}', 
                })

                return self.async_get(req)[0] 
        else:
            req = url

            return self.async_get(req)[0] 
    
    def filtered_skins_from_list(self, list_name: str, *filters):
        skins = self.skins_from_list(list_name)

        if skins is not None: 
            filtered_skins = self.filter_skins(skins, *filters) 

            return filtered_skins
    
    def suggestions_book(self, interaction: discord.Interaction, suggestions: list[dict], search_type: str, titles: tuple[str], 
    formatters: tuple[str], page_buttons_func):
        color = discord.Color.random()
        description = f'Did you mean one of these?'
        empty_description = "Never mind I have no suggestions. Sorry m8."

        embed_template = embed_utils.TrimmedEmbed(title=f"Possible {search_type} results", color=color, description=description)

        return self.generic_compilation_embeds(interaction, embed_template, search_type, suggestions, titles, formatters,
        empty_description=empty_description, artificial_limit=ui.CallbackSelect.MAX_OPTIONS, page_buttons_func=page_buttons_func)
    
    async def search_with_suggestions(self, interaction: discord.Interaction, search_type: str, titles: tuple[str], 
    formatters: tuple[str],
    search_list: list[dict], map_func, query: str, page_buttons_func, no_duplicates=False):
        perfect_matches = []
        suggestions = [] 

        for item in search_list: 
            item_name = map_func(item) 

            lowered_name = item_name.lower() 
            lowered_query = query.lower() 

            #debug(lowered_name) 
            #debug(lowered_query) 

            if lowered_name == lowered_query: 
                perfect_matches.append(item)

                if no_duplicates:
                    break
            elif not perfect_matches and (lowered_query in lowered_name or lowered_name in lowered_query): 
                suggestions.append(item)

        final_list = perfect_matches or suggestions 
        
        if len(final_list) == 1:
            return final_list
        else:
            suggestions_book = self.suggestions_book(interaction, final_list, search_type, titles, formatters, page_buttons_func)

            await suggestions_book.send_first()
    
    class VoteAction:
        def __init__(self, motion: dict, vote_action: str, motion_type: str, target_str: str):
            self.motion = motion
            self.vote_action = vote_action
            self.motion_type = motion_type
            self.target_str = target_str

            self.emoji = '\\' + (chars.check if vote_action == 'approve' else chars.x)
    
    @classmethod
    def count_votes(cls, total_motions) -> dict[list[VoteAction]]: 
        mapping = {} 

        for motion in total_motions: 
            votes = motion['votes'] 
            motion_type = motion['type']
            target = motion['target']
            target_type = motion['target_type']

            for vote in votes: 
                user_id = vote['user_id'] 
                vote_action = vote['action'] 

                if user_id not in mapping: 
                    mapping[user_id] = [] 

                if target_type == 'user':
                    target_str = target['username']
                elif target_type == 'skin':
                    target_str = f"{target['name']} (v{target['version']})"
                else:
                    target_str = 'N/A'
                
                action_obj = cls.VoteAction(motion, vote_action, motion_type, target_str)
                
                mapping[user_id].append(action_obj)
        
        return mapping
    
    @staticmethod
    def participation_str_list(r, member_strs): 
        for member_str in member_strs: 
            r.add(f'• {member_str}') 
    
    def build_participation_section(self, r, member_strs): 
        if member_strs: 
            self.participation_str_list(r, member_strs) 
        else: 
            r.add('There are no members in this category.')
    
    def participation_embed_template(self):
        color = discord.Color.random()

        return embed_utils.TrimmedEmbed(title='Motion voting summary', description='A summary of how many motions Artistry Guild \
members have voted on', color=color)

    def participant_embed(self, interaction: discord.Interaction, user: dict, votes: list[VoteAction]):
        base = self.base_profile_embed(user, specific_page='Motions voted by', big_image=False)

        titles = f"Motion type {chars.folder}", f"Motion target {chars.target}", f"Vote {chars.ballot_box}"
        formatters = "{.motion_type}", "{.target_str}", "{.emoji}"
            
        comp = self.generic_compilation_embeds(interaction, base, 'motions', votes, titles, formatters)

        return comp

    async def display_participant_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, participants: list[dict]):
        first_value = menu.values[0]

        index = int(first_value)

        part_dict = participants[index]

        participant = part_dict['user']
        votes = part_dict['votes']

        await menu_interaction.response.defer(thinking=True)

        book = self.participant_embed(menu_interaction, participant, votes)

        await book.send_first()
    
    def participant_page_menu(self, message_interaction: discord.Interaction, participants: list[dict]) \
        -> tuple[ui.CallbackSelect]:
        options = [ui.TruncatedSelectOption(label=participants[index]['username'], 
        description="", value=index) for index in range(len(participants))]

        menu = ui.CallbackSelect(self.display_participant_from_menu, message_interaction, participants.copy(), options=options,
        placeholder='Choose a member')

        return (menu,)
    
    def build_participation_book(self, interaction: discord.Interaction, count_mapping: dict[int, list[VoteAction]], 
    members_list: list[int]): 
        member_dicts = []

        for member in members_list: 
            username = member['username'] 
            member_id = member['id'] 

            approves = 0
            rejects = 0
            votes = ()

            if member_id in count_mapping: 
                votes = count_mapping[member_id] 

                for vote in votes:
                    vote_action = vote.vote_action

                    if vote_action == 'approve':
                        approves += 1
                    elif vote_action == 'reject':
                        rejects += 1
                    else:
                        raise RuntimeError(f'Vote on {vote.motion} by {member_id} that is neither an approve or a reject...?')
            
            member_dict = {
                'user': member,
                'username': username,
                'approves': approves,
                'rejects': rejects,
                'votes': votes,
            }

            member_dicts.append(member_dict)

        template = self.participation_embed_template()

        titles = f"Member {chars.crab}", f"Approvals {chars.check}", f"Rejections {chars.x}"
        formatters = "{[username]}", "{[approves]}", "{[rejects]}"
            
        comp = self.generic_compilation_embeds(interaction, template, 'members', member_dicts, titles, formatters,
        artificial_limit=ui.CallbackSelect.MAX_OPTIONS, page_buttons_func=self.participant_page_menu)
        
        return comp
    
    async def send_motion_participation(self, interaction: discord.Interaction): 
        await interaction.response.defer()

        with self.borrow_token():
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            recent_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            pending_motions, recent_motions, members_list = self.async_get(pending_motions_request, recent_motions_request, list_request) 

        if members_list: # None in jsons indicates at least one request failed
            total_motions = (pending_motions or ()) + (recent_motions or ()) 

            counts = self.count_votes(total_motions) 

            book = self.build_participation_book(interaction, counts, members_list)

            await book.send_first()
        else:
            await interaction.followup.send(content='There was an error fetching members.')
    
    def compile_voter_map(self, existing_map: dict, voters: list[dict]) -> dict[int, str]:
        requests = (self.PROFILE_TEMPLATE.format(voter['user_id']) for voter in voters if voter['user_id'] not in existing_map)

        results = self.async_get(*requests)

        if results:
            for user in results:
                user_id = user['id']

                existing_map[user_id] = user['username']
    
    def fetch_sb_members(self):
        with self.borrow_token():
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            })

            return self.async_get(list_request)[0]
    
    def motion_title_and_thumb(self, motion):
        target = motion['target']
        target_type = motion['target_type']
        action_type = motion['type']
        data = motion['data']

        if target_type == 'skin':
            name = target['name']
            version = target['version']
            asset = target['asset']

            title = f'{action_type} {name} (v{version})'

            if asset[0].isnumeric(): 
                template = self.CUSTOM_SKIN_ASSET_URL_TEMPLATE
            else:
                template = self.SKIN_ASSET_URL_TEMPLATE

            thumbnail = template.format(asset)
        elif target_type == 'user':
            pfp = target['picture']

            if not pfp: 
                pfp = self.DEFAULT_BETA_PFP
            else: 
                pfp = self.PFP_URL_TEMPLATE.format(pfp)
            
            thumbnail = tools.salt_url(pfp)

            if data == 1:
                role = 'member'
            else:
                role = 'manager'
            
            if action_type == 'addrole':
                action = f'add {role} role'
            else:
                action = f'remove {role} role'
            
            username = target['username']

            title = f'{action} for {username}'
        else:
            title = 'release upcoming skins'
            thumbnail = None
        
        debug(thumbnail)
        
        return title, thumbnail
    
    def motion_embed(self, motion: dict, members: list[dict]):
        title, thumbnail = self.motion_title_and_thumb(motion)

        title = f'Motion to {title}'

        color = discord.Color.random()

        embed = embed_utils.TrimmedEmbed(title=title, color=color)

        embed.set_thumbnail(url=thumbnail)
        
        user = motion['user']
        
        user_username = user['username'] 
        user_pfp = user['picture'] 
        user_page = self.PROFILE_PAGE_TEMPLATE.format(parse.quote(user_username))

        creator = user_username

        if not user_pfp: 
            user_pfp = self.DEFAULT_BETA_PFP
        else: 
            user_pfp = self.PFP_URL_TEMPLATE.format(user_pfp)
        
        pfp_url = tools.salt_url(user_pfp)

        embed.set_author(name=creator, icon_url=pfp_url, url=user_page) 

        when_created = motion['created_at']
        when_updated = motion['updated_at']

        date_created = parser.isoparse(when_created) 
        date_updated = parser.isoparse(when_updated)

        embed.add_field(name=f"Date created {chars.tools}", value=f'{tools.timestamp(date_created)}')
        embed.add_field(name=f'Date updated {chars.wrench}', value=f'{tools.timestamp(date_updated)}')

        num_upvotes = motion['approve_votes']
        num_downvotes = motion['reject_votes']
        
        total_votes = num_upvotes + num_downvotes
        
        upvote_ratio = num_upvotes * 100 / total_votes

        if members:
            turnout = total_votes * 100 / len(members)
            turnout_str = turnout
        else:
            turnout_str = 'unknown'

        embed.add_field(name=f'Vote stats {chars.ballot_box}', value=f'{upvote_ratio}% upvoted, {turnout_str}% voter turnout',
        inline=False)

        approved = motion['approved']
        rejected = motion['rejected']

        if approved:
            decision = 'approved'
            dec_emoji = chars.check
        elif rejected:
            decision = 'rejected'
            dec_emoji = chars.x
        else:
            decision = 'ongoing'
            dec_emoji = chars.question_mark
        
        embed.add_field(name=f'Status {dec_emoji}', value=decision)

        upvoted = []
        downvoted = []

        voters = motion['votes']

        voter_map = {user['id']: user['username'] for user in members} if members else {}

        self.compile_voter_map(voter_map, voters)

        for voter in voters:
            vote = voter['action']
            voter_id = voter['user_id']

            voter_display = voter_map[voter_id] if voter_id in voter_map else voter_id

            if vote == 'approve':
                upvoted.append(voter_display)
            else:
                downvoted.append(voter_display)
        
        upvotes_list = tools.format_iterable(upvoted, sep='\n') or 'No approvals'
        downvotes_list = tools.format_iterable(downvoted, sep='\n') or 'No rejections'

        embed.add_field(name=f'{num_upvotes} approvals {chars.check}', value=upvotes_list)
        embed.add_field(name=f'{num_downvotes} rejections {chars.x}', value=downvotes_list)

        motion_id = motion['id']
        target_id = motion['target_id']

        embed.set_footer(text=f'''Motion ID: {motion_id}
Target ID: {target_id}''')

        return embed
    
    class MotionRepresentation:
        def __init__(self, motion: dict, title: str, upvote_ratio: float, turnout_str: str, members_list: list[dict]):
            self.motion = motion
            self.title = title
            self.upvote_ratio = upvote_ratio
            self.turnout_str = turnout_str
            self.members_list = members_list

    def motion_reprs(self, motions_list: tuple[dict], members_list: list[dict]) -> list[MotionRepresentation]:
        reprs = []

        for motion in motions_list:
            title, thumbnail = self.motion_title_and_thumb(motion)
            num_upvotes = motion['approve_votes']
            num_downvotes = motion['reject_votes']

            total_votes = num_upvotes + num_downvotes
        
            upvote_ratio = num_upvotes / total_votes

            if members_list:
                turnout = total_votes / len(members_list)
                turnout_str = f'{turnout:.0%}'
            else:
                turnout_str = 'unknown'

            reprs.append(self.MotionRepresentation(motion, title, upvote_ratio, turnout_str, members_list))
        
        return reprs
    
    async def display_motion_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, motions: list[MotionRepresentation]):
        first_value = menu.values[0]

        index = int(first_value)

        motion_obj = motions[index]

        motion = motion_obj.motion
        members_cache = motion_obj.members_list

        await menu_interaction.response.defer(thinking=True)

        embed = self.motion_embed(motion, members_cache)

        await menu_interaction.followup.send(embed=embed)
    
    def motions_page_menu(self, message_interaction: discord.Interaction, motions: list[MotionRepresentation]) \
        -> tuple[ui.CallbackSelect]:
        options = [ui.TruncatedSelectOption(label=motions[index].title, 
        description="", value=index) for index in range(len(motions))]

        menu = ui.CallbackSelect(self.display_motion_from_menu, message_interaction, motions.copy(), options=options,
        placeholder='Choose a motion')

        return (menu,)
    
    def motions_page(self, interaction: discord.Interaction, motions_list: tuple[dict], members_list: list[dict],
    active: bool) -> ui.Page:
        title = 'Pending' if active else 'Recent'
        template = embed_utils.TrimmedEmbed(title=f'{title} motions')

        motion_reprs = self.motion_reprs(motions_list, members_list)

        titles = f'Motion {chars.scroll}', f'Upvote ratio {chars.thumbsup}', f'Turnout {chars.ballot_box}'
        formatters = '{.title}', '{.upvote_ratio:.0%}', '{.turnout_str}'

        return self.generic_compilation_embeds(interaction, template, 'motions', motion_reprs, titles, formatters,
        artificial_limit=ui.CallbackSelect.MAX_OPTIONS, page_buttons_func=self.motions_page_menu)
    
    async def motions_book(self, interaction: discord.Interaction):
        await interaction.response.defer()

        with self.borrow_token():
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            recent_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            pending_motions, recent_motions, members_list = self.async_get(pending_motions_request, recent_motions_request, list_request)
        
        pending_motions = pending_motions or ()
        recent_motions = recent_motions or ()

        pending_page = self.motions_page(interaction, pending_motions, members_list, True)
        recent_page = self.motions_page(interaction, recent_motions, members_list, False)

        book = ui.IndexedBook(interaction, ('Pending motions', pending_page), ('Recent motions', recent_page))

        await book.send_first()
    
    def unbalanced_stats(self, skin): 
        broken = False
        unbalanced = False

        stat_changes = skin['attributes'] 

        if stat_changes: 
            unbalanced = True

            animal_id = skin['fish_level']
            animal = self.find_animal_by_id(animal_id)

            changes_array = self.generate_stat_changes(stat_changes, animal)

            prev_sign = None

            for change in changes_array:
                local_broken = type(change) is str or change[3]

                broken = broken or local_broken

                if not local_broken:
                    attribute, old_val, new_val, waste = change

                    if attribute not in self.STATS_UNBALANCE_BLACKLIST and old_val != new_val:
                        sign = '-' if new_val < old_val else '+'

                        if prev_sign and prev_sign != sign:
                            unbalanced = False
                        
                        prev_sign = sign
        
        unbalance_sign = prev_sign if unbalanced else None

        return broken, unbalance_sign
    
    def valid_reddit_link(self, link): 
        m = re.compile(self.REDDIT_LINK_REGEX).match(link) 

        return m
    
    def reject_reasons(self, skin, check_reddit=True): 
        reasons = [] 

        skin_name = skin['name'] 
        skin_id = skin['id'] 

        skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

        # debug(f'{skin_name}: {skin_url}') 

        if check_reddit: 
            reddit_link = skin['reddit_link']

            if not reddit_link: 
                reasons.append('missing Reddit link') 
            elif not self.valid_reddit_link(reddit_link): 
                reasons.append('invalid Reddit link') 
        
        broken, unbalance_sign = self.unbalanced_stats(skin) 

        if broken: 
            reasons.append(f'invalid/malformed stat changes') 
        
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
    
    '''
    def fetch_tokens(self, needed_num): 
        self.credman.request_tokens(needed_num)
    '''
    
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
                    'Authorization': f'Bearer {self.get_token(0)}', 
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
                
                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 
                c_str = f'{c_name} (@{c_username})' 

                embed = embed_utils.TrimmedEmbed(title=skin_name, type='rich', description=desc, url=skin_url, color=color) 

                embed.set_author(name=f'Skin {rej_type}') 

                embed.set_thumbnail(url=asset_url) 
                #embed.add_field(name=f"Image link {chars.image}", value=f'[Image]({asset_url})') 

                embed.add_field(name=f"Creator {chars.carpenter}", value=c_str, inline=False) 
                embed.add_field(name=f"Rejection reasons {chars.scroll}", value=reason_str, inline=False) 

                embed.set_footer(text=f'ID: {skin_id}') 

                r.add(embed) 

                ''' 
                start = f"Rejected {chars.x}" if result is not None else f"Attemped to reject {chars.warning}" 

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
        r = reports.Report(self, c) 

        self.fetch_tokens(1) 

        token = self.get_token(0) 

        if token: 
            list_request = grequests.request('GET', self.SKIN_REVIEW_LIST_URL, headers={
                'Authorization': f'Bearer {token}', 
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

    async def self_embed(self): 
        guilds = self.guilds
        guild_count = len(guilds) 

        user_count = self.links_table.count() 

        self_user = self.user

        color = discord.Color.random() 

        if self_user: 
            avatar_url = self_user.avatar
            discord_tag = str(self_user) 
        else: 
            avatar_url = None
            discord_tag = "Couldn't fetch Discord tag" 
        
        invite_hyperlink = f'Check my Discord profile for invite link' 
        
        embed = embed_utils.TrimmedEmbed(title=discord_tag, description=invite_hyperlink, color=color) 

        if avatar_url: 
            url = str(avatar_url) 
            
            salted = tools.salt_url(url) 

            debug(salted) 

            embed.set_thumbnail(url=salted) 

        owner = await self.fetch_user(self.OWNER_ID) 

        if owner: 
            owner_tag = str(owner) 

            embed.add_field(name=f"Creator {chars.carpenter}", value=f'{owner_tag} (<@{self.OWNER_ID}>)')

        embed.set_footer(text=f'Used by {user_count} users across {guild_count} guilds') 

        return embed
    
    @classmethod
    def parse_translation_format(cls, key): 
        translation_format = cls.STAT_FORMATS[key] 

        display_name, formatter, *rest = translation_format

        converter = tools.trunc_float
        multiplier = None

        if rest: 
            element = rest[0] 

            if type(element) in (float, int): 
                multiplier = element
            else: 
                converter = element
        
        return display_name, formatter, converter, multiplier
    
    def calc_change_result(self, converter, attr_name: str, old_value: float, diff: str):
        broken = False

        try:
            float_diff = float(diff)
        except ValueError:
            new_value_converted = f'Non-number ({diff})'
            broken = True
        else:
            new_value = old_value + float_diff
            
            new_value_converted = converter(new_value)

            if not math.isfinite(new_value) or new_value < 0:
                broken = True
            elif attr_name in self.EXTRA_VALIDITY_REQUIREMENTS:
                extra_requirement = self.EXTRA_VALIDITY_REQUIREMENTS[attr_name]

                broken = not extra_requirement(new_value_converted)

                # debug(broken)
        
        return new_value_converted, broken
    
    def generate_stat_changes(self, stat_changes, animal) -> list[tuple]: 
        stat_changes_list = [] 

        for change in stat_changes.split(';'):
            split = change.split('=')

            if len(split) == 2: 
                attribute, diff = split

                key = self.STAT_CHANGE_TRANSLATIONS.get(attribute, None) 

                if key: 
                    display_name, formatter, converter, multiplier = self.parse_translation_format(key) 

                    old_value = animal[key]

                    if multiplier is not None:
                        old_value *= multiplier
                    
                    if converter is not None:
                        old_value_converted = converter(old_value)
                    else:
                        old_value_converted = old_value
                    
                    new_value_converted, broken = self.calc_change_result(converter, attribute, old_value, diff)

                    change = attribute, old_value_converted, new_value_converted, broken
                    # '**{display_name}:** {old_value_str} **->** {new_value_str}' 
                else: 
                    change = f'Untranslated change: {change}' 
            else: 
                change = f'Malformed change: {change}' 
            
            stat_changes_list.append(change)
        
        return stat_changes_list
    
    def add_stat_changes(self, embed: embed_utils.TrimmedEmbed, stat_changes: str, animal: dict):
        stat_changes_array = self.generate_stat_changes(stat_changes, animal)
        display_list = []

        for change in stat_changes_array:
            if type(change) is tuple:
                attribute, old_val, new_val, broken = change

                key = self.STAT_CHANGE_TRANSLATIONS[attribute]

                display_name, formatter, converter, multiplier = self.parse_translation_format(key)

                old_val_str = formatter.format(old_val)

                if type(new_val) is str:
                    new_val_str = new_val
                else:
                    new_val_str = formatter.format(new_val)
                
                line = f'**{display_name}:** {old_val_str} **->** {new_val_str}'

                if broken:
                    line += f' `{chars.x}`'
            else:
                line = f'{change} `{chars.x}`'
            
            display_list.append(line)
        
        display = tools.make_list(display_list)

        embed.add_field(name=f'Stat changes {chars.change}', value=display, inline=False)
    
    async def display_animal_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction, 
    message_interaction: discord.Interaction):
        first_value = menu.values[0]

        index = int(first_value)

        animal = self.animal_stats[index]

        await menu_interaction.response.defer(thinking=True)

        await menu_interaction.followup.send(embed=self.animal_embed(animal))
    
    def animal_page_menu(self, message_interaction: discord.Interaction, animals: list[dict]) -> tuple[ui.CallbackSelect]:
        options = [ui.TruncatedSelectOption(label=animal['name'], value=animal['fishLevel'],
        description=f"ID: {animal['fishLevel']}") for animal in animals]

        menu = ui.CallbackSelect(self.display_animal_from_menu, message_interaction, options=options,
        placeholder='Choose an animal')

        return (menu,)
    
    async def display_animal(self, interaction: discord.Interaction, animal_query):
        animal_data = await self.search_with_suggestions(interaction, 'animals', (f'Animal {chars.fish}',), ('{[name]}',), 
        self.animal_stats,
        lambda animal: animal['name'], animal_query, self.animal_page_menu, no_duplicates=True)

        if animal_data:
            animal = animal_data[0]

            await interaction.response.defer()

            await interaction.followup.send(embed=self.animal_embed(animal))
    
    async def skin_by_id(self, interaction: discord.Interaction, skin_id: str, version: int):   
        skin_url = self.SKIN_URL_TEMPLATE.format(skin_id)

        if version:
            skin_url += f'/{version}'

        skin_json = self.async_get(skin_url)[0] 

        await interaction.response.defer()

        if skin_json: 
            safe = skin_json['approved'] or skin_json['reviewed'] and not skin_json['rejected'] 

            if self.is_sb_channel(interaction.channel.id) or safe: 
                book = self.skin_embed(interaction, skin_json)
                
                await book.send_first()
            else: 
                await interaction.followup.send(content=f"You can only view approved or pending skins in this channel. Use this in a Skin Board channel to bypass this restriction.") 
        else: 
            await interaction.followup.send(content=f"That's not a skin. Maybe your ID and/or version are wrong.")
    
    async def display_skin_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, possible_skins: list[dict]):
        first_value = menu.values[0]

        index = int(first_value)

        skin = possible_skins[index]

        await menu_interaction.response.defer(thinking=True)

        book = self.skin_embed(menu_interaction, skin)

        await book.send_first()
    
    def skin_page_menu(self, message_interaction: discord.Interaction, possible_skins: list[dict]) -> tuple[ui.CallbackSelect]:
        options = [ui.TruncatedSelectOption(label=possible_skins[index]['name'], 
        description=f"ID: {possible_skins[index]['id']}", value=index) for index in range(len(possible_skins))]

        menu = ui.CallbackSelect(self.display_skin_from_menu, message_interaction, possible_skins.copy(), options=options,
        placeholder='Choose a skin')

        return (menu,)

    async def skin_by_name(self, interaction: discord.Interaction, skin_name, list_name: str):
        await interaction.response.defer()

        skins_list = self.skins_from_list(list_name)
        
        if skins_list: 
            skin_suggestions = await self.search_with_suggestions(interaction, 'skins', 
            (f'Skin {chars.SHORTCUTS.skin_symbol}', f'ID {chars.folder}'),
            ('{[name]}', '{[id]}'),
            skins_list, lambda skin: skin['name'], skin_name, self.skin_page_menu) 

            if skin_suggestions:
                promises = map(lambda suggestion: ui.Promise(self.skin_embed, interaction, suggestion), skin_suggestions)

                book = ui.ScrollyBook(interaction, *promises, page_title='Skin')

                await book.send_first()

            '''
            skin_json = None
            suggestions_str = '' 

            if type(skin_data) is list: 
                if len(skin_data) == 1: 
                    skin_json = skin_data[0] 
                else: 
                    if skin_data: 
                        skin_names = (skin['name'] for skin in skin_data) 

                        suggestions_str = tools.format_iterable(skin_names, formatter='`{}`') 

                        suggestions_str = f"Maybe you meant one of these? {suggestions_str}" 
                
                debug(f'Suggestions length: {len(skin_data)}') 
            elif skin_data: 
                skin_json = skin_data

                debug('match found') 
            else: 
                debug('limit exceeded') 

            if skin_json: 
                book = self.skin_embed(interaction, skin_json)
                
                await book.send_first()
            else: 
                text = "That's not a valid skin name. " + suggestions_str

                await interaction.followup.send(content=text) 
            '''
        else: 
            await interaction.followup.send(content=f"Can't fetch skins. Most likely the game is down and you'll need to wait \
until it's fixed. ") 

    def skin_embed_pages(self, interaction: discord.Interaction, skin: dict, status: dict, skin_embed: embed_utils.TrimmedEmbed, 
    extra_assets: dict[str, str]) -> ui.Page:
        pages = [('Main asset', ui.Page(interaction, embed=skin_embed))]
        
        if extra_assets:
            for asset_type, asset_data in extra_assets.items(): 
                asset_filename = asset_data['asset'] 

                if asset_filename[0].isnumeric(): 
                    template = self.CUSTOM_SKIN_ASSET_URL_TEMPLATE
                else:
                    template = self.SKIN_ASSET_URL_TEMPLATE
                
                extra_asset_url = template.format(asset_filename)
                salted_url = extra_asset_url

                copied = skin_embed.copy()

                copied.set_image(url=salted_url)

                new_entry = asset_type, ui.Page(interaction, embed=copied)

                pages.append(new_entry)
        
        if status['approved']:
            skin_type = 'approved'
        elif status['upcoming']:
            skin_type = 'upcoming'
        elif status['reviewed'] and not status['rejected']:
            skin_type = 'pending'
        else:
            skin_type = None
        
        buttons = self.approved_display_buttons(interaction, (skin,), skin_type, False)
        
        book = ui.IndexedBook(interaction, *pages, extra_buttons=buttons)

        return book
        
    def skin_embed(self, interaction: discord.Interaction, skin, direct_api=False) -> ui.Page: 
        color = discord.Color.random() 

        stat_changes = skin['attributes'] 
        when_created = skin['created_at'] 
        designer_id = skin['designer_id'] 
        animal_id = skin['fish_level'] 
        ID = skin['id'] 
        price = skin['price'] 
        sales = skin['sales'] 
        last_updated = skin['updated_at'] 
        version = skin['version'] 

        store_page = self.SKIN_STORE_PAGE_TEMPLATE.format(ID)

        asset_name = skin['asset'] 

        animal = self.find_animal_by_id(animal_id) 

        animal_name = animal['name'] 

        desc = None
        extra_assets = None
        reddit_link = None
        category = None
        season = None
        usable = None

        status = {
            attr: None for attr in self.SKIN_STATUS_ATTRS
        } 

        user = None

        if not direct_api:
            id_and_version = f'{ID}/{version}'

            skin_url = self.SKIN_URL_TEMPLATE.format(id_and_version) 

            skin_json = self.async_get(skin_url)[0] 
        else: 
            skin_json = skin

        def get(attribute):
            if attribute in skin:
                return skin[attribute]
            elif skin_json:
                return skin_json[attribute]
            else:
                return None
        
        desc = get('description')

        extra_assets = get('assets_data')

        #debug(desc) 

        reddit_link = get('reddit_link')
        category = get('category')
        season = get('season')
        usable = get('usable')

        user = get('user')

        for attr in self.SKIN_STATUS_ATTRS: 
            status[attr] = get(attr)

        #debug(desc) 

        embed = embed_utils.TrimmedEmbed(title=skin['name'], description=desc, color=color, url=store_page)

        if asset_name[0].isnumeric(): 
            template = self.CUSTOM_SKIN_ASSET_URL_TEMPLATE
        else:
            template = self.SKIN_ASSET_URL_TEMPLATE

        asset_url = template.format(asset_name)

        debug(asset_url) 

        embed.set_image(url=asset_url) 

        #animal_name = self.get_animal(animal_id) 

        embed.add_field(name=f"Animal {chars.fish}", value=animal_name) 
        embed.add_field(name=f"Price {chars.deeeepcoin}", value=f'{price:,}') 

        sales_emoji = chars.stonkalot if sales >= self.STONKS_THRESHOLD else chars.stonkanot

        embed.add_field(name=f"Sales {sales_emoji}", value=f'{sales:,}') 

        if stat_changes: 
            self.add_stat_changes(embed, stat_changes, animal) 

        if category: 
            embed.add_field(name=f"Category {chars.folder}", value=category) 

        if season: 
            embed.add_field(name=f"Season {chars.calendar}", value=season) 
        
        if usable is not None: 
            usable_emoji = chars.check if usable else chars.x

            embed.add_field(name=f"Usable {usable_emoji}", value=usable) 
        
        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {chars.tools}", value=f'{tools.timestamp(date_created)}') 

        version_str = str(version) 
        version_inline = True

        if last_updated: 
            date_updated = parser.isoparse(last_updated) 

            version_str += f' (updated {tools.timestamp(date_updated)})' 
            version_inline = False
        
        embed.add_field(name=f"Version {chars.wrench}", value=version_str, inline=version_inline) 

        if reddit_link: 
            embed.add_field(name=f"Reddit link {chars.reddit}", value=reddit_link)
        
        status_strs = [] 

        for status_attr, status_value in status.items(): 
            if status_value == True: 
                emoji = chars.check
            elif status_value == False: 
                emoji = chars.x
            else: 
                emoji = chars.question_mark
            
            status_str = f'`{emoji}` {status_attr.capitalize()}' 

            status_strs.append(status_str) 
        
        status_list_str = tools.make_list(status_strs, bullet_point='') 

        embed.add_field(name=f"Creators Center status {chars.magnifying_glass}", value=status_list_str, inline=False)

        reject_reaons = self.reject_reasons(skin, check_reddit=False)

        if reject_reaons:
            reasons_str = tools.make_list(reject_reaons)

            embed.add_field(name=f'Problems {chars.sarcastic_fringehead_out}', value=reasons_str)

        if user: 
            user_username = user['username'] 
            user_pfp = user['picture'] 
            user_page = self.PROFILE_PAGE_TEMPLATE.format(parse.quote(user_username))

            creator = user_username

            if not user_pfp: 
                user_pfp = self.DEFAULT_BETA_PFP
            else: 
                user_pfp = self.PFP_URL_TEMPLATE.format(user_pfp)
            
            pfp_url = tools.salt_url(user_pfp)

            debug(pfp_url)
            debug(user_page)

            embed.set_author(name=creator, icon_url=pfp_url, url=user_page) 

        embed.set_footer(text=f"ID: {ID}")

        pages = self.skin_embed_pages(interaction, skin, status, embed, extra_assets)

        return pages
    
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

            embed = embed_utils.TrimmedEmbed(title=title, type='rich', description=desc, color=color) 
            
            if not pfp: 
                pfp = self.DEFAULT_BETA_PFP
            else: 
                pfp = self.PFP_URL_TEMPLATE.format(pfp) 
            
            pfp_url = tools.salt_url(pfp) 

            debug(pfp_url) 
            
            embed.set_image(url=pfp_url) 

            embed.add_field(name=f"Kills {chars.iseedeadfish}", value=f'{kills:,}') 
            embed.add_field(name=f"Highscore {chars.first_place}", value=f'{max_score:,}') 
            embed.add_field(name=f"Coins {chars.deeeepcoin}", value=f'{coins:,}') 

            when_created = acc['date_created'] 
            when_last_played = acc['date_last_played'] 

            if when_created: 
                date_created = parser.isoparse(when_created) 

                embed.add_field(name=f"Date created {chars.baby}", value=f'{tools.timestamp(date_created)}') 

            if when_last_played: 
                date_last_played = parser.isoparse(when_last_played) 

                embed.add_field(name=f"Date last played {chars.video_game}", value=f'{tools.timestamp(date_last_played)}') 
        else: 
            embed = embed_utils.TrimmedEmbed(title='Error fetching account statistics', type='rich', description="There was an error fetching account statistics. ", color=color) 

            embed.add_field(name="Why?", value="This usually happens when you have skill issue and entered an invalid user on \
the `hackprofile` command. But it could also mean the game is down, especially if it happens on the `profile` command.") 
            embed.add_field(name="What now?", value="If this is because you made a mistake, just git gud in the future. If the \
game is down, nothing you can do but wait.") 
        
        embed.set_footer(text=f'ID: {acc_id}') 

        if contribs: 
            contribs_str = tools.make_list(contribs) 

            embed.add_field(name=f"Contributions {chars.heartpenguin}", value=contribs_str, inline=False) 
        
        if roles: 
            roles_str = tools.format_iterable(roles) 

            embed.add_field(name=f"Roles {chars.cooloctopus}", value=roles_str, inline=False)

        return embed
    
    def generate_socials(self, socials: list[dict]):
        mapped = []

        for social in socials:
            platform = social['platform_id']
            display = social['platform_user_id']
            verified = social['verified']
            given_url = social['platform_user_url']

            verified_text = ' '+ chars.verified if verified else ''

            icon, template = self.IconsEnum[platform].value

            if given_url:
                text = f'[{display}]({given_url})'
            elif template:
                text = f'[{display}]({template.format(display)})'
            else:
                text = display
            
            full_text = f'{icon} {text}{verified_text}'

            mapped.append(full_text)
        
        return '\n'.join(mapped)
    
    def profile_error_embed(self):
        color = discord.Color.random() 

        embed = embed_utils.TrimmedEmbed(title='Invalid account', type='rich', description="You have been trolled", color=color) 

        embed.add_field(name="Why?", value="""This usually happens when you have skill issue and entered an invalid user on \
the `hackprofile` command. 

But it could also mean the game is down, especially if it happens on the `profile` command.""", inline=False) 
        embed.add_field(name="What now?", value="If this is because you made a mistake, just git gud in the future. If the \
game is down, nothing you can do but wait.", inline=False)

        return embed
    
    def base_profile_embed(self, acc: dict, specific_page: str='', big_image=True, blacklist=False):
        acc_id = acc['id']
        real_username = acc['username']
        verified = acc['verified']

        public_page = self.PROFILE_PAGE_TEMPLATE.format(parse.quote(real_username))
        
        if blacklist:
            display_username = '(Blacklisted account)'
        else:
            display_username = real_username

        title = f'{specific_page}{" " if specific_page else ""}{display_username}{f" {chars.verified}" if verified else ""}'

        pfp = acc['picture'] 

        #debug(pfp_url)

        tier = acc['tier']

        color = self.TIER_COLORS[tier - 1]

        #debug(hex(color)) 

        embed = embed_utils.TrimmedEmbed(title=title, type='rich', color=color, url=public_page)

        if not blacklist:
            if not pfp: 
                pfp = self.DEFAULT_BETA_PFP
            else: 
                pfp = self.BETA_PFP_TEMPLATE.format(pfp) 
            
            pfp_url = tools.salt_url(pfp) 

            debug(pfp_url) 
            
            if big_image:
                embed.set_image(url=pfp_url)
            else:
                embed.set_thumbnail(url=pfp_url)

        footer_text = f'ID: {acc_id}'

        embed.set_footer(text=footer_text) 

        return embed
    
    def profile_embed(self, acc: dict, socials: list[dict]):
        desc = acc['about']
        
        kills = acc['kill_count'] 
        max_score = acc['highest_score'] 
        coins = acc['coins'] 
        plays = acc['play_count']
        views = acc['profile_views']

        xp = acc['xp']
        tier = acc['tier']

        death_message = acc['description']

        embed = self.base_profile_embed(acc)

        embed.description = desc

        embed.add_field(name=f"Kills {chars.iseedeadfish}", value=f'{kills:,}') 
        embed.add_field(name=f"Highscore {chars.first_place}", value=f'{max_score:,}') 
        embed.add_field(name=f"Coins {chars.deeeepcoin}", value=f'{coins:,}') 

        embed.add_field(name=f"Play count {chars.video_game}", value=f'{plays:,}')

        tier_emoji = self.TIER_EMOJIS[tier - 1]

        embed.add_field(name=f"XP {tier_emoji}", value=f'{xp:,} XP (Tier {tier})', inline=False)

        when_created = acc['date_created'] 
        when_last_played = acc['date_last_played'] 

        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {chars.birthday_cake}", value=f'{tools.timestamp(date_created)}') 

        if when_last_played: 
            date_last_played = parser.isoparse(when_last_played) 

            embed.add_field(name=f"Date last played {chars.video_game}", value=f'{tools.timestamp(date_last_played)}') 
        
        embed.add_field(name=f"Death message {chars.iseedeadfish}", value=f'*"{death_message}"*', inline=False)

        if socials:
            embed.add_field(name=f"Social links {chars.speech_bubble}", value=self.generate_socials(socials), inline=False)

        embed.add_field(name=f"Profile views {chars.eyes}", value=f'{views:,}')

        return embed
    
    def rankings_embed(self, acc: dict, rankings: dict):
        kills = acc['kill_count'] 
        max_score = acc['highest_score'] 
        plays = acc['play_count']

        embed = self.base_profile_embed(acc, specific_page='Stats & rankings for', big_image=False)

        if rankings:
            kill_rank_str = f" **(#{rankings['rank_kc']})**"
            score_rank_str = f" **(#{rankings['rank_hs']})**"
            plays_rank_str = f" **(#{rankings['rank_pc']})**"
        else:
            kill_rank_str = score_rank_str = plays_rank_str = ''
        
        embed.add_field(name=f"Kills {chars.iseedeadfish}", value=f'{kills:,}{kill_rank_str}') 
        embed.add_field(name=f"Highscore {chars.first_place}", value=f'{max_score:,}{score_rank_str}') 
        embed.add_field(name=f"Play count {chars.video_game}", value=f'{plays:,}{plays_rank_str}')

        if rankings:
            pd_stats = rankings['pd']

            if pd_stats:
                played = pd_stats['played']
                ratio = pd_stats['ratio']
                won = pd_stats['won']

                value = f'''• {won:,} wins
• {played:,} played
• {ratio}% won'''
            else:
                value = "Didn't play PD"

            embed.add_field(name=f"Pearl Defense stats (last 30 days) {chars.oyster}", value=value)
        
        return embed
    
    def gen_generic_compilation_page(self, interaction: discord.Interaction, embed_template: embed_utils.TrimmedEmbed, 
    items: list[dict],
    column_titles: tuple[str], column_strs: tuple[str], totals_str: str, tacked_fields: tuple[embed_utils.Field],
    page_buttons_func) -> ui.Page:
        embed = embed_template.copy()

        for tacked_field in tacked_fields:
            embed.add_field(**tacked_field.to_dict())

        for column_title, column_str in zip(column_titles, column_strs):
            embed.add_field(name=column_title, value=column_str)

        embed.add_field(name=f'Totals {chars.abacus}', value=totals_str, inline=False)

        if page_buttons_func:
            buttons = page_buttons_func(interaction, items)
        else:
            buttons = ()

        return ui.Page(interaction, embed=embed, buttons=buttons)
    
    def build_generic_compilation(self, interaction: discord.Interaction, embed_template: embed_utils.TrimmedEmbed, 
    comp_item: dict, 
    pages: list[ui.Page], titles: tuple[str], formatters: tuple[str], items: list[dict], 
    destinations: tuple[list], destination_lengths: list[int], totals_str: str, tacked_fields: tuple[embed_utils.Field], 
    page_buttons_func, artificial_limit: int):
        for index in range(len(destinations)):
            formatted = formatters[index].format(comp_item)
            
            destination_lengths[index] += len(formatted) + int(destination_lengths[index] > 0)

        # as of calculating this variable, the stuff has not been added to the running sum yet!
        too_long = artificial_limit and len(items) >= artificial_limit

        if not too_long:
            for destination_length in destination_lengths:
                if destination_length > embed_utils.TrimmedEmbed.MAX_FIELD_VAL:
                    too_long = True

                    break
        
        if too_long:
            column_strs = tuple(tools.format_iterable(column_list, sep='\n') for column_list in destinations)

            new_page = self.gen_generic_compilation_page(interaction, embed_template, items, titles, column_strs,
            totals_str, tacked_fields, page_buttons_func)

            pages.append(new_page)

            for index in range(len(destinations)):
                formatted = formatters[index].format(comp_item)

                destination_lengths[index] = len(formatted)
                destinations[index].clear()
            
            items.clear()
        
        for index in range(len(destinations)):
            formatted = formatters[index].format(comp_item)
            
            destinations[index].append(formatted)
        
        items.append(comp_item)
    
    @staticmethod
    def generic_compilation_aggregate(compilation_type: str, comp_items: list[dict], aggregate_names: tuple[str], 
    aggregate_attrs: tuple) -> str:
        aggregates = [f'{len(comp_items):,} {compilation_type}']
        
        for aggregate_name, aggregate_attr in zip(aggregate_names, aggregate_attrs):
            if type(aggregate_attr) is int:
                total = aggregate_attr
            else:
                total = sum(map(lambda creation: creation[aggregate_attr], comp_items))

            formatted = f'{total:,} {aggregate_name}'

            aggregates.append(formatted)
        
        return tools.make_list(aggregates)
    
    def generic_compilation_embeds(self, interaction: discord.Interaction, embed_template: embed_utils.TrimmedEmbed, 
    compilation_type: str, comp_items: list[dict],
    titles: tuple[str], formatters: tuple[str], aggregate_names: tuple[str]=(),
    aggregate_attrs: tuple[str]=(), tacked_fields: tuple[embed_utils.Field]=(),
    empty_description: str=None, extra_buttons=(), page_buttons_func=None, artificial_limit=None):
        if comp_items:
            pages = []
            destinations = tuple([] for title in titles)
            cur_items = []
            destination_lengths = [0] * len(titles)
            
            totals_str = self.generic_compilation_aggregate(compilation_type, comp_items, aggregate_names, aggregate_attrs)

            for comp_item in comp_items:
                self.build_generic_compilation(interaction, embed_template, comp_item, pages, titles, formatters, cur_items,
                destinations, destination_lengths, totals_str, tacked_fields, page_buttons_func, artificial_limit)
            
            column_strs = tuple(tools.format_iterable(column_list, sep='\n') for column_list in destinations)

            last_page = self.gen_generic_compilation_page(interaction, embed_template, cur_items, titles, column_strs,
            totals_str, tacked_fields, page_buttons_func)

            pages.append(last_page)

            debug(pages)

            return ui.ScrollyBook(interaction, *pages, extra_buttons=extra_buttons)
        else:
            embed = embed_template.copy()

            for tacked_field in tacked_fields:
                embed.add_field(**tacked_field.to_dict())
            
            if comp_items is None:
                embed.add_field(name=f"Something went wrong {chars.whoopsy_dolphin}", value=f'There was an error fetching \
{compilation_type}.')
            else:
                embed.add_field(name=f'No {compilation_type} {chars.funwaa_eleseal}', 
            value=empty_description or f'Nothing to see here, move along.')

            return ui.Page(interaction, embed=embed)

    def skin_contribs_embeds(self, interaction: discord.Interaction, acc: dict, skins: list[dict]):
        embed_template = self.base_profile_embed(acc, specific_page='Skins by', big_image=False)

        embed_template.description = 'This list only includes **officlally added** skins (skins approved for the Store)'

        titles = f'Skin {chars.SHORTCUTS.skin_symbol}', f'Sales {chars.stonkalot}'
        formatters = self.SKIN_EMBED_LINK_FORMATTER, '{[sales]:,}'

        skins.sort(key=lambda skin: skin['sales'], reverse=True)

        return self.generic_compilation_embeds(interaction, embed_template, 'skins', skins, titles, formatters, 
        aggregate_names=('sales',), aggregate_attrs=('sales',))
    
    def map_creations_embeds(self, interaction: discord.Interaction, acc: dict, maps: dict):
        embed_template = self.base_profile_embed(acc, specific_page='Maps by', big_image=False)

        embed_template.description = 'This list includes all maps marked **public**, including those not added as official maps'

        public_maps = list(filter(lambda map: map['public'], maps['items']))

        public_maps.sort(key=lambda map: map['likes'], reverse=True)

        titles = f'Map {chars.world_map}', f'Likes {chars.thumbsup}'
        formatters = self.MAP_EMBED_LINK_FORMATTER, '{[likes]:,}'

        return self.generic_compilation_embeds(interaction, embed_template, 'maps', public_maps, titles, formatters)
    
    def profile_embed_by_username(self, username: str):
        return self.profile_embed(*self.get_profile_by_username(username))
    
    def profile_embed_by_id(self, id):
        return self.profile_embed(*self.get_profile_by_id(id))
    
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
        locked = map_json['locked'] 

        when_created = map_json['created_at'] 
        when_updated = map_json['updated_at'] 

        map_data = json.loads(map_json['data']) 
        tags = map_json['tags'] 
        creator = map_json['user'] 

        tags_list = [tag['id'] for tag in tags] 
        creator_username = creator['username'] 
        creator_pfp = creator['picture'] 
        creator_page = self.PROFILE_PAGE_TEMPLATE.format(parse.quote(creator_username))

        world_size = map_data['worldSize'] 
        width = world_size['width'] 
        height = world_size['height'] 

        objs = map_data['screenObjects'] 

        map_link = self.MAPMAKER_URL_TEMPLATE.format(parse.quote(string_id)) 

        embed = embed_utils.TrimmedEmbed(title=title, description=desc, color=color, url=map_link) 

        embed.add_field(name=f"Likes {chars.thumbsup}", value=f'{likes:,}') 
        
        embed.add_field(name=f"Dimensions {chars.triangleruler}", value=f'{width} x {height}') 

        if 'settings' in map_data: 
            settings = map_data['settings'] 
            gravity = settings['gravity'] 

            embed.add_field(name=f"Gravity {chars.down}", value=f'{gravity:,}') 

        obj_count_list = self.count_objects(objs) 

        obj_count_str = tools.make_list(obj_count_list) 

        embed.add_field(name=f"Object count {chars.scroll}", value=obj_count_str, inline=False) 

        creator_str = creator_username

        if not creator_pfp: 
            creator_pfp = self.DEFAULT_BETA_PFP
        else: 
            creator_pfp = self.PFP_URL_TEMPLATE.format(creator_pfp) 
        
        pfp_url = tools.salt_url(creator_pfp) 

        debug(pfp_url) 

        embed.set_author(name=creator_str, icon_url=pfp_url, url=creator_page) 

        if clone_of: 
            clone_url = self.MAP_URL_TEMPLATE.format(clone_of) 

            clone_json = self.async_get(clone_url)[0] 

            if clone_json: 
                clone_title = clone_json['title'] 
                clone_string_id = clone_json['string_id'] 

                clone_link = self.MAPMAKER_URL_TEMPLATE.format(clone_string_id) 

                embed.add_field(name=f"Cloned from {chars.notes}", value=f'[{clone_title}]({clone_link})') 
        
        if when_created: 
            date_created = parser.isoparse(when_created) 

            embed.add_field(name=f"Date created {chars.tools}", value=f'{tools.timestamp(date_created)}') 
        
        if when_updated: 
            date_updated = parser.isoparse(when_updated) 

            embed.add_field(name=f"Date last updated {chars.wrench}", value=f'{tools.timestamp(date_updated)}') 
        
        lock_emoji = chars.lock if locked else chars.unlock
        
        embed.add_field(name=f"Locked {lock_emoji}", value=locked) 

        if tags_list: 
            tags_str = tools.format_iterable(tags_list, formatter='`{}`') 

            embed.add_field(name=f"Tags {chars.label}", value=tags_str, inline=False) 

        embed.set_footer(text=f'''ID: {ID}
String ID: {string_id}''') 

        return embed
    
    def skin_str_list(self, r, skin_list): 
        for skin in skin_list: 
            name = skin['name'] 
            ID = skin['id'] 
            version = skin['version'] 
            animal_id = skin['fish_level'] 
            animal = self.find_animal_by_id(animal_id) 
            animal_name = animal['name'] 

            skin_str = f"• {name} (v{version}) | (ID: {ID}) | {animal_name}" 

            r.add(skin_str) 
    
    def build_skins_report(self, r, skin_list): 
        if skin_list is None: 
            r.add('There was an error fetching skins.') 
        elif skin_list: 
            self.skin_str_list(r, skin_list) 
        else: 
            r.add('There are no skins in this category.') 
    
    @staticmethod
    def rl(skin_list): 
        return len(skin_list) if skin_list is not None else 0
    
    async def pending_display(self, r, filter_names_str, filters): 
        color = discord.Color.random() 

        pending, upcoming, motioned, rejected, trimmed_str = self.get_pending_skins(*filters) 

        r.add(f'**__Pending skins with filters {filter_names_str}__**') 
        
        r.add(f"**Unnoticed skins ({self.rl(pending)}) {chars.ghost}**") 
        self.build_skins_report(r, pending) 

        r.add(f"**Upcoming skins ({self.rl(upcoming)}) {chars.clock}**") 
        self.build_skins_report(r, upcoming) 
        
        r.add(f"**Skins in motion ({self.rl(motioned)}) {chars.ballot_box}**") 
        self.build_skins_report(r, motioned) 
        
        r.add(f"**Recently rejected skins ({self.rl(rejected)}) {chars.x}**") 
        self.build_skins_report(r, rejected) 

        if trimmed_str: 
            r.add(trimmed_str)
    
    def skin_search_base_embed(self, actual_type: str, description: str, filter_names_str: str):
        color = discord.Color.random()

        embed = embed_utils.TrimmedEmbed(title=f'{actual_type.capitalize()} skin search', description=description, color=color)

        if filter_names_str:
            tacked_fields = (embed_utils.Field(name=f'Filters used {chars.magnifying_glass}', value=filter_names_str, 
            inline=False),)
        else:
            tacked_fields = ()

        return embed, tacked_fields
    
    def mass_motion_requests(self, to_motion: list[dict], approve: bool) -> list[str]:  
        with self.borrow_token() as token:
            ids_and_versions = []
            requests = []

            for skin in to_motion:
                skin_id = skin['id']
                skin_version = skin['version']

                payload = {
                    'target_id': skin_id,
                    'target_type': 'skin',
                    'target_version': skin_version,
                    'type': 'approve' if approve else 'reject',
                }

                headers = {
                    'authorization': f'Bearer {token}',
                    'origin': 'https://creators.deeeep.io',
                }

                request = grequests.request('POST', self.MOTION_CREATION_URL, data=payload, headers=headers)

                ids_and_versions.append((skin_id, skin_version))
                requests.append(request)
            
            # debug(requests)
            
            results = self.async_get(*requests)

            # results = [None] * len(to_motion)
        
        failure_descs = []

        for index in range(len(results)):
            ID, version = ids_and_versions[index]
            result = results[index]

            if not result:
                failure_descs.append(f'{ID} (version {version})')
        
        return failure_descs
    
    async def mass_motion(self, interaction: discord.Interaction, to_motion: list[dict], approve: bool):
        await interaction.response.defer(thinking=True)

        failures = self.mass_motion_requests(to_motion, approve)

        failures_str = tools.format_iterable(failures)

        motion_type = 'approval' if approve else 'removal'

        await interaction.followup.send(content=f'Motioned {len(to_motion)} skins for {motion_type}, {len(failures)} failures: {failures_str}')
    
    async def approved_display_button_callback(self, button: ui.CallbackButton, button_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, skins: list[dict], approve: bool):
        await self.mass_motion(button_interaction, skins, approve)
    
    def approved_display_buttons(self, interaction: discord.Interaction, skins: list[dict], actual_type: str, multi: bool):
        if interaction.user.id == self.OWNER_ID:
            addition = ' all' if multi else ''

            approve_button = ui.CallbackButton(self.approved_display_button_callback, interaction, skins, True, 
            label=f'Motion to approve{addition}', style=discord.ButtonStyle.green)
            reject_button = ui.CallbackButton(self.approved_display_button_callback, interaction, skins, False, 
            label=f'Motion to remove{addition}', style=discord.ButtonStyle.red)

            if actual_type == 'pending': 
                return approve_button, reject_button
            
            elif actual_type == 'upcoming':
                return (reject_button,)

            else:
                return ()
        else:
            return ()
    
    async def approved_display(self, interaction: discord.Interaction, actual_type, filter_names_str, filters):
        need_token = False

        if actual_type == 'approved': 
            description = f'These skins are in the [Approved section]({self.APPROVED_PAGE}) of the Creators Center. They are also \
in the [Store]({self.STORE_PAGE}) (when they are available to buy).'

        elif actual_type == 'pending': 
            description = f'These skins are in the [Pending section]({self.PENDING_PAGE}) of the Creators Center.'
        
        elif actual_type == 'upcoming':
            description = f'These skins are in the [Upcoming section]({self.UPCOMING_PAGE}) of the Creators Center.'
        
        approved = self.filtered_skins_from_list(actual_type, *filters)

        embed_template, tacked_fields = self.skin_search_base_embed(actual_type, description, filter_names_str)

        buttons = self.approved_display_buttons(interaction, approved, actual_type, True)

        display = self.generic_compilation_embeds(interaction, embed_template, 'skins found', approved, 
        (f'Skin {chars.SHORTCUTS.skin_symbol}', f'ID {chars.folder}', f'Price {chars.deeeepcoin}'),
        (self.SKIN_EMBED_LINK_FORMATTER, '{[id]}', '{[price]:,}'), aggregate_names=(chars.deeeepcoin, 'sales'),
        aggregate_attrs=('price', 'sales'), tacked_fields=tacked_fields, extra_buttons=buttons,
        page_buttons_func=self.skin_page_menu, artificial_limit=ui.CallbackSelect.MAX_OPTIONS)
        
        await display.send_first()
    
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
        import ds_commands

        self.readied = True

        '''
        if not self.auto_rev_process: 
            self.auto_rev_process = self.loop.create_task(self.auto_rev_loop()) 

            debug('created auto rev process') 
        '''
        
        await ds_commands.gen_commands(self)
        
        await self.change_presence(activity=discord.Game(name='all systems operational'), status=discord.Status.online)
        
        debug('ready') 
    
    def decode_mention(self, mention): 
        member_id = None

        if not mention.isnumeric(): 
            m = re.compile(self.MENTION_REGEX).match(mention)

            if m: 
                member_id = m.group('member_id') 
        else: 
            member_id = mention
        
        #debug(member_id) 
        
        return int(member_id) if member_id is not None else None
    
    def decode_channel(self, c, mention): 
        channel_id = None

        if not mention.isnumeric(): 
            m = re.compile(self.CHANNEL_REGEX).match(mention)

            if m: 
                channel_id = m.group('channel_id') 
        else: 
            channel_id = mention
        
        #debug(member_id) 
        
        return int(channel_id) if channel_id is not None else None
    
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
    
    def get_map_string_id(self, query): 
        m = re.compile(self.MAP_REGEX).match(query)

        if m: 
            map_string_id = m.group('map_string_id') 

            return map_string_id
        
        #debug(map_id)
    
    async def link_help(self, interaction: discord.Interaction): 
        p1 = ui.Page(interaction, content='le test')

        p2_1 = ui.Page(interaction, content='E')
        p2_2 = ui.Page(interaction, content='F')

        p3_1 = ui.Page(interaction, content='le trol')
        p3_2 = ui.Page(interaction, content='tro')

        p2 = ui.ScrollyBook(interaction, p2_1, p2_2)
        p3 = ui.IndexedBook(interaction, ('thing', p3_1), ('other thing', p3_2))

        book = ui.ScrollyBook(interaction, p1, p2, p3, timeout=20)

        await book.send_first()
    
    def get_acc_id(self, query): 
        acc_id = None

        if query.isnumeric(): 
            acc_id = query
        else: 
            m = re.compile(self.PFP_REGEX).match(query)

            if m: 
                acc_id = m.group('acc_id') 
                
        return acc_id
    
    def get_true_username(self, query): 
        m = re.compile(self.PROFILE_PAGE_REGEX).match(query) 

        if m: 
            username = m.group('username') 

            return username
    
    def search_by_username(self, username): 
        search_url = self.USERNAME_SEARCH_TEMPLATE.format(username) 

        return self.async_get(search_url)[0] 
    
    def search_by_id_or_username(self, query): 
        acc_data = None

        true_username = self.get_true_username(query) 
        
        if true_username is not None: 
            acc_data = self.search_by_username(true_username) 
        
        if acc_data is None: 
            acc_id = self.get_acc_id(query) 

            if acc_id is not None: 
                acc_data = self.get_acc_data(acc_id) 
        
        return acc_data
    
    def get_socials(self, account_id):
        socials_url = self.SOCIALS_URL_TEMPLATE.format(account_id)

        return self.async_get(socials_url)[0]
    
    def connect_help_book(self, interaction: discord.Interaction) -> ui.ScrollyBook:
        signin_embed = discord.Embed(title='Sign in to your Deeeep.io account on Beta')
        signin_embed.set_image(url=self.SIGNING_IN)
        signin_page = ui.Page(interaction, embed=signin_embed)

        profile_open_embed = discord.Embed(title='Open your Deeeep.io profile by clicking your profile picture')
        profile_open_embed.set_image(url=self.OPENING_PROFILE)
        profile_open_page = ui.Page(interaction, embed=profile_open_embed)

        discord_embed = discord.Embed(title='Add your Discord tag as a social link on your Deeeep.io account')
        discord_embed.set_image(url=self.ADDING_DISCORD)
        discord_page = ui.Page(interaction, embed=discord_embed)

        connect_embed = discord.Embed(title="Copy your profile page's URL, then paste that URL into the \"connect\" command")
        connect_embed.set_image(url=self.CONNECT_COMMAND)
        connect_page = ui.Page(interaction, embed=connect_embed)

        help_book = ui.ScrollyBook(interaction, signin_page, profile_open_page, discord_page, connect_page)

        return help_book
    
    async def send_connect_help(self, interaction: discord.Interaction):
        help_book = self.connect_help_book(interaction)

        await help_book.send_first()
    
    async def link_dep_acc(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        username = self.get_true_username(query)

        # print(username)

        if username:
            acc_data = self.search_by_username(username) 
        else:
            acc_data = None

        if acc_data: 
            acc_id = acc_data['id']

            link = self.links_table.find_one(user_id=interaction.user.id, acc_id=acc_id)

            if not link:
                socials = self.get_socials(acc_id)
                tag = str(interaction.user)

                for social in socials:
                    if social['platform_id'] == 'dc' and social['platform_user_id'] == tag:
                        reusername = acc_data['username'] 

                        data = {
                            'user_id': interaction.user.id, 
                            'acc_id': acc_id,
                            'main': False,
                        } 

                        self.links_table.upsert(data, ['user_id', 'acc_id'], ensure=True) 

                        await interaction.followup.send(content=f"Successfully linked to Deeeep.io account with username \
`{reusername}` and ID `{acc_id}`.")

                        return
                else: 
                    await interaction.followup.send(content=f"You must add your Discord tag as a social link on that account \
to connect it.")
            else:
                await interaction.followup.send(content="You're already linked to this account.")
        else: 
            await interaction.followup.send(content="That doesn't seem like a valid profile.")
    
    async def unlink_account(self, button: ui.CallbackButton, button_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, acc_id: int, *affected_buttons: ui.CallbackButton):
        user = button_interaction.user

        self.links_table.delete(user_id=user.id, acc_id=acc_id)

        button.label = 'Account unlinked'
        button.disabled = True

        for button in affected_buttons:
            button.disabled = True

        await button_interaction.response.send_message(content=f'Unlinked account with ID {acc_id}.')
        await message_interaction.edit_original_response(view=button.view)
    
    def determine_main(self, user_id: int, acc_id: int) -> bool:
        return self.mains_table.find_one(acc_id=acc_id, user_id=user_id)
    
    def update_mark_button(self, button: ui.CallbackButton, is_main: bool):
        if is_main:
            label = 'Unmark account as main'
            callback = self.unmark_main
        else:
            label = 'Mark account as main'
            callback = self.mark_main
        
        button.label = label
        button.stored_callback = callback
    
    async def update_mark_view(self, button: ui.CallbackButton, message_interaction: discord.Interaction, 
    is_main: bool):
        self.update_mark_button(button, is_main)

        await message_interaction.edit_original_response(view=button.view)
    
    async def mark_main(self, button: ui.CallbackButton, button_interaction: discord.Interaction,
    message_interaction: discord.Interaction, acc_id: int):
        row = dict(user_id=button_interaction.user.id, acc_id=acc_id)

        self.mains_table.upsert(row, ['user_id'], ensure=True)

        await button_interaction.response.send_message(content=f'This account (ID {acc_id}) will now be your first account.')

        await self.update_mark_view(button, message_interaction, True)
    
    async def unmark_main(self, button: ui.CallbackButton, button_interaction: discord.Interaction,
    message_interaction: discord.Interaction, acc_id: int):
        self.mains_table.delete(user_id=button_interaction.user.id, acc_id=acc_id)

        await button_interaction.response.send_message(content=f'This account (ID {acc_id}) will no longer be your first \
account. Well, it might still be, but that would just be due to random chance.')

        await self.update_mark_view(button, message_interaction, False)
    
    def generate_profile_buttons(self, interaction: discord.Interaction, user: discord.Member, acc_id: int):
        if user and user.id == interaction.user.id:
            is_main = self.determine_main(interaction.user.id, acc_id)

            toggle_main_button = ui.CallbackButton(None, interaction, acc_id)

            self.update_mark_button(toggle_main_button, is_main)

            unlink_button = ui.CallbackButton(self.unlink_account, interaction, acc_id, 
            style=discord.ButtonStyle.danger, label='Unlink account')

            return toggle_main_button, unlink_button
        else:
            return ()
    
    def profile_book(self, interaction: discord.Interaction, acc: dict, socials: list, 
    rankings: dict, skin_contribs: list[dict], map_creations: dict, user: discord.Member=None, user_blacklist=False) -> ui.Page:
        if acc:
            '''
            options = [discord.SelectOption(label=i) for i in range(5)]

            useless_menu = discord.ui.Select(placeholder='Useless menu', options=options)
            useless_button = discord.ui.Button(label='Useless button')
            '''

            buttons = self.generate_profile_buttons(interaction, user, acc['id'])

            if not user_blacklist and not self.blacklisted(interaction.guild_id, 'account', acc['id']):
                home_page = ui.Page(interaction, embed=self.profile_embed(acc, socials))
                rankings_page = ui.Page(interaction, embed=self.rankings_embed(acc, rankings))

                skin_contribs_page = self.skin_contribs_embeds(interaction, acc, skin_contribs)
                map_creations_page = self.map_creations_embeds(interaction, acc, map_creations)

                contribs_page = ui.IndexedBook(interaction, ('Skins', skin_contribs_page), ('Maps', map_creations_page))

                profile_book = ui.IndexedBook(interaction, ('About', home_page), ('Stats & Rankings', rankings_page), 
                ('Creations', contribs_page), extra_buttons=buttons)

                return profile_book
            else:
                return ui.Page(interaction, embed=self.base_profile_embed(acc, blacklist=True), buttons=buttons)
        else:
            return ui.Page(interaction, embed=self.profile_error_embed())

    def delayed_profile_book(self, interaction: discord.Interaction, user: discord.Member, acc_id: int, blacklist: bool): 
        acc, socials, rankings, skin_contribs, map_creations = self.get_profile_by_id(acc_id)
        
        return self.profile_book(interaction, acc, socials, rankings, skin_contribs, map_creations, user=user, 
        user_blacklist=blacklist)
    
    async def full_profile_book(self, interaction: discord.Interaction, user: discord.Member, *acc_ids: int,
    blacklist: bool):
        pages = map(lambda acc_id: ui.Promise(self.delayed_profile_book, interaction, user, acc_id, blacklist), 
        acc_ids)

        full_book = ui.ScrollyBook(interaction, *pages, page_title='Account')

        await full_book.send_first()
    
    async def display_account_by_username(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()

        acc, socials, rankings, skin_contribs, map_creations = self.get_profile_by_username(username)

        book = self.profile_book(interaction, acc, socials, rankings, skin_contribs, map_creations)

        await book.send_first()
    
    async def display_account_by_id(self, interaction: discord.Interaction, account_id: int):
        await interaction.response.defer()

        acc, socials, rankings, skin_contribs, map_creations = self.get_profile_by_id(account_id)

        book = self.profile_book(interaction, acc, socials, rankings, skin_contribs, map_creations)

        await book.send_first()
    
    @classmethod
    def format_stat(cls, animal, stat_key): 
        stat_value = animal[stat_key] 

        display_name, formatter, converter, multiplier = cls.parse_translation_format(stat_key) 

        if multiplier is not None:
            stat_value *= multiplier

        if converter is not None:
            stat_value = converter(stat_value) 
        
        # print(stat_value)

        stat_value_str = formatter.format(stat_value) 

        name = display_name.capitalize()

        return name, stat_value_str
    
    def get_translations(self, *translation_queries) -> tuple[str]:
        urls = []

        for index in range(0, len(translation_queries), 2):
            query = translation_queries[index]
            is_name = translation_queries[index + 1]

            formatter = self.CROWDL_NAME_TEMPLATE if is_name else self.CROWDL_DESC_TEMPLATE

            urls.append(formatter.format(query))
        
        results = self.async_get(*urls)

        return tuple(map(lambda response: response[0]['value'] if response else None, results))
    
    def animal_embed(self, animal): 
        animal_name = animal['name'] 
        animal_id = animal['fishLevel']

        crowdl_name, crowdl_desc = self.get_translations(animal_name, True, animal_name, False)

        title = crowdl_name or animal_name

        color = discord.Color.random() 

        if animal_name in self.CHARACTER_EXCEPTIONS: 
            image_url = self.CHARACTER_EXCEPTIONS[animal_name] 
        else: 
            image_url = self.CHARACTER_TEMPLATE.format(animal_name) 

        image_url = tools.salt_url(image_url) 

        embed = embed_utils.TrimmedEmbed(title=title, type='rich', color=color, description=crowdl_desc)

        embed.set_thumbnail(url=image_url) 

        stat_names = [] 
        stat_values = [] 

        for stat in self.NORMAL_STATS: 
            name, value = self.format_stat(animal, stat) 

            stat_names.append(name)
            stat_values.append(value) 

        animal_habitat = habitat.Habitat(animal['habitat']) 
        habitat_list = animal_habitat.convert_to_list() 

        for index in range(len(self.BIOME_STATS)): 
            stat = self.BIOME_STATS[index] 

            name, value = self.format_stat(animal, stat) 

            if index >= 1: 
                habitat_display_index = index - 1
                habitat_display = habitat_list[habitat_display_index] 
            
                value += f' ({habitat_display})' 

            stat_names.append(name)
            stat_values.append(value) 

        boost_stats = ['boosts'] 

        has_charge = animal['hasSecondaryAbility'] 

        if has_charge: 
            boost_stats.append('secondaryAbilityLoadTime') 

        for stat in boost_stats: 
            name, value = self.format_stat(animal, stat) 

            stat_names.append(name)
            stat_values.append(value) 
        
        stat_names_str = tools.make_list(stat_names, bullet_point='') 
        stat_values_str = tools.make_list(stat_values, bullet_point='') 
        
        embed.add_field(name='Stat', value=stat_names_str) 
        embed.add_field(name='Value', value=stat_values_str) 

        passives = [] 

        if animal_habitat.has_reef():
            passives.append('Reef animal (immune to slowing corals)')

        can_walk = animal['canStand'] 

        if can_walk: 
            walk_speed = animal['walkSpeedMultiplier'] 

            passives.append(f'Can walk at {walk_speed:.0%} speed') 

        for boolean in self.BOOLEANS: 
            value = animal[boolean] 

            if value: 
                boolean_list = tools.decamelcase(boolean) 

                string = tools.format_iterable(boolean_list, sep=' ').capitalize() 
            
                passives.append(string) 
        
        if passives: 
            passives_string = tools.make_list(passives) 

            embed.add_field(name='Passive abilities', value=passives_string, inline=False)
        
        embed.set_footer(text=f'''ID: {animal_id}
In-game name: {animal_name}''')
        
        return embed
    
    @task
    async def execute(self, comm, c, m, *args): 
        message_time_str = m.created_at.strftime(self.MESSAGE_LOG_TIME_FORMAT) 

        message_str = f'''Message content: {m.content}
Message author: {m.author}
Message channel: {c}
Message guild: {m.guild}
Message time: {message_time_str}''' 

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