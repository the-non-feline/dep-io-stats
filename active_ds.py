import discord
from discord.ext import commands as comms
import logs
from logs import debug
import tools
import commands
import chars
import trimmed_embed
import reports
import habitat
import commands
import dep_io_stats
from dep_io_stats import DS
import slash_util
import typing
import ds_commands

import os

class Active_DS(DS): 
    def __init__(self, logs_file_name, storage_file_name, animals_file_name, *credentials):
        super().__init__(logs_file_name, storage_file_name, animals_file_name, *credentials)