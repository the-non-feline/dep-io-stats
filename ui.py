from sys import exc_info
import discord.ui
import discord
import logs
from logs import debug

DEFAULT_TIMEOUT = 600.0

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

    def __init__(self, *, timeout=DEFAULT_TIMEOUT):
        super().__init__(timeout=timeout)

        self.active_views.add(self)
    
    @classmethod
    async def close_all(cls):
        for view in cls.active_views.copy():
            await view.close()
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        try:
            raise error
        except:
            debug(f'error in {item}', exc_info=True)

class RestrictedView(TrackedView):
    def __init__(self, original_user: discord.User, original_interaction: discord.Interaction, *, timeout=DEFAULT_TIMEOUT):
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
        for item in self.children:
            item.disabled = True

        try:
            await self.original_interaction.edit_original_response(view=self)
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

    def __init__(self, interaction: discord.Interaction, content=None, embed=None, allowed_mentions=None, timeout=DEFAULT_TIMEOUT, 
    buttons: tuple[CallbackButton]=()):
        self.interaction = interaction
        self.buttons = buttons
        self.timeout = timeout
        self.content = content
        self.embed = embed
        self.allowed_mentions = allowed_mentions
        self.view = None
        self.level = self.MAX_ROW
    
    async def send_self(self, interaction: discord.Interaction):
        if interaction.response.is_done():
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
        if interaction.response.is_done():
            await interaction.edit_original_response(content=self.content, embed=self.embed, 
            allowed_mentions=self.allowed_mentions, view=self.view)
        else:
            await interaction.response.edit_message(content=self.content, embed=self.embed, 
        allowed_mentions=self.allowed_mentions, view=self.view)
    
    async def send_first(self):
        self.assign_view()
        self.set_level()

        debug('assigned')

        await self.register_self(self.interaction)

        debug('registered')

        return await self.send_self(self.interaction)
    
    async def register_self(self, interaction: discord.Interaction):
        for button in self.buttons:
            self.view.add_item(button)
    
    async def deregister_self(self, interaction: discord.Interaction):
        for button in self.buttons:
            self.view.remove_item(button)

    def set_view(self, view: RestrictedView):
        self.view = view
    
    def set_level(self, level: int=MAX_ROW):
        self.level = level

        for button in self.buttons:
            button.row = self.level
    
    def assign_view(self):
        if self.buttons:
            new_view = RestrictedView(self.interaction.user, self.interaction, timeout=self.timeout)
        
            self.set_view(new_view)

class Promise(Page):
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

        self.level = self.MAX_ROW
        self.view = None
        self.buttons = ()
    
    def execute(self) -> Page:
        executed = self.callback(*self.args, **self.kwargs)

        executed.set_view(self.view)
        executed.set_level(self.level)

        return executed
    
    async def send_first(self):
        executed = self.execute()

        return await executed.send_first()

class Book(Page):
    def __init__(self, interaction: discord.Interaction, timeout, pages: list[Page], 
    buttons: list[CallbackButton]):
        self.interaction = interaction
        self.timeout = timeout
        self.level = self.MAX_ROW
        self.current_index = 0

        self.view = None

        self.pages = pages
        self.buttons = buttons
    
    async def cur_page(self, interaction: discord.Interaction) -> Page:
        cur = self.pages[self.current_index]

        if type(cur) is Promise:
            if not interaction.response.is_done():
                await interaction.response.defer()

            new_cur = cur.execute()

            self.pages[self.current_index] = new_cur
        
        return self.pages[self.current_index]

    def add_button(self, button: CallbackButton):
        self.buttons.append(button)

    async def send_self(self, interaction: discord.Interaction):
        return await (await self.cur_page(interaction)).send_self(interaction)
    
    async def edit_self(self, interaction: discord.Interaction):
        return await (await self.cur_page(interaction)).edit_self(interaction)
    
    async def register_self(self, interaction: discord.Interaction):
        await super().register_self(interaction)
        
        await (await self.cur_page(interaction)).register_self(interaction)
    
    async def deregister_self(self, interaction: discord.Interaction):
        await super().deregister_self(interaction)
        
        await (await self.cur_page(interaction)).deregister_self(interaction)   
    
    def set_view(self, view: RestrictedView):
        super().set_view(view)

        for page in self.pages:
            page.set_view(view)
    
    def set_level(self, level: int=Page.MAX_ROW):
        super().set_level(level)

        for page in self.pages:
            page.set_level(level=level - 1)

class IndexedBook(Book):
    def __new__(cls, interaction: discord.Interaction, *page_tuples: tuple, timeout=DEFAULT_TIMEOUT, 
    extra_buttons: tuple[CallbackButton]=()):
        if len(page_tuples) > 1 or extra_buttons:
            return super().__new__(cls)
        else:
            page_tuples[0][1].interaction = interaction

            return page_tuples[0][1]

    def __init__(self, interaction: discord.Interaction, *page_tuples: tuple, timeout=DEFAULT_TIMEOUT, 
    extra_buttons: tuple[CallbackButton]=()):
        self.cur_button = None

        # generate the buttons here
        if len(page_tuples) > 1:
            normal_buttons = [CallbackButton(self.jump_to_page, interaction, index, style=discord.ButtonStyle.primary, 
        label=page_tuples[index][0]) for index in range(len(page_tuples))]
        
            self.cur_button = normal_buttons[0]

            self.cur_button.disabled = True
        else:
            normal_buttons = []
        
        buttons = normal_buttons + list(extra_buttons)

        super().__init__(interaction, timeout, [page_tuple[1] for page_tuple in page_tuples], buttons)
    
    async def jump_to_page(self, button: CallbackButton, button_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, index: int):
        await (await self.cur_page(button_interaction)).deregister_self(button_interaction)

        self.cur_button.disabled = False

        self.current_index = index
        self.cur_button = button

        self.cur_button.disabled = True

        await (await self.cur_page(button_interaction)).register_self(button_interaction)

        await self.edit_self(button_interaction)

class ScrollyBook(Book):
    def __new__(cls, interaction: discord.Interaction, *pages: Page, timeout=DEFAULT_TIMEOUT, extra_buttons: tuple[CallbackButton]=(),
    page_title='Page'):
        if len(pages) > 1 or extra_buttons:
            return super().__new__(cls)
        else:
            pages[0].interaction = interaction
            
            return pages[0]
    
    def __init__(self, interaction: discord.Interaction, *pages: Page, timeout=DEFAULT_TIMEOUT, extra_buttons: tuple[CallbackButton]=(),
    page_title='Page'):
        self.left_button = CallbackButton(self.turn_page, interaction, -1, style=discord.ButtonStyle.primary, label='Previous')
        self.page_number = discord.ui.Button(disabled=True)
        self.right_button = CallbackButton(self.turn_page, interaction, 1, style=discord.ButtonStyle.primary, label='Next')
        # self.close_button = CallbackButton(self.manual_close, self.interaction, style=discord.ButtonStyle.danger, label='Close',
        # row=1)
        # self.view.add_item(self.close_button)

        self.page_title = page_title

        if len(pages) > 1:
            normal_buttons = [self.left_button, self.page_number, self.right_button]
        else:
            normal_buttons = []
        
        buttons_list = normal_buttons + list(extra_buttons)
        
        super().__init__(interaction, timeout, list(pages), buttons_list)

        self.update_buttons()
    
    '''
    async def close_book(self):
        self.view.clear_items()
        
        closed_button = discord.ui.Button(disabled=True, label=f'Time limit for using buttons already elapsed', row=0)
        
        self.view.add_item(closed_button)

        await self.interaction.edit_original_response(view=self.view)
    
    async def manual_close(self, button_interaction: discord.Interaction, message_interaction: discord.Interaction):
        self.view.stop()
    
    async def wait_until_finished(self):
        await self.view.wait()
        await self.close_book()
    '''
    
    def update_buttons(self):
        self.left_button.disabled = self.current_index <= 0
        self.right_button.disabled = self.current_index >= len(self.pages) - 1
        self.page_number.label = f'{self.page_title} {self.current_index + 1} / {len(self.pages)}'
    
    async def turn_page(self, button: CallbackButton, button_interaction: discord.Interaction, 
    message_interaction: discord.Interaction, direction: int):
        await (await self.cur_page(button_interaction)).deregister_self(button_interaction)

        self.current_index += direction
        
        self.update_buttons()

        await (await self.cur_page(button_interaction)).register_self(button_interaction)
        await self.edit_self(button_interaction)