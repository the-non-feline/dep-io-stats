import math
import re
from urllib import parse

import discord
import grequests
from dateutil import parser

import chars
import ds_communism
import embed_utils
import tools
import ui
from logs import debug
import ds_animals
import typing


class DSSkins(ds_communism.DSCommunism, ds_animals.DSAnimals):
    """
    Class to handle all skin-related methods
    """

    def rev_channel(self):
        c_entry = self.rev_data_table.find_one(key=self.REV_CHANNEL_KEY)

        if c_entry:
            c_id = c_entry['channel_id']

            c = self.get_channel(c_id)

            return c

    def is_sb_channel(self, channel_id: int) -> bool:
        """
        Checks whether the specified channel ID is an Artistry Guild channel
        """

        if channel_id:
            c_entry = self.sb_channels_table.find_one(channel_id=channel_id)

            return c_entry
        else:
            return False

    def skins_from_list(self, list_name: str) -> list[dict] | None:
        """
        Get the skins from the given list, which is either "approved", "pending", or "upcoming"
        """

        need_token = False

        if list_name == 'approved':
            url = self.APPROVED_SKINS_LIST_URL

        elif list_name == 'pending':
            url = self.PENDING_SKINS_LIST_URL

        elif list_name == 'upcoming':
            url = self.UPCOMING_LIST_URL
            need_token = True
        else:
            raise RuntimeError("Skin list name is not a valid choice...?")

        if need_token:
            with self.borrow_token() as token:
                req = grequests.request('GET', url, headers={
                    'authorization': f'Bearer {token}',
                }, timeout=self.REQUEST_TIMEOUT)

                return self.async_get(req)[0]
        else:
            req = url

            return self.async_get(req)[0]

    def filtered_skins_from_list(self, list_name: str, *filters) -> list[dict] | None:
        """
        Fetch the skins from the given list (approved, pending, or upcoming), and filter them through the provided
        filters
        """

        skins = self.skins_from_list(list_name)

        if skins is not None:
            filtered_skins = self.filter_skins(skins, *filters)

            return filtered_skins

    def filter_skins(self, skins_list, *filters) -> list[dict]:
        """
        Filter the skins list, leaving only the ones that pass the filters
        """

        passed_skins = []

        for skin in skins_list:
            for skin_filter in filters:
                # debug(skin_filter)

                if not skin_filter(self, skin):
                    break
            else:
                passed_skins.append(skin)

        return passed_skins

    class VoteAction:
        """
        Object to store a user's voting action (although the user themselves aren't stored)
        """

        def __init__(self, motion: dict, vote_action: str, motion_type: str, target_str: str):
            self.motion = motion
            self.vote_action = vote_action
            self.motion_type = motion_type
            self.target_str = target_str

            self.emoji = '\\' + (chars.check if vote_action == 'approve' else chars.x)

    @classmethod
    def count_votes(cls, total_motions: list[dict]) -> dict[int, list[VoteAction]]:
        """
        Compile all the votes each Artistry member has cast on the motions in the list
        """

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
    def participation_embed_template() -> embed_utils.TrimmedEmbed:
        """
        Generate the template to use for participation embeds
        """

        color = discord.Color.random()

        return embed_utils.TrimmedEmbed(title='Motion voting summary', description='A summary of how many motions \
Artistry Guild members have voted on', color=color)

    def participant_embed(self, interaction: discord.Interaction, user: dict, votes: list[VoteAction]) \
            -> ui.Page | ui.ScrollyBook:
        """
        Generate the voting summary compilation for an Artistry member
        """

        base = self.base_profile_embed(user, specific_page='Motions voted by', big_image=False)

        titles = f"Motion type {chars.folder}", f"Motion target {chars.target}", f"Vote {chars.ballot_box}"
        formatters = "{.motion_type}", "{.target_str}", "{.emoji}"

        comp = self.generic_compilation_embeds(interaction, base, 'motions', votes, titles, formatters)

        return comp

    # noinspection PyUnusedLocal
    async def display_participant_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction,
                                            message_interaction: discord.Interaction, participants: list[dict]):
        """
        Display voting summary for an Artistry member selected from the dropdown menu
        """

        first_value = menu.values[0]

        index = int(first_value)

        part_dict = participants[index]

        participant = part_dict['user']
        votes = part_dict['votes']

        await menu_interaction.response.defer(thinking=True)

        book = self.participant_embed(menu_interaction, participant, votes)

        await book.send_first()

    def participant_page_menu(self, message_interaction: discord.Interaction, participants: list[dict]) \
            -> tuple[ui.CallbackSelect, ...]:
        """
        The dropdown menu on the list of participants (Artistry members)
        """

        options = [ui.TruncatedSelectOption(label=participants[index]['username'],
                                            description="", value=index) for index in range(len(participants))]

        menu = ui.CallbackSelect(self.display_participant_from_menu, message_interaction, participants.copy(),
                                 options=options,
                                 placeholder='Choose a member')

        return (menu,)

    class MotionRepresentation:
        """
        A class that represents a motion
        """

        def __init__(self, motion: dict, title: str, upvote_ratio: float, turnout_str: str, members_list: list[dict]):
            self.motion = motion
            self.title = title
            self.upvote_ratio = upvote_ratio
            self.turnout_str = turnout_str
            self.members_list = members_list

    def motion_reprs(self, motions_list: tuple[dict, ...], members_list: list[dict]) -> list[MotionRepresentation]:
        """
        Generate the representations of the motions
        """

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

    def motion_title_and_thumb(self, motion: dict) -> tuple[str, str | None]:
        """
        Get the title and thumbnail for the motion
        """

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

    def build_participation_book(self, interaction: discord.Interaction, count_mapping: dict[int, list[VoteAction]],
                                 members_list: list[dict]) -> ui.Page | ui.ScrollyBook:
        """
        Generate the book of participation
        """

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
                        raise RuntimeError(
                            f'Vote on {vote.motion} by {member_id} that is neither an approve or a reject...?')

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
                                               artificial_limit=ui.CallbackSelect.MAX_OPTIONS,
                                               page_buttons_func=self.participant_page_menu)

        return comp

    async def send_motion_participation(self, interaction: discord.Interaction):
        """
        Send the voting summary
        """

        await interaction.response.defer()

        with self.borrow_token():
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)
            recent_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)

            pending_motions, recent_motions, members_list = self.async_get(pending_motions_request,
                                                                           recent_motions_request, list_request)

        if members_list:  # None in jsons indicates at least one request failed
            total_motions = (pending_motions or []) + (recent_motions or [])

            counts = self.count_votes(total_motions)

            book = self.build_participation_book(interaction, counts, members_list)

            await book.send_first()
        else:
            await interaction.followup.send(content='There was an error fetching members.')

    def compile_voter_map(self, existing_map: dict, voters: list[dict]):
        """
        Compile the map of user IDs to account data
        """

        requests = (self.PROFILE_TEMPLATE.format(voter['user_id']) for voter in voters if
                    voter['user_id'] not in existing_map)

        results = self.async_get(*requests)

        if results:
            for user in results:
                user_id = user['id']

                existing_map[user_id] = user['username']

    def fetch_sb_members(self) -> list[dict] | None:
        """
        Get the list of Artistry Guild members
        """

        with self.borrow_token():
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)

            return self.async_get(list_request)[0]

    def motion_embed(self, motion: dict, members: list[dict]) -> embed_utils.TrimmedEmbed:
        """
        Generate the embed for a motion
        """

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

        embed.add_field(name=f'Vote stats {chars.ballot_box}',
                        value=f'{upvote_ratio}% upvoted, {turnout_str}% voter turnout',
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

    # noinspection PyUnusedLocal
    async def display_motion_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction,
                                       message_interaction: discord.Interaction, motions: list[MotionRepresentation]):
        """
        Callback to display a motion from the dropdown menu of motions
        """

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
        """
        Generate the dropdown menu to select a motion
        """

        options = [ui.TruncatedSelectOption(label=motions[index].title,
                                            description="", value=index) for index in range(len(motions))]

        menu = ui.CallbackSelect(self.display_motion_from_menu, message_interaction, motions.copy(), options=options,
                                 placeholder='Choose a motion')

        return (menu,)

    def motions_page(self, interaction: discord.Interaction, motions_list: tuple[dict], members_list: list[dict],
                     active: bool) -> ui.Page | ui.ScrollyBook:
        """
        Generate the book of motions for a given category

        active: Display pending motions if True, else display recent motions
        """

        title = 'Pending' if active else 'Recent'
        color = discord.Color.random()
        template = embed_utils.TrimmedEmbed(title=f'{title} motions', color=color)

        motion_reprs = self.motion_reprs(motions_list, members_list)

        titles = f'Motion {chars.scroll}', f'Upvote ratio {chars.thumbsup}', f'Turnout {chars.ballot_box}'
        formatters = '{.title}', '{.upvote_ratio:.0%}', '{.turnout_str}'

        return self.generic_compilation_embeds(interaction, template, 'motions', motion_reprs, titles, formatters,
                                               artificial_limit=ui.CallbackSelect.MAX_OPTIONS,
                                               page_buttons_func=self.motions_page_menu)

    async def motions_book(self, interaction: discord.Interaction):
        """
        Generate and send the book of motions, both pending and recent
        """

        await interaction.response.defer()

        with self.borrow_token():
            pending_motions_request = grequests.request('GET', self.PENDING_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)
            recent_motions_request = grequests.request('GET', self.RECENT_MOTIONS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)
            list_request = grequests.request('GET', self.SKIN_BOARD_MEMBERS_URL, headers={
                'Authorization': f'Bearer {self.token}',
            }, timeout=self.REQUEST_TIMEOUT)

            pending_motions, recent_motions, members_list = self.async_get(pending_motions_request,
                                                                           recent_motions_request, list_request)

        pending_motions = pending_motions or ()
        recent_motions = recent_motions or ()

        pending_page = self.motions_page(interaction, pending_motions, members_list, True)
        recent_page = self.motions_page(interaction, recent_motions, members_list, False)

        book = ui.IndexedBook(interaction, ('Pending motions', pending_page), ('Recent motions', recent_page))

        await book.send_first()

    def unbalanced_stats(self, skin) -> tuple[bool, str | None]:
        """
        Determines whether a skin has broken and/or unbalanced stats

        Returns a boolean: whether the stats are broken, followed by the unbalance sign, or None if there is no
        unbalance
        """

        broken = False
        unbalanced = False
        prev_sign = None

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

    def generate_stat_changes(self, stat_changes, animal) -> list[str]:
        """
        Generate an array of string representations of stat changes
        """

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

    def calc_change_result(self, converter: typing.Callable[[int | float], int | float], attr_name: str,
                           old_value: float, diff: str) -> tuple[int | float, bool]:
        """
        Calculate the result of a stat change, and return the new result and whether it's broken or not
        """

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

    def reject_reasons(self, skin: dict, check_reddit=True) -> list[str]:
        """
        Return a list of reasons to reject a skin
        """

        reasons = []

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

    def valid_reddit_link(self, link: str) -> typing.Match[str] | None:
        """
        Return whether a Reddit link is valid or not (returns a typing.Match if valid, None otherwise)
        """

        m = re.compile(self.REDDIT_LINK_REGEX).match(link)

        return m

    def inspect_skins(self, review_list: list[dict]) -> tuple[list[dict], list[list[str]]]:
        """
        Review all skins and return lists of rejected skins and corresponding rejection reasons
        """

        rejected = []
        reasons = []

        for skin in review_list:
            rej_reasons = self.reject_reasons(skin)

            if rej_reasons:
                rejected.append(skin)
                reasons.append(rej_reasons)

                # debug(rejected)
        # debug(reasons)

        return rejected, reasons

    def add_stat_changes(self, embed: embed_utils.TrimmedEmbed, stat_changes: str, animal: dict):
        """
        Tack the stat changes string onto the embed
        """

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

    def mass_motion_requests(self, to_motion: list[dict], approve: bool) -> list[str]:
        """
        Mass motions the given list of skins, and return a list of strings of skins that failed
        """

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

                request = grequests.request('POST', self.MOTION_CREATION_URL, data=payload, headers=headers,
                                            timeout=self.REQUEST_TIMEOUT)

                ids_and_versions.append((skin_id, skin_version))
                requests.append(request)

            # debug(requests)

            results = self.async_get(*requests)

            # results = [None] * len(to_motion)

        failure_descs = []

        for index in range(len(results)):
            skin_id, version = ids_and_versions[index]
            result = results[index]

            if not result:
                failure_descs.append(f'{skin_id} (version {version})')

        return failure_descs

    async def mass_motion(self, interaction: discord.Interaction, to_motion: list[dict], approve: bool):
        """
        Mass-motion the specified skins
        """

        await interaction.response.defer(thinking=True)

        failures = self.mass_motion_requests(to_motion, approve)

        failures_str = tools.format_iterable(failures)

        motion_type = 'approval' if approve else 'removal'

        await interaction.followup.send(
            content=f'Motioned {len(to_motion)} skins for {motion_type}, {len(failures)} failures: {failures_str}')

    async def approved_display_button_callback(self, button: ui.CallbackButton, button_interaction: discord.Interaction,
                                               message_interaction: discord.Interaction, skins: list[dict],
                                               approve: bool):
        """
        Callback for when the motion buttons on a skin are pressed
        """

        await self.mass_motion(button_interaction, skins, approve)

    def approved_display_buttons(self, interaction: discord.Interaction, skins: tuple[dict, ...], actual_type: str,
                                 multi: bool) -> tuple[ui.CallbackButton] \
                                                 | tuple[ui.CallbackButton, ui.CallbackButton] | tuple[()]:
        """
        Generate the motion buttons on the skin and skin list embeds
        """

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

    @staticmethod
    def skin_search_base_embed(actual_type: str, description: str, filter_names_str: str) \
            -> tuple[embed_utils.TrimmedEmbed, tuple[embed_utils.Field] | tuple[()]]:
        """
        Generate the base embed for all skin list display

        Returns the embed and a tuple of fields to tack onto the embed
        """

        color = discord.Color.random()

        embed = embed_utils.TrimmedEmbed(title=f'{actual_type.capitalize()} skin search', description=description,
                                         color=color)

        if filter_names_str:
            tacked_fields = (embed_utils.Field(name=f'Filters used {chars.magnifying_glass}', value=filter_names_str,
                                               inline=False),)
        else:
            tacked_fields = ()

        return embed, tacked_fields

    def skin_page_menu(self, message_interaction: discord.Interaction, possible_skins: list[dict]) \
            -> tuple[ui.CallbackSelect]:
        """
        Generate the dropdown menu for the skins list
        """

        options = [ui.TruncatedSelectOption(label=possible_skins[index]['name'],
                                            description=f"ID: {possible_skins[index]['id']}", value=index) for index in
                   range(len(possible_skins))]

        menu = ui.CallbackSelect(self.display_skin_from_menu, message_interaction, possible_skins.copy(),
                                 options=options,
                                 placeholder='Choose a skin')

        return (menu,)

    async def approved_display(self, interaction: discord.Interaction, actual_type, filter_names_str, filters):
        """
        Generate and display the skins list
        """

        if actual_type == 'approved':
            description = f'These skins are in the [Approved section]({self.APPROVED_PAGE}) of the Creators Center. \
They are also in the [Store]({self.STORE_PAGE}) (when they are available to buy).'

        elif actual_type == 'pending':
            description = f'These skins are in the [Pending section]({self.PENDING_PAGE}) of the Creators Center.'

        elif actual_type == 'upcoming':
            description = f'These skins are in the [Upcoming section]({self.UPCOMING_PAGE}) of the Creators Center.'
        else:
            description = ''

        approved = self.filtered_skins_from_list(actual_type, *filters)

        embed_template, tacked_fields = self.skin_search_base_embed(actual_type, description, filter_names_str)

        buttons = self.approved_display_buttons(interaction, approved, actual_type, True)

        display = self.generic_compilation_embeds(interaction, embed_template, 'skins found', approved,
                                                  (f'Skin {chars.SHORTCUTS.skin_symbol}', f'ID {chars.folder}',
                                                   f'Price {chars.deeeepcoin}'),
                                                  (self.SKIN_EMBED_LINK_FORMATTER, '{[id]}', '{[price]:,}'),
                                                  aggregate_names=(chars.deeeepcoin, 'sales'),
                                                  aggregate_attrs=('price', 'sales'), tacked_fields=tacked_fields,
                                                  extra_buttons=buttons,
                                                  page_buttons_func=self.skin_page_menu,
                                                  artificial_limit=ui.CallbackSelect.MAX_OPTIONS)

        await display.send_first()

    def skin_embed_pages(self, interaction: discord.Interaction, skin: dict, status: dict,
                         skin_embed: embed_utils.TrimmedEmbed,
                         extra_assets: dict[str, dict]) -> ui.Page | ui.IndexedBook:
        """
        Generate the pages for the skin embed
        """

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

    def skin_embed(self, interaction: discord.Interaction, skin: dict, direct_api=False) -> ui.Page | ui.IndexedBook:
        """
        Generate the skin embed/book
        """

        color = discord.Color.random()

        stat_changes = skin['attributes']
        when_created = skin['created_at']
        animal_id = skin['fish_level']
        skin_id = skin['id']
        price = skin['price']
        sales = skin['sales']
        last_updated = skin['updated_at']
        version = skin['version']

        store_page = self.SKIN_STORE_PAGE_TEMPLATE.format(skin_id)

        asset_name = skin['asset']

        animal = self.find_animal_by_id(animal_id)

        animal_name = animal['name']

        status = {
            attr: None for attr in self.SKIN_STATUS_ATTRS
        }

        if not direct_api:
            id_and_version = f'{skin_id}/{version}'

            skin_url = self.SKIN_URL_TEMPLATE.format(id_and_version)

            skin_json = self.async_get(skin_url)[0]
        else:
            skin_json = skin

        def get(attribute: str):
            if attribute in skin:
                return skin[attribute]
            elif skin_json:
                return skin_json[attribute]
            else:
                return None

        desc = get('description')

        extra_assets = get('assets_data')

        # debug(desc)

        reddit_link = get('reddit_link')
        category = get('category')
        season = get('season')
        usable = get('usable')

        user = get('user')

        for attr in self.SKIN_STATUS_ATTRS:
            status[attr] = get(attr)

        # debug(desc)

        embed = embed_utils.TrimmedEmbed(title=skin['name'], description=desc, color=color, url=store_page)

        if asset_name[0].isnumeric():
            template = self.CUSTOM_SKIN_ASSET_URL_TEMPLATE
        else:
            template = self.SKIN_ASSET_URL_TEMPLATE

        asset_url = template.format(asset_name)

        debug(asset_url)

        embed.set_image(url=asset_url)

        # animal_name = self.get_animal(animal_id)

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
            if status_value is None:
                emoji = chars.question_mark
            elif status_value:
                emoji = chars.check
            else:
                emoji = chars.x

            status_str = f'`{emoji}` {status_attr.capitalize()}'

            status_strs.append(status_str)

        status_list_str = tools.make_list(status_strs, bullet_point='')

        embed.add_field(name=f"Creators Center status {chars.magnifying_glass}", value=status_list_str, inline=False)

        reject_reasons = self.reject_reasons(skin, check_reddit=False)

        if reject_reasons:
            reasons_str = tools.make_list(reject_reasons)

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

        embed.set_footer(text=f"ID: {skin_id}")

        pages = self.skin_embed_pages(interaction, skin, status, embed, extra_assets)

        return pages

    async def skin_by_id(self, interaction: discord.Interaction, skin_id: str, version: int):
        """
        Display a skin by its ID, or display an error if it's not found or not displayable
        """

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
                await interaction.followup.send(
                    content=f"You can only view approved or pending skins in this channel. Use this in a Skin Board \
channel to bypass this restriction.")
        else:
            await interaction.followup.send(content=f"That's not a skin. Maybe your ID and/or version are wrong.")

    async def display_skin_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction,
                                     message_interaction: discord.Interaction, possible_skins: list[dict]):
        """
        Display a skin from the dropdown menu
        """

        first_value = menu.values[0]

        index = int(first_value)

        skin = possible_skins[index]

        await menu_interaction.response.defer(thinking=True)

        book = self.skin_embed(menu_interaction, skin)

        await book.send_first()

        async def skin_by_name(self, interaction: discord.Interaction, skin_name, list_name: str):
            await interaction.response.defer()

            skins_list = self.skins_from_list(list_name)

            if skins_list:
                skin_suggestions = await self.search_with_suggestions(interaction, 'skins',
                                                                      (f'Skin {chars.SHORTCUTS.skin_symbol}',
                                                                       f'ID {chars.folder}'),
                                                                      ('{[name]}', '{[id]}'),
                                                                      skins_list, lambda skin: skin['name'], skin_name,
                                                                      self.skin_page_menu)

                if skin_suggestions:
                    promises = map(lambda suggestion: ui.Promise(self.skin_embed, interaction, suggestion),
                                   skin_suggestions)

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
