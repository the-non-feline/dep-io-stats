import discord
import logs
from logs import debug

class Report: 
    MAX_MESSAGE = 2000

    def __init__(self, interaction: discord.Interaction): 
        self.interaction = interaction
        self.contents = [] 
    
    async def send_message(self, sent_messages, texts, embed=None): 
        if len(texts) > 0 or embed is not None: 
            content = '\n'.join(texts) 

            debug(len(content)) 

            sent_messages.append(await self.interaction.followup.send(content=content, embed=embed)) 

            texts.clear() 
    
    def add(self, to_add): 
        self.contents.append(to_add) 
    
    async def send_self(self): 
        sent_messages = [] 

        to_send = [] 

        for message in self.contents: 
            if isinstance(message, discord.Embed): 
                await self.send_message(sent_messages, to_send, embed=message) 
            else: 
                buffer = to_send + [message] 
                proposed = '\n'.join(buffer) 

                if len(proposed) > self.MAX_MESSAGE: 
                    debug(len(proposed)) 

                    await self.send_message(sent_messages, to_send) 
                
                to_send.append(message) 
        
        await self.send_message(sent_messages, to_send) 
        
        self.contents.clear() 

        return sent_messages