import requests

headers = {
    'origin': 'https://creators.deeeep.io',
}

r = requests.request('POST', 'https://apibeta.deeeep.io/auth/local/signin' , data={
    'email': 'pandinobud@gmail.com', 
    'password': '(Th1sisn0tcorrect)', 
}, headers=headers)

print(r.text)