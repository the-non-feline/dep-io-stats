import logging

import dataset
import discord
import discord.ui
import discord.ui
import grequests
from discord.ext import commands

import ds_constants
import logs
import ui
from logs import debug
import embed_utils
import chars
import tools


class DSBase(ds_constants.DS_Constants, commands.Bot):
    """
    Class to store all instance variables for the bot, as well as some methods
    """

    def __init__(self, logs_file_name: str, storage_file_name: str, animals_file_name: str, email: str, password: str):
        """
        Initializes the bot

        logs_file_name: the filename of the file to log to
        storage_file_name: the filename of the SQL database
        animals_file_name: the filename of the file containing all animal stats
        email: the email of the bot's Deeeep.io account
        password: the password of the bot's Deeeep.io account
        """

        self.email = email
        self.password = password

        self.active_token_requests = 0
        self.token = None

        # self.credman = credman.CredMan(self, self.credentials)

        # database consists of many tables
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

        # this is how the bot logs
        handler = logging.StreamHandler(self.logs_file)

        logs.logger.addHandler(handler)

        # self.levels_file = open(levels_file_name, mode='r')

        self.tasks = 0
        self.logging_out = False

        self.readied = False

        self.auto_rev_process = None

        # is this used for anything? IDK
        self.ALL_FILTERS = {}

        super().__init__(',', intents=discord.Intents(), activity=discord.Game(name='starting up'),
                         status=discord.Status.dnd)

    def blacklisted(self, guild_id: int, blacklist_type: str, target: int) -> bool:
        """
        Checks whether the given target has the given type of blacklist in the given guild
        """

        if guild_id:
            b_entry = self.blacklists_table.find_one(guild_id=guild_id, type=blacklist_type, target=target)

            return b_entry
        else:
            return False

    async def logout(self):
        """
        Logs out and shuts down the bot
        """

        try:
            if self.auto_rev_process:
                self.auto_rev_process.cancel()

            '''
            self.tree.clear_commands(guild=discord.Object(273213133731135500))
            await self.tree.sync(guild=discord.Object(273213133731135500))
            '''

            # close all remaining views
            await ui.TrackedView.close_all()

            # set status to offline
            await self.change_presence(status=discord.Status.offline)

            # close the logs file
            self.logs_file.close()
            # self.levels_file.close()
        finally:
            await super().close()

    def async_get(self, *all_requests: str | tuple[str, str] | grequests.AsyncRequest) -> list[dict | list | None]:
        """
        Sends one or more requests asynchronously. Returns a list containing the JSON of each response, or None for
        unsuccessful requests

        all_requests: Each parameter is treated differently depending on what it is:
            str: a URL to be sent with a GET request
            tuple: must be in the format method, URL. Will send a request with the given method and URL
            grequests.AsyncRequest: will be sent as-is
        """

        requests_list = []

        for request in all_requests:
            if type(request) is str:  # plain url
                to_add = grequests.get(request, timeout=self.REQUEST_TIMEOUT)
            elif type(request) is tuple:  # (method, url)
                to_add = grequests.request(*request, timeout=self.REQUEST_TIMEOUT)
            else:
                to_add = request

            requests_list.append(to_add)

        # noinspection PyUnusedLocal
        def handler(waste_request, exception):
            debug('connection error')
            debug(exception)

        datas = grequests.map(requests_list, exception_handler=handler)

        # debug(datas)

        jsons = []

        # build the list
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

            # debug(jsons)

        return jsons

    def fetch_token(self):
        """
        Fetches a token (or uses the cached one if one already fetched) and sets the token attribute to that
        """

        if not self.token:
            debug(self.email)
            debug(self.password)

            request = grequests.request('POST', self.LOGIN_URL, data={
                'email': self.email,
                'password': self.password,
            }, headers={
                'origin': 'https://creators.deeeep.io'
            }, timeout=self.REQUEST_TIMEOUT)

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
        """
        Forgets the token
        """

        former_token = self.token

        self.token = None

        debug(f'Forgor token {former_token}')

    class TokenManager:
        """
        Context manager for borrow_token method
        """
        def __init__(self, client):
            self.client = client

        def __enter__(self):
            self.client.active_token_requests += 1

            self.client.fetch_token()

            return self.client.token

        def __exit__(self, exc_type, exc_value, traceback):
            self.client.active_token_requests -= 1

            if not self.client.active_token_requests:
                self.client.del_token()

    def borrow_token(self) -> TokenManager:
        """
        Context manager that fetches a token and forgets it at the end
        """

        return self.TokenManager(self)

    def suggestions_book(self, interaction: discord.Interaction, suggestions: list[dict], search_type: str,
                         titles: tuple[str, ...],
                         formatters: tuple[str, ...], page_buttons_func) -> ui.Page:
        """
        Generate the prompt of possible suggestions when the user searches something and doesn't get exact match
        """

        color = discord.Color.random()
        description = f'Did you mean one of these?'
        empty_description = "Never mind I have no suggestions. Sorry m8."

        embed_template = embed_utils.TrimmedEmbed(title=f"Possible {search_type} results", color=color,
                                                  description=description)

        return self.generic_compilation_embeds(interaction, embed_template, search_type, suggestions, titles,
                                               formatters,
                                               empty_description=empty_description,
                                               artificial_limit=ui.CallbackSelect.MAX_OPTIONS,
                                               page_buttons_func=page_buttons_func)

    @staticmethod
    def gen_generic_compilation_page(interaction: discord.Interaction, embed_template: embed_utils.TrimmedEmbed,
                                     items: list[dict | object],
                                     column_titles: tuple[str, ...], column_strs: tuple[str, ...], totals_str: str,
                                     tacked_fields: tuple[embed_utils.Field, ...],
                                     page_buttons_func) -> ui.Page:
        """
        Generate one page of the compilation

        interaction: the Discord interaction that asked for this compilation
        embed_template: a bare embed to use as a template
        items: the items in the compilation
        column_titles: the titles to use for each attribute
        column_strs: the values to use for each attribute
        totals_str: the string of all the totals
        tacked_fields: all the extra fields to tack on
        page_buttons_func: a function to generate the extra buttons on the page. Takes a discord.Interaction and
            a list of items and returns a tuple of UI elements.
        """

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
                                  pages: list[ui.Page], titles: tuple[str, ...], formatters: tuple[str, ...],
                                  items: list[dict | object],
                                  destinations: tuple[list, ...], destination_lengths: list[int, ...], totals_str: str,
                                  tacked_fields: tuple[embed_utils.Field, ...],
                                  page_buttons_func, artificial_limit: int):
        """
        Build on the compilation book for one item

        interaction: the Discord interaction that asked for this compilation
        embed_template: a bare embed to use as a template
        comp_item: the item
        pages: the list of Pages in the book so far; this is modified by this method
        titles: the column titles
        formatters: format strings specifying how each attribute is formatted in its display value
        items: the items in the compilation
        destinations: a tuple of lists where each attribute will be added to its corresponding list. Modified by this
            method.
        destination_lengths: a list that keeps track of the length of each destination
        totals_str: the string of the aggregated totals
        tacked_fields: all the extra fields to tack on
        page_buttons_func: a function to generate the extra buttons on the page. Takes a discord.Interaction and
            a list of items and returns a tuple of UI elements.
        artificial_limit: maximum number of items per page
        """

        for index in range(len(destinations)):
            formatted = formatters[index].format(comp_item)

            destination_lengths[index] += len(formatted) + int(destination_lengths[index] > 0)

        # as of calculating this variable, the stuff has not been added to the running sum yet!
        too_long = artificial_limit and len(items) >= artificial_limit

        if not too_long:
            for destination_length in destination_lengths:
                if destination_length > embed_utils.TrimmedEmbed.MAX_FIELD_VAL:
                    too_long = True

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
    def generic_compilation_aggregate(compilation_type: str, comp_items: list[dict | object],
                                      aggregate_names: tuple[str, ...],
                                      aggregate_attrs: tuple[str | int, ...]) -> str:
        """
        Build the totals string

        compilation_type: the name of the compilation
        comp_items: the items in the compilation
        aggregate_names: the names of each total
        aggregate_attrs: the attributes to aggregate
        """

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
                                   compilation_type: str, comp_items: list[dict | object],
                                   titles: tuple[str, ...], formatters: tuple[str, ...],
                                   aggregate_names: tuple[str, ...] = (),
                                   aggregate_attrs: tuple[str, ...] = (),
                                   tacked_fields: tuple[embed_utils.Field, ...] = (),
                                   empty_description: str = None, extra_buttons=(), page_buttons_func=None,
                                   artificial_limit=None) -> ui.Page | ui.ScrollyBook:
        """
        Big daddy method to build the whole compilation book

        interaction: the Discord interaction that asked for this compilation
        embed_template: a bare embed to use as a template
        compilation_type: the name of the compilation
        comp_items: the items in the compilation
        titles: the column titles
        formatters: format strings specifying how each attribute is formatted in its display value
        aggregate_names: the names of each total
        aggregate_attrs: the attributes to aggregate
        tacked_fields: all the extra fields to tack on
        empty_description: the string to display when the compilation is empty
        extra_buttons: the extra buttons to add to the book
        page_buttons_func: a function to generate the extra buttons on the page. Takes a discord.Interaction and
            a list of items and returns a tuple of UI elements
        artificial_limit: maximum number of items per page
        """

        if comp_items:
            pages = []
            # noinspection PyUnusedLocal
            destinations = tuple([] for title in titles)
            cur_items = []
            destination_lengths = [0] * len(titles)

            totals_str = self.generic_compilation_aggregate(compilation_type, comp_items, aggregate_names,
                                                            aggregate_attrs)

            for comp_item in comp_items:
                self.build_generic_compilation(interaction, embed_template, comp_item, pages, titles, formatters,
                                               cur_items,
                                               destinations, destination_lengths, totals_str, tacked_fields,
                                               page_buttons_func, artificial_limit)

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
                embed.add_field(name=f"Something went wrong {chars.whoopsy_dolphin}", value=f'There was an error \
fetching {compilation_type}.')
            else:
                embed.add_field(name=f'No {compilation_type} {chars.funwaa_eleseal}',
                                value=empty_description or f'Nothing to see here, move along.')

            return ui.Page(interaction, embed=embed)

    async def search_with_suggestions(self, interaction: discord.Interaction, search_type: str, titles: tuple[str, ...],
                                      formatters: tuple[str, ...],
                                      search_list: list[dict], map_func, query: str, page_buttons_func,
                                      no_duplicates=False):
        """
        Search through a list of stuff by name, displaying a book of suggestions if no single match found
        """

        perfect_matches = []
        suggestions = []

        for item in search_list:
            item_name = map_func(item)

            lowered_name = item_name.lower()
            lowered_query = query.lower()

            # debug(lowered_name)
            # debug(lowered_query)

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
            suggestions_book = self.suggestions_book(interaction, final_list, search_type, titles, formatters,
                                                     page_buttons_func)

            await suggestions_book.send_first()

    async def self_embed(self) -> embed_utils.TrimmedEmbed:
        """
        Returns the embed describing its own stats
        """

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

        embed.set_footer(text=f'''• Connected to {user_count} accounts
• In {guild_count} guilds''')

        return embed
