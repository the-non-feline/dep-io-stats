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

    def get_skin_board_role(self, members_list, acc_id):
        role = None

        if members_list:
            prev_member_id = None
            reached_manager = False

            for member in members_list:
                member_id = member['id']

                # debug(member_id)

                if prev_member_id and prev_member_id > member_id:
                    reached_manager = True

                if str(member_id) == acc_id:
                    position = 'Manager' if reached_manager else 'Member'
                    role = f'Skin Board {position}'

                    break

                prev_member_id = member_id

        return role

    def get_roles(self, acc, acc_id, members_list):
        roles = []

        skin_board_role = self.get_skin_board_role(members_list, acc_id)

        if skin_board_role:
            roles.append(skin_board_role)

        if acc:
            if acc['beta']:
                roles.append(f'Beta Tester')

        return roles

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
                }, timeout=self.REQUEST_TIMEOUT)

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

                embed = embed_utils.TrimmedEmbed(title=skin_name, type='rich', description=desc, url=skin_url,
                                                 color=color)

                embed.set_author(name=f'Skin {rej_type}')

                embed.set_thumbnail(url=asset_url)
                # embed.add_field(name=f"Image link {chars.image}", value=f'[Image]({asset_url})')

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
            }, timeout=self.REQUEST_TIMEOUT)

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

<<<<<<< Updated upstream
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
    
    def map_error_embed(self):
        color = discord.Color.random() 

        embed = embed_utils.TrimmedEmbed(title="Couldn't find that map", type='rich', description="Truly unfortunate. Here's some possible \
explanations.", color=color) 

        embed.add_field(name=f"Maybe the game is not working {chars.whoopsy_dolphin}", value="It do be like that sometimes. \
The only option here is to wait until it works again.", inline=False)
        embed.add_field(name=f"Or maybe it's just being slow {chars.sleepy_shark}", value=f"I'm a bot with places to be, and I ain't got the patience \
to wait more than {self.REQUEST_TIMEOUT} seconds for a map to load. If you want to make the map load faster, you can look up the map by numeric \
ID instead of string ID.", inline=False) 
        embed.add_field(name=f"Or maybe it's a skill issue {chars.funwaa_eleseal}", value="It is also quite possible that you made a typo in your \
search.", inline=False)

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
    
=======
>>>>>>> Stashed changes
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

    def decode_mention(self, mention):
        member_id = None

        if not mention.isnumeric():
            m = re.compile(self.MENTION_REGEX).match(mention)

            if m:
                member_id = m.group('member_id')
        else:
            member_id = mention

        # debug(member_id)

        return int(member_id) if member_id is not None else None

    def decode_channel(self, c, mention):
        channel_id = None

        if not mention.isnumeric():
            m = re.compile(self.CHANNEL_REGEX).match(mention)

            if m:
                channel_id = m.group('channel_id')
        else:
            channel_id = mention

        # debug(member_id)

        return int(channel_id) if channel_id is not None else None

    async def prompt_for_message(self, c, member_id, choices=None, custom_check=lambda to_check: True, timeout=None,
                                 timeout_warning=10, default_choice=None):
        mention = '<@{}>'.format(member_id)

        extension = '{}, reply to this message with '.format(mention)

        # noinspection PyShadowingNames
        def check(to_check):
            valid_choice = choices is None or any(((to_check.content.lower() == choice.lower()) for choice in choices))

            # debug(to_check.channel.id == channel.id)
            # debug(to_check.author.id == member_id)
            # debug(valid_choice)
            # debug(custom_check(to_check))

            return to_check.channel.id == c.id and to_check.author.id == member_id and valid_choice and custom_check(
                to_check)

        to_return = None

        try:
            message = await self.wait_for('message', check=check, timeout=timeout)
        except asyncio.TimeoutError:
            await self.send(c, content='{}, time limit exceeded, going with default. '.format(mention))

            to_return = default_choice
        else:
            to_return = message.content

        return to_return

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
