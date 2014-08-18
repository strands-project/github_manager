from github3 import login
import yaml

token = id = ''

CREDENTIALS_FILE = 'github.token'

with open(CREDENTIALS_FILE, 'r') as fd:
    token = fd.readline().strip()  # Can't hurt to be paranoid
    id = fd.readline().strip()

gh = login(token=token)

org = gh.organization('strands-project')
repos = org.iter_repos('all')

rosinstall = []
for r in repos:
    entry = {'git': {'local-name': str(r.name),
                     'uri': str(r.html_url),
                     'version': str(r.default_branch)}}
    rosinstall.append(entry)
print yaml.dump(rosinstall)
