import discord

class TrimmedEmbed(discord.Embed): 
    MAX_TITLE = 256
    MAX_DESC = 2048
    MAX_FIELD_VAL = 1024
    MAX_FOOTER = 2048
    TRAIL_OFF = '...' 

    def __init__(self, **kwargs): 
        title = kwargs.get('title', None) 

        kwargs['title'] = self.trim_maybe(title, self.MAX_TITLE) if title else discord.Embed.Empty

        desc = kwargs.get('description', None) 

        kwargs['description'] = self.trim_maybe(desc, self.MAX_DESC) if desc else discord.Embed.Empty

        super().__init__(**kwargs) 
    
    def trim_maybe(self, string, limit): 
        string = str(string) 
        
        if string and len(string) > limit: 
            string = string[:limit - len(self.TRAIL_OFF)] + self.TRAIL_OFF
        
        return string
    
    def add_field(self, *, name, value, inline=True): 
        value = self.trim_maybe(value, self.MAX_FIELD_VAL) 

        return super().add_field(name=name, value=value, inline=inline) 
    
    def set_footer(self, *, text=None, icon_url=discord.Embed.Empty): 
        if text: 
            text = self.trim_maybe(text, self.MAX_FOOTER) 
        else: 
            text = discord.Embed.Empty
        
        return super().set_footer(text=text, icon_url=icon_url) 
