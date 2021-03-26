import tools

class Command: 
    COMMANDS = {} 

    def __init__(self, func, name, definite_usages, indefinite_usages, public): 
        self.name = name
        self.definite_usages = definite_usages
        self.indefinite_usages = indefinite_usages
        self.func = func
        self.public = public

        self.COMMANDS[self.name] = self
    
    @classmethod
    def get_command(cls, name): 
        return cls.COMMANDS.get(name.lower(), None) 
    
    @classmethod
    def all_commands(cls, public_only=True): 
        comms = cls.COMMANDS.values() 

        if public_only: 
            comms = filter(lambda comm: comm.public, comms) 
        
        return map(lambda comm: comm.name, comms) 
    
    def usages_str(self, client, c, m): 
        prefix = client.prefix(c) 

        usages_list = [] 

        for param_list, desc in self.definite_usages.items(): 
            usage = prefix + self.name

            if param_list: 
                usage += ' ' + tools.format_iterable(param_list, sep=' ') 

            use_and_desc = f'`{usage}` - {desc}' 

            usages_list.append(use_and_desc) 
        
        for param_list, desc in self.indefinite_usages.items(): 
            usage = prefix + self.name

            usage += ' ' + tools.format_iterable(param_list, sep=' ') 

            #desc += ' (spaces are permitted)' 

            use_and_desc = f'`{usage}` - {desc}' 

            usages_list.append(use_and_desc) 
        
        return tools.make_list(usages_list, bullet_point='') 
    
    def check_args(self, client, c, m, *args): 
        for usage in self.definite_usages: 
            if len(args) == len(usage): 
                return True

        for usage in self.indefinite_usages: 
            if len(args) >= len(usage): 
                return True
        
        return False
    
    async def run(self, client, c, m, *args): 
        return await self.func(client, c, m, *args) 
    
    async def attempt_run(self, client, c, m, *args): 
        incorrect = True

        if self.check_args(client, c, m, *args): 
            incorrect = await self.run(client, c, m, *args) 
        
        if incorrect: 
            usages_str = self.usages_str(client, c, m) 

            await client.send(c, content=f"""The correct ways to use this command are: 

{usages_str}""", reference=m) 