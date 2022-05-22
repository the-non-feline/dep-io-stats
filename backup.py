@DS.command('blacklist', definite_usages={
    ('user', '<mention>'): 'Blacklist the mentioned user from displaying their Deeeep.io account **on this server only**', 
    ('user', '<user_id>'): 'Like above, but with discord ID instead to avoid pings', 
    ('account', '<account_id>'): 'Blacklists the Deeeep.io account with account ID of `<account_id>` from being displayed **on this server only**', 
    ('map', '<map_id>'): 'Blacklists the map with string ID of `<map_id>` from being displayed **on this server only**', 
}) 
@DS.requires_perms(req_one=('manage_messages',)) 
async def blacklist(self, c, m, blacklist_type, target_str): 
    lower_type = blacklist_type.lower() 

    target = self.convert_target(lower_type, target_str) 

    if target: 
        data = {
            'type': lower_type, 
            'guild_id': c.guild.id, 
            'target': target, 
        } 

        self.blacklists_table.upsert(data, ['type', 'guild_id', 'target'], ensure=True) 

        await self.send(c, content=f'Successfully blacklisted {lower_type} `{target}` on this server.') 
    else: 
        return True

@DS.command('unblacklist', definite_usages={
    ('user', '<mention>'): 'Unblacklist the mentioned user from displaying their Deeeep.io account **on this server only**', 
    ('user', '<user_id>'): 'Like above, but with discord ID instead to avoid pings', 
    ('account', '<account_id>'): 'Unblacklists the Deeeep.io account with account ID of `<account_id>` from being displayed **on this server only**', 
    ('map', '<string_id>'): 'Unblacklists the map with string ID of `<string_id>` from being displayed **on this server only**', 
}) 
@DS.requires_perms(req_one=('manage_messages',)) 
async def unblacklist(self, c, m, blacklist_type, target_str): 
    lower_type = blacklist_type.lower() 

    target = self.convert_target(lower_type, target_str) 

    if target: 
        self.blacklists_table.delete(guild_id=c.guild.id, type=lower_type, target=target) 

        await self.send(c, content=f'Successfully unblacklisted {lower_type} `{target}` on this server.') 
    else: 
        return True

@DS.command('fakerev', definite_usages={
    (): 'Not even Fede knows of the mysterious function of this command...', 
}, public=False) 
@DS.requires_owner
async def fake_review(self, c, m): 
    await self.check_review(c, self.fake_check) 

@DS.command('rev', definite_usages={
    (): 'Not even Fede knows of the mysterious function of this command...', 
}, public=False) 
@DS.requires_owner
async def real_review(self, c, m): 
    rev_channel = self.rev_channel() 

    if rev_channel: 
        await self.check_review(rev_channel, self.real_check, silent_fail=True) 
    else: 
        await self.send(c, content='Not set') 

@DS.command('link', definite_usages={
    (): 'View help on linking accounts', 
    ('<account_profile_pic_URL>',): "Link to the Deeeep.io account with the URL of the account's profile picture", 
    ('<account_id>',): "Like above, but with the account ID", 
}, indefinite_usages={
    ('<username>',): 'Like above, but with the given username', 
}) 
async def link(self, c, m, *query): 
    if query: 
        return await self.link_dep_acc(c, m, query) 
    else: 
        await self.link_help(c, m) 

@DS.command('unlink', definite_usages={
    (): 'Unlink your Deeeep.io account', 
})
async def unlink(self, c, m): 
    self.links_table.delete(user_id=m.author.id) 

    await self.send(c, content='Unlinked your account. ') 

@DS.command('revc', definite_usages={
    ('<channel>',): "Sets `<channel>` as the logging channel for skn review", 
    (): 'Like above, but with the current channel', 
    (DS.REV_CHANNEL_SENTINEL,): 'Un-set the logging channel', 
}, public=False) 
@DS.requires_owner
async def set_rev_channel(self, c, m, flag=None): 
    if flag == self.REV_CHANNEL_SENTINEL: 
        self.rev_data_table.delete(key=self.REV_CHANNEL_KEY) 

        await self.send(c, content="Channel removed as the logging channel.") 
    else: 
        if flag is None: 
            channel_id = c.id
        else: 
            channel_id = self.decode_channel(c, flag) 
        
        if channel_id is not None: 
            data = {
                'key': self.REV_CHANNEL_KEY, 
                'channel_id': channel_id, 
            } 

            self.rev_data_table.upsert(data, ['key'], ensure=True) 

            await self.send(c, content=f'Set <#{channel_id}> as the logging channel for skin review.') 
        else: 
            return True

@DS.command('revi', definite_usages={
    ('<i>',): 'Does something', 
}, public=False) 
@DS.requires_owner
async def set_rev_interval(self, c, m, interval): 
    if interval.isnumeric(): 
        seconds = int(interval) 

        data = {
            'key': self.REV_INTERVAL_KEY, 
            'interval': seconds, 
        } 

        self.rev_data_table.upsert(data, ['key'], ensure=True) 

        await self.send(c, content=f'Set interval to {seconds} seconds. ') 
    else: 
        return True

@DS.command('sbchannel', definite_usages={
    ('add', '<channel>'): 'Adds `<channel>` as a Skin Board channel', 
    ('add',): 'Like above, but with the current channel', 
    ('remove', '<channel>'): 'Removes `<channel>` as a Skin Board channel', 
    ('remove',): 'Like above, but with the current channel', 
}, public=False) 
@DS.requires_owner
async def set_sb_channels(self, c, m, flag, channel=None): 
    flag = flag.lower() 

    if channel: 
        channel_id = self.decode_channel(c, channel) 
    else: 
        channel_id = c.id
    
    if channel_id is not None: 
        if flag == 'remove': 
            self.sb_channels_table.delete(channel_id=channel_id) 

            await self.send(c, content=f"<#{channel_id}> removed as a Skin Board channel.") 
        elif flag == 'add': 
            data = {
                'channel_id': channel_id, 
            } 

            self.sb_channels_table.upsert(data, ['channel_id'], ensure=True) 

            await self.send(c, content=f'Added <#{channel_id}> as a Skin Board channel.') 
        else: 
            return True
    else: 
        return True

@DS.command('participation', definite_usages={
    (): "Get a summary of Skin Board members' recent votes", 
}, public=False) 
@DS.requires_sb_channel
async def participation(self, c, m): 
    await self.send_participation_report(c) 

@DS.command('habitat', definite_usages={
    ('<habitat_number>',): "Converts `<habitat_number>` to a list of habitat flags.",
})
async def convert_habitat(self, c, m, num): 
    if num.isnumeric(): 
        hab = habitat.Habitat(num) 

        await self.send(c, content=f'`{num}` translates to `{hab}`.')
    else: 
        return True

@DS.command('tree', definite_usages={
    (): "Displays the evolution tree (as of the Snow and Below beta version)",
})
async def evo_tree(self, c, m):
    with open(self.TREE, mode='rb') as tree_file:
        discord_file = discord.File(tree_file)

        await self.send(c, content=f"""The current evolution tree as of Snow and Below beta:
{char_map['void']}""", file=discord_file)

@DS.command('shutdown', definite_usages={
    (): "Turn off the bot", 
}, public=False) 
@DS.requires_owner
async def shut_down(self, c, m): 
    await self.send(c, content='shutting down') 

    self.logging_out = True

    await self.change_presence(status=discord.Status.dnd, activity=discord.Game(name='shutting down')) 

@DS.command('help', definite_usages={
    (): 'Get a list of all public commands', 
    ('<command>',): 'Get help on `<command>`', 
}) 
async def send_help(self, c, m, command_name=None): 
    if command_name: 
        comm = commands.Command.get_command(command_name)  

        if comm: 
            usage_str = comm.usages_str(self, c, m) 

            await self.send(c, content=f'''How to use the `{command_name}` command: 

{usage_str}''') 
        else: 
            prefix = self.prefix(c) 

            await self.send(c, content=f"That's not a valid command name. Type `{prefix}{self.send_help.name}` for a list of public commands. ") 
    else: 
        com_list_str = tools.format_iterable(commands.Command.all_commands(public_only=True), formatter='`{}`') 
        prefix = self.prefix(c) 

        await self.send(c, content=f'''All public commands for this bot: {com_list_str}. 
Type `{prefix}{self.send_help.name} <command>` for help on a specified `<command>`''') 