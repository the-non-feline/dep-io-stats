import discord
from dateutil import parser

import chars
import ds_communism
import embed_utils
import tools
from logs import debug
import re
import ui


class DSAccs(ds_communism.DSCommunism):
    """
    Class to handle all methods related to Deeeep.io accounts
    """

    def get_acc_data(self, acc_id: str) -> dict | None:
        """
        Get account JSON data for the Deeeep.io account with the given ID
        """

        url = self.DATA_URL_TEMPLATE.format(acc_id)

        return self.async_get(url)[0]

    def get_true_username(self, query: str) -> str | None:
        """
        Extract the username from the query, which is either a username or a profile page URL
        """

        m = re.compile(self.PROFILE_PAGE_REGEX).match(query)

        if m:
            username = m.group('username')

            return username

    def get_profile_by_username(self, username: str) \
            -> tuple[dict | None, list | tuple | None, dict | None, list | tuple | None, dict | None]:
        """
        Fetch profile data based on the given username
        """

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

            socials, rankings, skin_contribs, map_creations = self.async_get(socials_url, rankings_url,
                                                                             skin_contribs_url, map_creations_url)
        else:
            socials = skin_contribs = ()
            rankings = map_creations = {}

        return acc_json, socials, rankings, skin_contribs, map_creations

    def generate_socials(self, socials: list[dict]) -> str:
        """
        Return the socials string
        """

        mapped = []

        for social in socials:
            platform = social['platform_id']
            display = social['platform_user_id']
            verified = social['verified']
            given_url = social['platform_user_url']

            verified_text = ' ' + chars.verified if verified else ''

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

    @staticmethod
    def profile_error_embed() -> embed_utils.TrimmedEmbed:
        """
        Generate the embed for when the profile is not found
        """

        color = discord.Color.random()

        embed = embed_utils.TrimmedEmbed(title='Invalid account', type='rich', description="You have been trolled",
                                         color=color)

        embed.add_field(name="Why?", value="""This usually happens when you have skill issue and entered an invalid \
user on the `hackprofile` command. 

But it could also mean the game is down, especially if it happens on the `profile` command.""", inline=False)
        embed.add_field(name="What now?", value="If this is because you made a mistake, just git gud in the future. \
If the game is down, nothing you can do but wait.", inline=False)

        return embed

    def profile_embed(self, acc: dict, socials: list[dict]) -> embed_utils.TrimmedEmbed:
        """
        Generate the first page of the profile book
        """

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
            embed.add_field(name=f"Social links {chars.speech_bubble}", value=self.generate_socials(socials),
                            inline=False)

        embed.add_field(name=f"Profile views {chars.eyes}", value=f'{views:,}')

        return embed

    def rankings_embed(self, acc: dict, rankings: dict) -> embed_utils.TrimmedEmbed:
        """
        Generate the rankings embed
        """

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

    def get_profile_by_id(self, acc_id: int) \
            -> tuple[dict | None, list | None, dict | None, list | None, dict | None]:
        """
        Fetch the profile information for the account with the given ID
        """

        acc_url = self.DATA_URL_TEMPLATE.format(acc_id)
        social_url = self.SOCIALS_URL_TEMPLATE.format(acc_id)
        rankings_url = self.RANKINGS_TEMPLATE.format(acc_id)
        skin_contribs_url = self.SKIN_CONTRIBS_TEMPLATE.format(acc_id)
        map_creations_url = self.MAP_CONTRIBS_TEMPLATE.format(acc_id)

        # noinspection PyTypeChecker
        return self.async_get(acc_url, social_url, rankings_url, skin_contribs_url, map_creations_url)

    def profile_embed_by_username(self, username: str):
        """
        Generate the profile embed (first page) for the account with the given username
        """

        return self.profile_embed(*self.get_profile_by_username(username))

    def profile_embed_by_id(self, acc_id: int):
        """
        Generate the profile embed (first page) for the account with the given ID
        """

        return self.profile_embed(*self.get_profile_by_id(acc_id))

    def get_acc_id(self, query: str):
        """
        Fetch an account ID from a query string
        """

        acc_id = None

        if query.isnumeric():
            acc_id = query
        else:
            m = re.compile(self.PFP_REGEX).match(query)

            if m:
                acc_id = m.group('acc_id')

        return acc_id

    def search_by_username(self, username: str):
        """
        Fetch an account by username (or profile URL)
        """

        search_url = self.USERNAME_SEARCH_TEMPLATE.format(username)

        return self.async_get(search_url)[0]

    def search_by_id_or_username(self, query: str):
        """
        Fetch an account by ID, username, or profile URL
        """

        acc_data = None

        true_username = self.get_true_username(query)

        if true_username is not None:
            acc_data = self.search_by_username(true_username)

        if acc_data is None:
            acc_id = self.get_acc_id(query)

            if acc_id is not None:
                acc_data = self.get_acc_data(acc_id)

        return acc_data

    def get_socials(self, account_id: int):
        """
        Fetch the list of socials for the account with the given ID
        """

        socials_url = self.SOCIALS_URL_TEMPLATE.format(account_id)

        return self.async_get(socials_url)[0] or ()

    def connect_help_book(self, interaction: discord.Interaction):
        """
        Generate the instruction book for linking accounts
        """

        signin_embed = discord.Embed(title='Sign in to your Deeeep.io account on Beta')
        signin_embed.set_image(url=self.SIGNING_IN)
        signin_page = ui.Page(interaction, embed=signin_embed)

        profile_open_embed = discord.Embed(title='Open your Deeeep.io profile by clicking your profile picture')
        profile_open_embed.set_image(url=self.OPENING_PROFILE)
        profile_open_page = ui.Page(interaction, embed=profile_open_embed)

        discord_embed = discord.Embed(title='Add your Discord username as a social link on your Deeeep.io account')
        discord_embed.set_image(url=self.ADDING_DISCORD)
        discord_page = ui.Page(interaction, embed=discord_embed)

        connect_embed = discord.Embed(title="Copy your profile page's URL, then paste that URL into the \"connect\" \
command")
        connect_embed.set_image(url=self.CONNECT_COMMAND)
        connect_page = ui.Page(interaction, embed=connect_embed)

        help_book = ui.ScrollyBook(interaction, signin_page, profile_open_page, discord_page, connect_page)

        return help_book

    async def send_connect_help(self, interaction: discord.Interaction):
        """
        Send the instruction book for linking accounts
        """

        help_book = self.connect_help_book(interaction)

        await help_book.send_first()

    async def link_dep_acc(self, interaction: discord.Interaction, query: str):
        """
        Handle a request to link a Deeeep.io account
        """

        # noinspection PyUnresolvedReferences
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
                tag = interaction.user.name

                for social in socials:
                    if social['platform_id'] == 'dc' and social['platform_user_id'] == tag:
                        reusername = acc_data['username']

                        data = {
                            'user_id': interaction.user.id,
                            'acc_id': acc_id,
                            'main': False,
                        }

                        self.links_table.upsert(data, ['user_id', 'acc_id'], ensure=True)

                        await interaction.followup.send(content=f"Successfully linked to Deeeep.io account with \
username `{reusername}` and ID `{acc_id}`.")

                        return
                else:
                    await interaction.followup.send(content=f"You must add your Discord username `{tag}` as a \
(Discord) social link on that account to connect it.")
            else:
                await interaction.followup.send(content="You're already linked to this account.")
        else:
            await interaction.followup.send(content="That doesn't seem like a valid profile.")

    async def unlink_account(self, button: ui.CallbackButton, button_interaction: discord.Interaction,
                             message_interaction: discord.Interaction, acc_id: int,
                             *affected_buttons: ui.CallbackButton):
        """
        Handle a request to unlink a Deeeep.io account
        """

        user = button_interaction.user

        self.links_table.delete(user_id=user.id, acc_id=acc_id)

        button.label = 'Account unlinked'
        button.disabled = True

        for button in affected_buttons:
            button.disabled = True

        # noinspection PyUnresolvedReferences
        await button_interaction.response.send_message(content=f'Unlinked account with ID {acc_id}.')
        await message_interaction.edit_original_response(view=button.view)

    def determine_main(self, user_id: int, acc_id: int) -> dict | None:
        """
        Return the database entry of the account if the specified account ID is the main account of the user with the
        specified user ID

        :return: the database entry, or None if not found
        """

        return self.mains_table.find_one(acc_id=acc_id, user_id=user_id)

    def update_mark_button(self, button: ui.CallbackButton, is_main: dict | bool | None):
        """
        Update the button based on whether the current displayed account is the main account
        """

        if is_main:
            label = 'Unmark account as main'
            callback = self.unmark_main
        else:
            label = 'Mark account as main'
            callback = self.mark_main

        button.label = label
        button.stored_callback = callback

    async def update_mark_view(self, button: ui.CallbackButton, message_interaction: discord.Interaction,
                               is_main: dict | bool | None):
        """
        Update the button and view based on whether the current displayed account is the main account
        """

        self.update_mark_button(button, is_main)

        await message_interaction.edit_original_response(view=button.view)

    async def mark_main(self, button: ui.CallbackButton, button_interaction: discord.Interaction,
                        message_interaction: discord.Interaction, acc_id: int):
        """
        Mark the currently displayed account as the main account
        """

        row = dict(user_id=button_interaction.user.id, acc_id=acc_id)

        self.mains_table.upsert(row, ['user_id'], ensure=True)

        # noinspection PyUnresolvedReferences
        await button_interaction.response.send_message(
            content=f'This account (ID {acc_id}) will now be your first account.')

        await self.update_mark_view(button, message_interaction, True)

    async def unmark_main(self, button: ui.CallbackButton, button_interaction: discord.Interaction,
                          message_interaction: discord.Interaction, acc_id: int):
        """
        Unmark the currently displayed account as the main account
        """

        self.mains_table.delete(user_id=button_interaction.user.id, acc_id=acc_id)

        # noinspection PyUnresolvedReferences
        await button_interaction.response.send_message(content=f'This account (ID {acc_id}) will no longer be your \
        first account. Well, it might still be, but that would just be due to random chance.')

        await self.update_mark_view(button, message_interaction, False)

    def generate_profile_buttons(self, interaction: discord.Interaction, user: discord.Member, acc_id: int) -> \
            tuple[ui.CallbackButton, ui.CallbackButton] | tuple[()]:
        """
        Generate the buttons associated with each account display (aside from the scroll buttons)
        """

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
                     rankings: dict, skin_contribs: list[dict], map_creations: dict, user: discord.Member = None,
                     user_blacklist=False) -> ui.IndexedBook | ui.Page:
        """
        Generate the book with all the profile pages (tabs) for a given account
        """

        if acc:
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

    def delayed_profile_book(self, interaction: discord.Interaction, user: discord.Member, acc_id: int,
                             blacklist: bool):
        """
        Callback to a Promise that generates a profile book from the given parameters
        """

        acc, socials, rankings, skin_contribs, map_creations = self.get_profile_by_id(acc_id)

        return self.profile_book(interaction, acc, socials, rankings, skin_contribs, map_creations, user=user,
                                 user_blacklist=blacklist)

    async def full_profile_book(self, interaction: discord.Interaction, user: discord.Member, *acc_ids: int,
                                blacklist: bool):
        """
        Generate the big daddy book for all of a user's accounts. Each page is initially a Promise to avoid having to
        fetch data for all the accounts at once.
        """

        pages = map(lambda acc_id: ui.Promise(self.delayed_profile_book, interaction, user, acc_id, blacklist),
                    acc_ids)

        full_book = ui.ScrollyBook(interaction, *pages, page_title='Account')

        await full_book.send_first()

    async def display_account_by_username(self, interaction: discord.Interaction, username: str):
        """
        Display the account with the given username
        """

        # noinspection PyUnresolvedReferences
        await interaction.response.defer()

        acc, socials, rankings, skin_contribs, map_creations = self.get_profile_by_username(username)

        book = self.profile_book(interaction, acc, socials, rankings, skin_contribs, map_creations)

        await book.send_first()

    async def display_account_by_id(self, interaction: discord.Interaction, account_id: int):
        """
        Display the account with the given ID
        """

        # noinspection PyUnresolvedReferences
        await interaction.response.defer()

        acc, socials, rankings, skin_contribs, map_creations = self.get_profile_by_id(account_id)

        book = self.profile_book(interaction, acc, socials, rankings, skin_contribs, map_creations)

        await book.send_first()
