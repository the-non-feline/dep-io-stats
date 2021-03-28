import time
import math

def format_iterable(iterable, formatter='{}', sep=', '):
    return sep.join((formatter.format(item) for item in iterable)) 

def make_list(iterable, bullet_point='• '): 
    return format_iterable(iterable, formatter=bullet_point + '{}', sep='\n')

def salt_url(url): 
    if '?' in url: 
        border = '&' 
    else: 
        border = '?' 
    
    return url + border + f'ds_salt={time.time()}' 

def trunc_float(num): 
    if math.isfinite(num): 
        trunced = int(num) 

        if num == trunced: 
            num = trunced
    
    return num