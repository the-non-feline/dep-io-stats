import tools

COMMANDS = {} 

class Command: 
    def __init__(self, name, usages, func): 
        self.name = name
        self.usages = usages
        self.func = func
    
    def usages_str(self, client, c, author): 
        prefix = client.prefix(c) 

        usages_list = [] 

        for param_list, desc in self.usages.items(): 
            usage = prefix + self.name

            if param_list: 
                usage += ' ' + tools.format_iterable(param_list, sep=' ') 

            use_and_desc = f'`{usage}` - {desc}' 

            usages_list.append(use_and_desc) 
        
        return tools.make_list(usages_list, bullet_point='') 
    
    def check_args(self, client, c, author, *args): 
        for usage in self.usages: 
            if len(args) == len(usage): 
                return True
        else: 
            return False
    
    async def run(self, client, c, author, *args): 
        await self.func(self, client, c, author, *args) 
    
    async def attempt_run(self, client, c, author, *args): 
        if self.check_args(client, c, author, *args): 
            await self.run(client, c, author, *args) 
        else: 
            usages_str = self.usages_str(client, c, author) 

            await client.send(c, content=f"""{author.mention}, the correct ways to use this command are: 

{usages_str}""") 