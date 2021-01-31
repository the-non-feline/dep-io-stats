import logging

logger = logging.getLogger(__name__) 

logger.setLevel(logging.DEBUG) 

def debug(msg, *args, **kwargs): 
    try: 
        logger.debug(f'{msg}\n', *args, **kwargs) 
    except UnicodeEncodeError: 
        debug('Could not log message', exc_info=True) 

def clear_file(file, should_log=True):
    file.seek(0)
    file.truncate(0)

    if should_log: 
        debug('cleared') 

def trim_file(file, max_size): 
    debug('trimming\n\n') 

    if not file.closed and file.seekable() and file.readable(): 
        file.seek(0, 2) 

        size = file.tell() 

        #debug(f'file is {size} bytes now') 

        if size > max_size: 
            extra_bytes = size - max_size

            file.seek(extra_bytes) 

            contents = file.read() 

            #trimmed_contents = contents[len(contents) - self.max_size - 1:] 

            #debug(len(contents)) 
            #debug(len(trimmed_contents)) 
            
            clear_file(file, should_log=False) 

            file.seek(0) 

            file.write(contents) 

            file.flush() 