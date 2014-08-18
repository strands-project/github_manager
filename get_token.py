from github3 import authorize
from getpass import getpass

user = 'marc-hanheide'
password = ''
CREDENTIALS_FILE = 'github.token'

while not password:
    password = getpass('Password for {0}: '.format(user))

note = 'github3.py example app'
note_url = 'http://example.com'
scopes = ['user', 'repo']

auth = authorize(user, password, scopes, note, note_url)

print auth.id

with open(CREDENTIALS_FILE, 'w') as fd:
    fd.write(auth.token + '\n')
    fd.write(str(auth.id))
