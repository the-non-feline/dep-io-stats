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