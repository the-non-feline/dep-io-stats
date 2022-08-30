from datetime import datetime
import time
import math
import discord
from discord import app_commands

def format_iterable(iterable, formatter='{}', sep=', '):
    return sep.join((formatter.format(item) for item in iterable)) 

def make_list(iterable, bullet_point='• '): 
    return format_iterable(iterable, formatter=bullet_point + '{}', sep='\n')

def salt_url(url: str): 
    if '?' in url: 
        border = '&' 
    else: 
        border = '?' 
    
    return url + border + f'ds_salt={time.time_ns()}' 

def trunc_float(num): 
    if math.isfinite(num): 
        trunced = int(num) 

        if num == trunced: 
            num = trunced
    
    return num

def decamelcase(string): 
    words = [] 

    current_word = '' 

    for char in string: 
        if char.upper() == char: 
            if current_word: 
                words.append(current_word) 

                current_word = '' 
        
        current_word += char
    
    if current_word: 
        words.append(current_word) 

        current_word = '' 
    
    return words

def timestamp(t: datetime): 
    secs = int(t.timestamp()) 

    return f'<t:{secs}>'

def trim_maybe(string: str, limit: int, trail_off='...'):
    string = str(string) 
        
    if string and len(string) > limit: 
        string = string[:limit - len(trail_off)] + trail_off
    
    return string