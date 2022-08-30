import discord
import logs
import tools

class TrimmedEmbed(discord.Embed): 
    MAX_AUTHOR = 256
    MAX_TITLE = 256
    MAX_DESC = 2048
    MAX_FIELD_VAL = 1024
    MAX_FOOTER = 2048
    TRAIL_OFF = '...' 

    def __init__(self, **kwargs): 
        title = kwargs.get('title', None) 

        kwargs['title'] = self.trim_maybe(title, self.MAX_TITLE) if title else None

        desc = kwargs.get('description', None) 

        kwargs['description'] = self.trim_maybe(desc, self.MAX_DESC) if desc else None

        super().__init__(**kwargs) 
    
    def trim_maybe(self, string: str, limit: str):
        return tools.trim_maybe(string, limit, self.TRAIL_OFF)
    
    def add_field(self, *, name, value, inline=True): 
        value = self.trim_maybe(value, self.MAX_FIELD_VAL) 

        return super().add_field(name=name, value=value, inline=inline) 
    
    def set_footer(self, *, text=None, icon_url=None): 
        if text: 
            text = self.trim_maybe(text, self.MAX_FOOTER) 
        else: 
            text = None
        
        return super().set_footer(text=text, icon_url=icon_url) 
    
    def set_author(self, *, name, url=None, icon_url=None): 
        name = self.trim_maybe(name, self.MAX_AUTHOR) 

        return super().set_author(name=name, url=url, icon_url=icon_url) 
    
    @classmethod
    def too_long(cls, limit: int, *vals):
        for val in vals:
            if len(val) > limit:
                return True

class Field:
    def __init__(self, *, name, value, inline: bool=True):
        self.name = name
        self.value = value
        self.inline = inline
    
    def to_dict(self):
        return {
            'name': self.name,
            'value': self.value,
            'inline': self.inline,
        }