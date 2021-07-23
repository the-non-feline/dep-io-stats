import grequests
import logs
from logs import debug

class CredMan: 
    def __init__(self, client, credentials): 
        self.client = client
        self.credentials = credentials
        self.tokens = [None] * len(self.credentials) 
    
    def request_tokens(self, needed_num): 
        start_index = None

        debug(f'requested {needed_num} tokens') 

        # find the first token that is None
        for index in range(needed_num): 
            token = self.tokens[index] 

            if token is None: 
                start_index = index

                break
            else: 
                debug(f'already have token {index + 1} ({token})') 
        
        if start_index is not None: 
            requests_list = [] 

            for index in range(start_index, needed_num): 
                email, password = creds = self.credentials[index] 

                request = grequests.request('POST', self.client.LOGIN_URL, data={
                    'email': email, 
                    'password': password, 
                }) 

                requests_list.append(request) 
                
            jsons = self.client.async_get(*requests_list) 

            for index in range(len(jsons)): 
                json = jsons[index] 

                insert_index = start_index + index
                token_number = insert_index + 1

                if json: 
                    token = json['token'] 

                    self.tokens[insert_index] = token

                    debug(f'fetched token {token_number} ({token})') 
                else: 
                    debug(f'error fetching token {token_number}, which is currently ({self.tokens[insert_index]})') 
    
    def clear_tokens(self): 
        for index in range(len(self.tokens)): 
            self.tokens[index] = None
        
        debug('cleared tokens') 