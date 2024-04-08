"""

Class for all methods that handle animals

"""

import json

import discord
import typing

import chars
import ds_base
import embed_utils
import habitat
import tools
import ui


class DSAnimals(ds_base.DSBase):
    """
    Class to handle all animal-related methods
    """

    def set_animal_stats(self):
        """
        sets animal_stats attribute to the most updated version of animal stats
        """

        self.animal_stats = self.get_animal_stats()

        print('set animal stats')

    def get_animal_stats(self) -> list[dict]:
        """
        loads the JSON contents of the animal stats file
        """

        with open(self.animals_file_name, mode='r') as file:
            return json.load(file)

    @staticmethod
    def animal_check(target_id: int):
        """
        I seriously don't remember what this was for, i think it's like for filters or smth
        """

        # noinspection PyUnusedLocal
        def check(self, skin):
            animal = skin['fish_level']

            return animal == target_id

        return check

    def find_animal_by_id(self, animal_id: int) -> dict:
        """
        Fetch an animal's JSOn data by its ID
        """

        stats = self.animal_stats

        return stats[animal_id]

    def find_animal_by_name(self, animal_name: str) -> dict | None:
        """
        Fetch an animal's JSON data by its name
        """

        stats = self.animal_stats

        for animal in stats:
            if animal['name'] == animal_name.lower():
                return animal

        return None

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

    # noinspection PyUnusedLocal
    async def display_animal_from_menu(self, menu: ui.CallbackSelect, menu_interaction: discord.Interaction,
                                       message_interaction: discord.Interaction):
        """
        Display the selected animal from the dropdown menu
        """

        first_value = menu.values[0]

        index = int(first_value)

        animal = self.animal_stats[index]

        await menu_interaction.response.defer(thinking=True)

        await menu_interaction.followup.send(embed=self.animal_embed(animal))

    def animal_page_menu(self, message_interaction: discord.Interaction, animals: list[dict]) \
            -> tuple[ui.CallbackSelect]:
        """
        Generate the dropdown menu for selecting animals
        """

        options = [ui.TruncatedSelectOption(label=animal['name'], value=animal['fishLevel'],
                                            description=f"ID: {animal['fishLevel']}") for animal in animals]

        menu = ui.CallbackSelect(self.display_animal_from_menu, message_interaction, options=options,
                                 placeholder='Choose an animal')

        return (menu,)

    def get_translations(self, *translation_queries: str | bool) -> tuple[str, ...]:
        """
        Get the Crowdl translations of animal texts.

        Each entry in translation_queries is a string (the text) followed by a boolean: True if that text is the
        name, False if it's the description
        """

        urls = []

        for index in range(0, len(translation_queries), 2):
            query = translation_queries[index]
            is_name = translation_queries[index + 1]

            formatter = self.CROWDL_NAME_TEMPLATE if is_name else self.CROWDL_DESC_TEMPLATE

            urls.append(formatter.format(query))

        results = self.async_get(*urls)

        return tuple(map(lambda response: response[0]['value'] if response else None, results))

    @classmethod
    def parse_translation_format(cls, key: str) \
            -> tuple[str, str, typing.Callable[[int | float], int | float], int | float]:
        """
        Given the abbreviation of a stat change, return the display name, formatter, converter, and multiplier
        for that stat change, in that order
        """

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

    @classmethod
    def format_stat(cls, animal: dict, stat_key: str) -> tuple[str, str]:
        """
        Given an animal and the stat to display, format the stat's value

        Returns the display name of the stat and the formatted value
        """

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

    async def display_animal(self, interaction: discord.Interaction, animal_query: str):
        animal_data = await self.search_with_suggestions(interaction, 'animals', (f'Animal {chars.fish}',),
                                                         ('{[name]}',),
                                                         self.animal_stats,
                                                         lambda given_animal: given_animal['name'], animal_query,
                                                         self.animal_page_menu, no_duplicates=True)

        if animal_data:
            animal = animal_data[0]

            await interaction.response.defer()

            await interaction.followup.send(embed=self.animal_embed(animal))
