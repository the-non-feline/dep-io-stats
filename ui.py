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
    
    def add_item(self, item):
        debug(f'Adding {item}')

        return super().add_item(item)
    
    def remove_item(self, item):
        debug(f'Removing {item}')

        return super().remove_item(item)

class Page:
    MAX_ROW = 4

    def __init__(self, content=None, embed=None, allowed_mentions=None, view=None):
        self.interaction = None
        self.content = content
        self.embed = embed
        self.allowed_mentions = allowed_mentions
        self.view = view
        self.level = 0
    
    async def send_self(self, interaction: discord.Interaction, followup: bool):
        if followup:
            if self.view:
                await interaction.followup.send(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions, view=self.view)
            else:
                await interaction.followup.send(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions)
        else:
            if self.view:
                await interaction.response.send_message(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions, view=self.view)
            else:
                await interaction.response.send_message(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions)
    
    async def edit_self(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions, view=self.view)
    
    async def send_first(self, followup=False):
        return await self.send_self(self.interaction, followup=followup)
    
    def register_self(self):
        pass
    
    def deregister_self(self):
        pass

    def set_view(self, view: RestrictedView):
        self.view = view
    
    def set_level(self, level: int=MAX_ROW):
        self.level = level

class Book(Page):
    def __init__(self, interaction: discord.Interaction, timeout, view: RestrictedView, pages: tuple[Page], 
    buttons: tuple[CallbackButton]):
        self.interaction = interaction
        self.timeout = timeout
        self.level = 0

        if view:
            self.view = view
        else:
            self.view = RestrictedView(interaction.user, interaction, timeout=self.timeout)

        self.pages = pages
        self.buttons = list(buttons)
    
    def cur_page(self) -> Page:
        pass

    def add_button(self, button: CallbackButton):
        self.buttons.append(button)

    async def send_self(self, interaction: discord.Interaction, followup: bool):
        return await self.cur_page().send_self(interaction, followup)
    
    async def edit_self(self, interaction: discord.Interaction):
        return await self.cur_page().edit_self(interaction)
    
    async def send_first(self, followup=False):
        self.set_view(self.view)
        self.set_level()

        self.register_self()

        return await self.send_self(self.interaction, followup)
    
    def register_self(self):
        for button in self.buttons:
            self.view.add_item(button)
        
        self.cur_page().register_self() 
    
    def deregister_self(self):
        for button in self.buttons:
            self.view.remove_item(button)
        
        self.cur_page().deregister_self()   
    
    def set_view(self, view: RestrictedView):
        super().set_view(view)

        for page in self.pages:
            page.set_view(view)
    
    def set_level(self, level: int=Page.MAX_ROW):
        super().set_level(level)

        for button in self.buttons:
            button.row = self.level

        for page in self.pages:
            page.set_level(level=level - 1)

class IndexedBook(Book):
    def __new__(cls, interaction: discord.Interaction, *page_tuples: tuple, timeout=180.0, view=None, extra_buttons=()):
        if len(page_tuples) > 1:
            return super().__new__(cls)
        else:
            page_tuples[0][1].interaction = interaction

            return page_tuples[0][1]

    def __init__(self, interaction: discord.Interaction, *page_tuples: tuple, timeout=180.0, view=None, extra_buttons=()):
        # generate the buttons here
        buttons = tuple(CallbackButton(self.jump_to_page, interaction, page, style=discord.ButtonStyle.primary, 
        label=button_name, row=0) for button_name, page in page_tuples) + extra_buttons

        super().__init__(interaction, timeout, view, tuple(page_tuple[1] for page_tuple in page_tuples), buttons)

        self.cur_button = self.buttons[0]
        self.current_page = page_tuples[0][1]

        self.cur_button.disabled = True
    
    def cur_page(self):
        return self.current_page
    
    async def jump_to_page(self, button: CallbackButton, button_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, page: Page):
        self.cur_page().deregister_self()

        self.cur_button.disabled = False

        self.current_page = page
        self.cur_button = button

        self.cur_button.disabled = True

        self.cur_page().register_self()

        await self.edit_self(button_interaction)

class ScrollyBook(Book):
    def __new__(cls, interaction: discord.Interaction, *pages: Page, timeout=180.0, view=None, extra_buttons=()):
        if len(pages) > 1:
            return super().__new__(cls)
        else:
            pages[0].interaction = interaction
            
            return pages[0]
    
    def __init__(self, interaction: discord.Interaction, *pages: Page, timeout=180.0, view=None, extra_buttons=()):
        self.cur_index = 0

        self.left_button = CallbackButton(self.turn_page, interaction, -1, style=discord.ButtonStyle.primary, label='Previous',
        row=0)
        self.page_number = discord.ui.Button(disabled=True, label=f'Page {self.cur_index + 1} / {len(pages)}',
        row=0)
        self.right_button = CallbackButton(self.turn_page, interaction, 1, style=discord.ButtonStyle.primary, label='Next',
        row=0)
        # self.close_button = CallbackButton(self.manual_close, self.interaction, style=discord.ButtonStyle.danger, label='Close',
        # row=1)
        # self.view.add_item(self.close_button)

        buttons_tuple = (self.left_button, self.page_number, self.right_button) + extra_buttons
        
        super().__init__(interaction, timeout, view, pages, buttons_tuple)

        self.current_page = self.pages[self.cur_index]

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

    def cur_page(self) -> Page:
        return self.current_page
    
    def update_buttons(self):
        self.left_button.disabled = self.cur_index <= 0
        self.right_button.disabled = self.cur_index >= len(self.pages) - 1
        self.page_number.label = f'Page {self.cur_index + 1} / {len(self.pages)}'
    
    async def turn_page(self, button: CallbackButton, button_interaction: discord.Interaction, message_interaction: discord.Interaction, direction: int):
        self.cur_page().deregister_self()

        self.cur_index += direction
        self.current_page = self.pages[self.cur_index]
        
        self.update_buttons()

        self.cur_page().register_self()
        await self.edit_self(button_interaction)