import discord

from ds_accs import DSAccs
from ds_animals import DSAnimals
from ds_maps import DSMaps
from ds_skins import DSSkins
from logs import debug
import ds_commands


class DSClient(DSAccs, DSAnimals, DSMaps, DSSkins):
    async def on_ready(self):
        # noinspection PyAttributeOutsideInit
        self.readied = True

        '''
        if not self.auto_rev_process: 
            self.auto_rev_process = self.loop.create_task(self.auto_rev_loop()) 

            debug('created auto rev process') 
        '''

        await ds_commands.gen_commands(self)

        await self.change_presence(activity=discord.Game(name='all systems operational'), status=discord.Status.online)

        debug('ready')
