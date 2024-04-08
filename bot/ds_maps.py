import json
import re
from urllib import parse

import discord
from dateutil import parser

import chars
import ds_communism
import embed_utils
import tools
from logs import debug


class DSMaps(ds_communism.DSCommunism):
    """
    Class to handle all map-related stuff
    """

    def map_error_embed(self):
        """
        Generate the embed that shows when the map can't be fetched
        """

        color = discord.Color.random()

        embed = embed_utils.TrimmedEmbed(title="Couldn't find that map", type='rich',
                                         description="Truly unfortunate. Here's some possible explanations.",
                                         color=color)

        embed.add_field(name=f"Maybe the game is not working {chars.whoopsy_dolphin}",
                        value="It do be like that sometimes. The only option here is to wait until it works again.",
                        inline=False)
        embed.add_field(name=f"Or maybe it's just being slow {chars.sleepy_shark}",
                        value=f"""I ain't got the patience to wait more than {self.REQUEST_TIMEOUT} seconds for a map \
to load. 

**Tip:** Finding maps by **numerical ID** is very fast. You can use that to avoid this issue.""", inline=False)
        embed.add_field(name=f"Or maybe it's a skill issue {chars.funwaa_eleseal}",
                        value="""It is also quite possible that you made a typo in your search.

**Is your string ID a number?** If I see a number, I'm assuming it's a numerical ID. You can use the `find_by` \
parameter to tell me otherwise.""",
                        inline=False)

        return embed

    def count_objects(self, objs: list[dict]):
        """
        Generate a list of strings stating the total number of objects in the map + the number of each type of object
        """

        class Counter:
            """
            Helper class for counting objects
            """

            total_obj = 0
            total_points = 0
            counters = {}

            def __init__(self, layer_name: str, display_name=None):
                self.layer_name = layer_name
                self.display_name = display_name

                self.obj = 0
                self.points = 0

                self.counters[layer_name] = self

            def add(self, element: dict):
                """
                Count an element in this layer
                """

                # if an element doesn't come with a list of points, it counts as one point
                points = 1

                if 'points' in element:
                    points = len(element['points'])

                self.obj += 1
                self.__class__.total_obj += 1

                self.points += points
                self.__class__.total_points += points

            def get_display_name(self):
                """
                Return the string representation of this layer's name
                """

                if self.display_name:
                    return self.display_name
                else:
                    return self.layer_name.replace('-', ' ')

            @classmethod
            def add_element(cls, element: dict):
                """
                Add an element to the class's total and the corresponding layer's total
                """

                layer_id = element['layerId']

                if layer_id in cls.counters:
                    counter = cls.counters[layer_id]
                else:
                    counter = cls(layer_id)

                counter.add(element)

        [Counter.add_element(element) for element in objs]

        result_list = [f'{counter.obj:,} {counter.get_display_name()} ({counter.points:,} points)' for counter in
                       Counter.counters.values()]

        result_list.insert(0, f'**{Counter.total_obj:,} total objects ({Counter.total_points:,} points)**')

        return result_list

    def map_embed(self, map_json: dict):
        """
        Generate the embed for the map
        """

        color = discord.Color.random()

        title = map_json['title']
        ID = map_json['id']
        string_id = map_json['string_id']
        desc = map_json['description']
        likes = map_json['likes']
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

    def get_map_string_id(self, query: str) -> str | None:
        """
        Fetch the string ID of a map from an input query string
        """

        m = re.compile(self.MAP_REGEX).match(query)

        if m:
            map_string_id = m.group('map_string_id')

            return map_string_id

        # debug(map_id)
