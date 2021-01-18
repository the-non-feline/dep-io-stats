def format_iterable(iterable, formatter='{}', sep=', '):
    return sep.join((formatter.format(item) for item in iterable)) 

def make_list(iterable, bullet_point='• '): 
    return format_iterable(iterable, formatter=bullet_point + '{}', sep='\n')