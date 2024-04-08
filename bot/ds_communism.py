from urllib import parse

import chars
import ds_base
import embed_utils
import tools
from logs import debug


class DSCommunism(ds_base.DSBase):
    """
    Some methods such as base_profile_embed are shared across multiple modules, but aren't exactly "base" either.
    This class contains those.
    """

    def base_profile_embed(self, acc: dict, specific_page: str = '', big_image=True, blacklist=False) \
            -> embed_utils.TrimmedEmbed:
        """
        Generate the basic template for all profile-related embeds, such as account tabs and voting summaries
        """

        acc_id = acc['id']
        real_username = acc['username']
        verified = acc['verified']

        public_page = self.PROFILE_PAGE_TEMPLATE.format(parse.quote(real_username))

        if blacklist:
            display_username = '(Blacklisted account)'
        else:
            display_username = real_username

        title = f'{specific_page}{" " if specific_page else ""} {display_username}\
{f" {chars.verified}" if verified else ""}'

        pfp = acc['picture']

        # debug(pfp_url)

        tier = acc['tier']

        color = self.TIER_COLORS[tier - 1]

        # debug(hex(color))

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
