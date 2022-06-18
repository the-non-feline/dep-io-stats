import discord.ui
import discord
import logs
from logs import debug

class CallbackButton(discord.ui.Button):
    def __init__(self, callback, message_interaction, *args, style=discord.ButtonStyle.secondary, label=None, disabled=False, 
    custom_id=None, url=None, emoji=None, row=None, **kwargs):
        super().__init__(style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row)

        self.stored_callback = callback
        self.message_interaction = message_interaction
        self.args = args
        self.kwargs = kwargs
    
    async def callback(self, button_interaction: discord.Interaction):
        return await self.stored_callback(self, button_interaction, self.message_interaction, *self.args, **self.kwargs)

class TrackedView(discord.ui.View):
    active_views = set()

    def __init__(self, *, timeout=180.0):
        super().__init__(timeout=timeout)

        self.active_views.add(self)
    
    @classmethod
    async def close_all(cls):
        for view in cls.active_views.copy():
            await view.close()

class RestrictedView(TrackedView):
    def __init__(self, original_user: discord.User, original_interaction: discord.Interaction, *, timeout=180.0):
        super().__init__(timeout=timeout)
        
        self.original_user = original_user
        self.original_interaction = original_interaction
    
    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.original_user:
            await interaction.response.send_message(content=f"{interaction.user.mention} used click. It's not very effective...",
            ephemeral=True)
        else:
            return True
    
    async def close(self):
        self.clear_items()

        closed_button = discord.ui.Button(disabled=True, label=f'No longer accepting button presses', row=0)
        
        self.add_item(closed_button)

        try:
            await self.original_interaction.edit_original_message(view=self)
        except discord.errors.NotFound:
            debug(f"View {self}'s original message couldn't be found")

        self.stop()

        self.active_views.remove(self)
    
    async def on_timeout(self) -> None:
        await self.close()

        return await super().on_timeout()

class Page:
    def __init__(self, content=None, embed=None, allowed_mentions=None):
        self.content = content
        self.embed = embed
        self.allowed_mentions = allowed_mentions
    
    async def send_self(self, parent, interaction: discord.Interaction):
        await interaction.response.send_message(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions, view=parent.view)
    
    async def edit_self(self, parent, interaction: discord.Interaction):
        await interaction.response.edit_message(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions, view=parent.view)

class Book:
    pass

class ScrollyBook:
    def __init__(self, interaction: discord.Interaction, *pages: Page, timeout=None):
        self.interaction = interaction
        self.pages = pages
        self.cur_index = 0
        self.timeout = timeout

        self.view = RestrictedView(interaction.user, interaction, timeout=self.timeout)

        self.left_button = CallbackButton(self.turn_page, self.interaction, -1, style=discord.ButtonStyle.primary, label='Previous',
        row=0)
        self.page_number = discord.ui.Button(disabled=True, label=f'Page {self.cur_index + 1} / {len(self.pages)}',
        row=0)
        self.right_button = CallbackButton(self.turn_page, self.interaction, 1, style=discord.ButtonStyle.primary, label='Next',
        row=0)
        # self.close_button = CallbackButton(self.manual_close, self.interaction, style=discord.ButtonStyle.danger, label='Close',
        # row=1)

        self.view.add_item(self.left_button)
        self.view.add_item(self.page_number)
        self.view.add_item(self.right_button)
        # self.view.add_item(self.close_button)

        self.update_buttons()
    
    '''
    async def close_book(self):
        self.view.clear_items()
        
        closed_button = discord.ui.Button(disabled=True, label=f'Time limit for using buttons already elapsed', row=0)
        
        self.view.add_item(closed_button)

        await self.interaction.edit_original_message(view=self.view)
    
    async def manual_close(self, button_interaction: discord.Interaction, message_interaction: discord.Interaction):
        self.view.stop()
    
    async def wait_until_finished(self):
        await self.view.wait()
        await self.close_book()
    '''
    
    async def send_first(self):
        cur = self.pages[self.cur_index]

        await cur.send_self(self, self.interaction)
    
    def update_buttons(self):
        self.left_button.disabled = self.cur_index <= 0
        self.right_button.disabled = self.cur_index >= len(self.pages) - 1
        self.page_number.label = f'Page {self.cur_index + 1} / {len(self.pages)}'
    
    async def turn_page(self, button: CallbackButton, button_interaction: discord.Interaction, message_interaction: discord.Interaction, direction: int):
        self.cur_index += direction
        cur = self.pages[self.cur_index]
        
        self.update_buttons()

        await cur.edit_self(self, button_interaction)