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
import json

import logs
from logs import debug
import tools
import commands
from chars import c
import trimmed_embed
import reports
import habitat
import ds_constants

class DS(ds_constants.DS_Constants, discord.Client): 
    def __init__(self, logs_file_name, storage_file_name, animals_file_name, email, password): 
        self.email = email
        self.password = password

        self.db = dataset.connect(storage_file_name) 
        self.links_table = self.db.get_table('account_links') 
        self.prefixes_table = self.db.get_table('prefixes') 
        self.rev_data_table = self.db.get_table('rev_data') 
        self.blacklists_table = self.db.get_table('blacklists') 
        self.sb_channels_table = self.db.get_table('sb_channels') 

        self.logs_file = open(logs_file_name, mode='w+', encoding='utf-8') 
        self.animals_file_name = animals_file_name

        self.ANIMAL_FILTERS = {} 

        self.set_animal_stats() 

        handler = logging.StreamHandler(self.logs_file) 

        logs.logger.addHandler(handler) 

        #self.levels_file = open(levels_file_name, mode='r') 

        self.tasks = 0
        self.logging_out = False

        self.readied = False
        self.token = None

        self.auto_rev_process = None

        super().__init__(activity=discord.Game(name='starting up'), status=discord.Status.dnd) 
    
    def animal_stats(self): 
        with open(self.animals_file_name, mode='r') as file: 
            return json.load(file) 
    
    @staticmethod
    def animal_check(target_id): 
        def check(self, skin): 
            animal = skin['fish_level'] 

            return animal == target_id
        
        return check
    
    def set_animal_stats(self): 
        self.temp_animal_stats = self.animal_stats() 

        self.ANIMAL_FILTERS.clear() 

        for index in range(len(self.temp_animal_stats)): 
            stats = self.temp_animal_stats[index] 

            name = stats['name'] 
            animal_id = index

            self.ANIMAL_FILTERS[name] = self.animal_check(animal_id) 

        debug('set animal stats') 
    
    def find_animal(self, animal_id): 
        stats = self.temp_animal_stats

        return stats[animal_id] 
    
    def prefix(self, c): 
        p = self.prefixes_table.find_one(guild_id=c.guild.id) 
        
        if p: 
            return p['prefix'] 
        else: 
            return self.DEFAULT_PREFIX
    
    def blacklisted(self, c, blacklist_type, target): 
        b_entry = self.blacklists_table.find_one(guild_id=c.guild.id, type=blacklist_type, target=target) 

        return b_entry
    
    def rev_channel(self): 
        c_entry = self.rev_data_table.find_one(key=self.REV_CHANNEL_KEY) 

        if c_entry: 
            c_id = c_entry['channel_id'] 

            c = self.get_channel(c_id) 

            return c
    
    def is_sb_channel(self, channel_id): 
        c_entry = self.sb_channels_table.find_one(channel_id=channel_id) 

        return c_entry
    
    async def send(self, c, *args, **kwargs): 
        try: 
            return await c.send(*args, **kwargs) 
        except discord.errors.Forbidden: 
            debug('that was illegal') 
    
    async def logout(self): 
        if self.auto_rev_process: 
            self.auto_rev_process.cancel() 
        
        await self.change_presence(status=discord.Status.offline)
        
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
            if self.is_sb_channel(c.id): 
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
    
    def filter_skins(self, channel, skins_list, *filters): 
        passed_skins = [] 
        trimmed_str = None

        should_trim = not self.is_sb_channel(channel.id) 

        for skin in skins_list: 
            debug('checking skin') 

            filtered_len = len(passed_skins) 

            if should_trim and filtered_len == self.SEARCH_LIMIT: 
                trimmed_str = f'***Search limited to {self.SEARCH_LIMIT} results. Perform the search in a Skin Board channel to display the full results.***' 

                break
            
            for skin_filter in filters: 
                if not skin_filter(self, skin): 
                    break
            else: 
                passed_skins.append(skin) 
        
        return passed_skins, trimmed_str
        
    def get_pending_skins(self, channel, *filters): 
        self.get_review_token() 

        pending_motions = rejected_motions = None
        
        if self.token: 
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            rejected_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            pending_list, pending_motions, rejected_motions = self.async_get(self.PENDING_SKINS_LIST_URL, pending_motions_request, rejected_motions_request) 
        else: 
            pending_list = self.async_get(self.PENDING_SKINS_LIST_URL)[0] 

        unnoticed_pending = None
        upcoming_pending = None
        motioned_pending = None
        rejected_pending = None

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
            
            filtered_skins, trimmed_str = self.filter_skins(channel, pending_list, *filters) 

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
        
        return unnoticed_pending, upcoming_pending, motioned_pending, rejected_pending, trimmed_str
    
    def get_approved_skins(self, channel, *filters): 
        filtered_skins = None
        trimmed_str = None

        approved = self.async_get(self.SKINS_LIST_URL)[0] 

        if approved is not None: 
            filtered_skins, trimmed_str = self.filter_skins(channel, approved, *filters) 

        return filtered_skins, trimmed_str
    
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
            elif len(suggestions) == self.MAX_SKIN_SUGGESTIONS: 
                return None
            elif lowered_query in lowered_name: 
                suggestions.append(skin) 
        else: 
            return suggestions
    
    @staticmethod
    def count_votes(total_motions): 
        mapping = {} 

        for motion in total_motions: 
            votes = motion['votes'] 

            for vote in votes: 
                user_id = vote['user_id'] 
                vote_action = vote['action'] 

                if user_id not in mapping: 
                    mapping[user_id] = [] 
                
                mapping[user_id].append(vote_action) 
        
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
    
    def build_participation_report(self, report, count_mapping, members_list): 
        voted_strs = [] 
        non_voted_strs = [] 

        for member in members_list: 
            name = member['name'] 
            username = member['username'] 
            member_id = member['id'] 

            if member_id in count_mapping: 
                votes = count_mapping[member_id] 

                approves = votes.count('approve') 
                rejects = votes.count('reject') 
                total_votes = len(votes) 

                member_str = f'{name} (@{username}) | {total_votes} votes ({approves} approved, {rejects} rejected)' 

                voted_strs.append(member_str) 
            else: 
                member_str = f'{name} (@{username})' 

                non_voted_strs.append(member_str) 
        
        report.add('__**Member Participation Report**__') 

        voted_length = len(voted_strs) 

        report.add(f"**Voted recently ({voted_length}) {c['ballot_box']}**") 
        self.build_participation_section(report, voted_strs) 

        non_voted_length = len(non_voted_strs) 

        report.add(f"**Didn't vote recently ({non_voted_length}) {c['x']}**") 
        self.build_participation_section(report, non_voted_strs) 
    
    def get_motion_participation(self, report): 
        self.get_review_token() 

        members_list = None

        if self.token: 
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            recent_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}', 
            }) 

            jsons = self.async_get(pending_motions_request, recent_motions_request, list_request) 

            if None not in jsons: # None in jsons indicates at least one request failed
                pending_motions, recent_motions, members_list = jsons

                total_motions = (pending_motions or []) + (recent_motions or []) 

                counts = self.count_votes(total_motions) 

                self.build_participation_report(report, counts, members_list) 
            else: 
                report.add('There was an error fetching motions and/or members.') 
    
    async def send_participation_report(self, c): 
        r = reports.Report(self, c) 

        self.get_motion_participation(r) 

        await r.send_self() 
    
    def unbalanced_stats(self, skin): 
        broken = False
        unbalanced = False

        stat_changes = skin['attributes'] 

        if stat_changes: 
            unbalanced = True

            split_changes = stat_changes.split(';') 

            prev_sign = None

            for change_str in split_changes: 
                split = change_str.split('=') 

                if len(split) == 2: 
                    stat, value = split

                    sign = value[0] 
                    abs_value = value[1:] 

                    m = re.compile(self.FLOAT_CHECK_REGEX).match(value) 

                    if not m: 
                        broken = True

                        debug(f'{value} failed regex') 

                    if stat not in self.STATS_UNBALANCE_BLACKLIST: 
                        if prev_sign and prev_sign != sign: 
                            unbalanced = False
                        
                        prev_sign = sign
                else: 
                    broken = True

                    debug(f'{change_str} is invalid')
        
        unbalance_sign = prev_sign if unbalanced else None

        debug(broken) 
        debug(unbalance_sign) 

        return broken, unbalance_sign
    
    def valid_reddit_link(self, link): 
        m = re.compile(self.REDDIT_LINK_REGEX).match(link) 

        return m
    
    def reject_reasons(self, skin, check_reddit=True): 
        reasons = [] 

        skin_name = skin['name'] 
        skin_id = skin['id'] 

        skin_url = self.SKIN_URL_TEMPLATE.format(skin_id) 

        debug(f'{skin_name}: {skin_url}') 

        if check_reddit: 
            reddit_link = skin['reddit_link']

            if not reddit_link: 
                reasons.append('missing Reddit link') 
            elif not self.valid_reddit_link(reddit_link): 
                reasons.append('invalid Reddit link') 
        
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
                
                creator = skin['user'] 
                c_name = creator['name'] 
                c_username = creator['username'] 
                c_str = f'{c_name} (@{c_username})' 

                embed = trimmed_embed.TrimmedEmbed(title=skin_name, type='rich', description=desc, url=skin_url, color=color) 

                embed.set_author(name=f'Skin {rej_type}') 

                embed.set_thumbnail(url=asset_url) 
                #embed.add_field(name=f"Image link {c['image']}", value=f'[Image]({asset_url})') 

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
        r = reports.Report(self, c) 

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

        embed.add_field(name=f"Public commands {c['scroll']}", value=com_list, inline=False) 

        embed.set_footer(text=f'Used by {user_count} users across {guild_count} guilds') 

        return embed
    
    @classmethod
    def parse_translation_format(cls, key): 
        translation_format = cls.STAT_FORMATS[key] 

        display_name, formatter, *rest = translation_format

        converter = tools.trunc_float
        multiplier = 1

        if rest: 
            element = rest[0] 

            if type(element) in (float, int): 
                multiplier = element
            else: 
                converter = element
        
        return display_name, formatter, converter, multiplier
    
    def add_stat_changes(self, embed, stat_changes, animal): 
        stat_changes_list = [] 

        for change in stat_changes.split(';'): 
            split = change.split('=') 

            if len(split) == 2: 
                attribute, diff = split

                key = self.STAT_CHANGE_TRANSLATIONS.get(attribute, None) 

                if key: 
                    display_name, formatter, converter, multiplier = self.parse_translation_format(key) 

                    old_value = animal[key] * multiplier

                    old_value_converted = converter(old_value) 

                    old_value_str = formatter.format(old_value_converted) 

                    m = re.compile(self.FLOAT_CHECK_REGEX).match(diff) 

                    if m: 
                        float_diff = float(diff) 

                        new_value = old_value + float_diff

                        new_value_converted = converter(new_value) 
                        
                        new_value_str = formatter.format(new_value_converted) 
                    else: 
                        new_value_str = f'invalid ({diff})' 

                    change_str = f'**{display_name}:** {old_value_str} **->** {new_value_str}' 
                else: 
                    change_str = f'Untranslated change: {change}' 
            else: 
                change_str = f'Invalid change: {change}' 
            
            stat_changes_list.append(change_str) 
        
        stat_changes_str = tools.make_list(stat_changes_list)  

        embed.add_field(name=f"Stat changes {c['change']}", value=stat_changes_str, inline=False) 
        
    def skin_embed(self, skin, direct_api=False): 
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

        asset_name = skin['asset'] 

        animal = self.find_animal(animal_id) 

        animal_name = animal['name'] 

        desc = None
        extra_assets = None
        reddit_link = None
        category = None
        season = None
        usable = None

        user = None

        if not direct_api: 
            skin_url = self.SKIN_URL_TEMPLATE.format(ID) 

            skin_json = self.async_get(skin_url)[0] 
        else: 
            skin_json = skin

        if skin_json: 
            desc = skin_json['description'] 

            extra_assets = skin_json['assets_data'] 

            #debug(desc) 

            reddit_link = skin_json['reddit_link'] 
            category = skin_json['category'] 
            season = skin_json['season'] 
            usable = skin_json['usable'] 

            user = skin_json['user'] 

        #debug(desc) 

        embed = trimmed_embed.TrimmedEmbed(title=skin['name'], description=desc, color=color, url=reddit_link) 

        if asset_name[0].isnumeric(): 
            asset_name = self.CUSTOM_SKIN_ASSET_URL_ADDITION + asset_name

        asset_url = tools.salt_url(self.SKIN_ASSET_URL_TEMPLATE.format(asset_name)) 

        debug(asset_url) 

        embed.set_image(url=asset_url) 

        #animal_name = self.get_animal(animal_id) 

        embed.add_field(name=f"Animal {c['fish']}", value=animal_name) 
        embed.add_field(name=f"Price {c['deeeepcoin']}", value=f'{price:,}') 

        sales_emoji = c['stonkalot'] if sales >= self.STONKS_THRESHOLD else c['stonkanot'] 

        embed.add_field(name=f"Sales {sales_emoji}", value=f'{sales:,}') 

        if stat_changes: 
            self.add_stat_changes(embed, stat_changes, animal) 

        if category: 
            embed.add_field(name=f"Category {c['folder']}", value=category) 

        if season: 
            embed.add_field(name=f"Season {c['calendar']}", value=season) 
        
        if usable is not None: 
            usable_emoji = c['check'] if usable else c['x'] 

            embed.add_field(name=f"Usable {usable_emoji}", value=usable) 
        
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
        
        if extra_assets: 
            urls_list = [] 

            for asset_type, asset_data in extra_assets.items(): 
                asset_filename = asset_data['asset'] 

                if asset_filename[0].isnumeric(): 
                    asset_filename = self.CUSTOM_SKIN_ASSET_URL_ADDITION + asset_filename
                
                extra_asset_url = self.SKIN_ASSET_URL_TEMPLATE.format(asset_filename) 

                urls_list.append(f'[{asset_type}]({extra_asset_url})') 
            
            extra_assets_str = tools.make_list(urls_list) 

            embed.add_field(name=f"Additional assets {c['palette']}", value=extra_assets_str, inline=False) 

        if user: 
            user_name = user['name']
            user_username = user['username'] 
            user_pfp = user['picture'] 

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
        locked = map_json['locked'] 

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
        
        lock_emoji = c['lock'] if locked else c['unlock'] 
        
        embed.add_field(name=f"Locked {lock_emoji}", value=locked) 

        if tags_list: 
            tags_str = tools.format_iterable(tags_list, formatter='`{}`') 

            embed.add_field(name=f"Tags {c['label']}", value=tags_str, inline=False) 

        embed.set_footer(text=f'''ID: {ID}
String ID: {string_id}''') 

        return embed
    
    def skin_str_list(self, r, skin_list): 
        for skin in skin_list: 
            name = skin['name'] 
            ID = skin['id'] 
            version = skin['version'] 
            animal_id = skin['fish_level'] 
            animal = self.find_animal(animal_id) 
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

        pending, upcoming, motioned, rejected, trimmed_str = self.get_pending_skins(r.channel, *filters) 

        r.add(f'**__Pending skins with filters {filter_names_str}__**') 
        
        r.add(f"**Unnoticed skins ({self.rl(pending)}) {c['ghost']}**") 
        self.build_skins_report(r, pending) 

        r.add(f"**Upcoming skins ({self.rl(upcoming)}) {c['clock']}**") 
        self.build_skins_report(r, upcoming) 
        
        r.add(f"**Skins in motion ({self.rl(motioned)}) {c['ballot_box']}**") 
        self.build_skins_report(r, motioned) 
        
        r.add(f"**Recently rejected skins ({self.rl(rejected)}) {c['x']}**") 
        self.build_skins_report(r, rejected) 

        if trimmed_str: 
            r.add(trimmed_str) 
    
    async def approved_display(self, r, filter_names_str, filters): 
        approved, hidden_str = self.get_approved_skins(r.channel, *filters) 
        
        approved_length = self.rl(approved) 

        r.add(f"**__Approved skins with filters {filter_names_str}__ ({approved_length})** {c['check']}") 
        
        self.build_skins_report(r, approved) 

        if hidden_str: 
            r.add(hidden_str) 
    
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
        
        await self.change_presence(activity=discord.Game(name='all systems operational'), status=discord.Status.online)
        
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
    
    def convert_target(self, lower_type, target_str): 
        if lower_type == 'user': 
            target = self.decode_mention(c, target_str) 
        elif lower_type == 'account': 
            target = int(target_str) if target_str.isnumeric() else None
        elif lower_type == 'map': 
            target = int(target_str) if target_str.isnumeric() else None
        else: 
            target = None
        
        return target
    
    def get_map_string_id(self, query): 
        m = re.compile(self.MAP_REGEX).match(query)

        if m: 
            map_string_id = m.group('map_string_id') 

            return map_string_id
        
        #debug(map_id) 
    
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
        acc_id = self.get_acc_id(query) 
        
        if acc_id is not None: 
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
    
    @classmethod
    def format_stat(cls, animal, stat_key): 
        stat_value = animal[stat_key] 

        display_name, formatter, converter, multiplier = cls.parse_translation_format(stat_key) 

        stat_value *= multiplier
        stat_value = converter(stat_value) 

        stat_value_str = formatter.format(stat_value) 

        name = display_name.capitalize()

        return name, stat_value_str
    
    @classmethod
    def animal_embed(cls, animal): 
        animal_name = animal['name'] 

        title = f'Animal stats - {animal_name.capitalize()}' 
        color = discord.Color.random() 

        if animal_name in cls.CHARACTER_EXCEPTIONS: 
            image_url = cls.CHARACTER_EXCEPTIONS[animal_name] 
        else: 
            image_url = cls.CHARACTER_TEMPLATE.format(animal_name) 

        image_url = tools.salt_url(image_url) 

        embed = discord.Embed(title=title, type='rich', color=color)

        embed.set_thumbnail(url=image_url) 

        stat_names = [] 
        stat_values = [] 

        for stat in cls.NORMAL_STATS: 
            name, value = cls.format_stat(animal, stat) 

            stat_names.append(name)
            stat_values.append(value) 

        animal_habitat = habitat.Habitat(animal['habitat']) 
        habitat_list = animal_habitat.convert_to_list() 

        for index in range(len(cls.BIOME_STATS)): 
            stat = cls.BIOME_STATS[index] 

            name, value = cls.format_stat(animal, stat) 

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
            name, value = cls.format_stat(animal, stat) 

            stat_names.append(name)
            stat_values.append(value) 
        
        stat_names_str = tools.make_list(stat_names, bullet_point='') 
        stat_values_str = tools.make_list(stat_values, bullet_point='') 
        
        embed.add_field(name='Stat', value=stat_names_str) 
        embed.add_field(name='Value', value=stat_values_str) 

        passives = [] 

        can_walk = animal['canStand'] 

        if can_walk: 
            walk_speed = animal['walkSpeedMultiplier'] 

            passives.append(f'Can walk at {walk_speed:.0%} speed') 

        for boolean in cls.BOOLEANS: 
            value = animal[boolean] 

            if value: 
                boolean_list = tools.decamelcase(boolean) 

                string = tools.format_iterable(boolean_list, sep=' ').capitalize() 
            
                passives.append(string) 
        
        if passives: 
            passives_string = tools.make_list(passives) 

            embed.add_field(name='Passive abilities', value=passives_string, inline=False) 
        
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