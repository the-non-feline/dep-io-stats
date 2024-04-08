import discord

import chars
import ds_communism
from logs import debug
import re


class DSAccs(ds_communism.DSCommunism):
    """
    Class to handle all methods related to Deeeep.io accounts
    """

    def get_acc_data(self, acc_id: int) -> dict | None:
        """
        Get account JSON data for the Deeeep.io account with the given ID
        """

        url = self.DATA_URL_TEMPLATE.format(acc_id)

        return self.async_get(url)[0]

    def get_true_username(self, query) -> str | None:
        """
        Extract the username from the query, which is either a username or a profile page URL
        """

        m = re.compile(self.PROFILE_PAGE_REGEX).match(query)

        if m:
            username = m.group('username')

            return username

    def get_profile_by_username(self, username: str) -> tuple[dict | None, list | tuple, list | tuple, list | tuple,
                                                              list | tuple]:
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
            socials = rankings = skin_contribs = map_creations = ()

        return acc_json, socials, rankings, skin_contribs, map_creations

    def skin_contribs_embeds(self, interaction: discord.Interaction, acc: dict, skins: list[dict]):
        embed_template = self.base_profile_embed(acc, specific_page='Skins by', big_image=False)

        embed_template.description = 'This list only includes **officially added** skins (skins approved for the Store)'

        titles = f'Skin {chars.SHORTCUTS.skin_symbol}', f'Sales {chars.stonkalot}'
        formatters = self.SKIN_EMBED_LINK_FORMATTER, '{[sales]:,}'

        if skins:
            skins.sort(key=lambda skin: skin['sales'], reverse=True)

        return self.generic_compilation_embeds(interaction, embed_template, 'skins', skins, titles, formatters,
                                               aggregate_names=('sales',), aggregate_attrs=('sales',))
