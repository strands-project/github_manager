from github3 import login, user, authorize
from getpass import getpass


class github_manager:

    _gh = None
    __password = None
    _user = None


    def __init__(self, user=None, token=None):
        if user is not None:
            self._user = user
            while not self.__password:
                self.__password = getpass('Password for {0}: '.format(user))

            self._gh = login(user, password=self.__password)
            return
        if token is not None:
            self._gh = login(token=token)
            return
        raise Exception('neither user name nor token succeeded')


    def query_orga_repos(self, organisation, filter='all'):
        org = self._gh.organization(organisation)
        repos = org.iter_repos(filter)

        rosinstall = []
        for r in repos:
            entry = {'git': {'local-name': str(r.name),
                             'uri': str(r.html_url),
                             'version': str(r.default_branch)}}
            rosinstall.append(entry)
        return rosinstall

    def generate_app_token(self, note = 'github_manager_app', note_url = 'https://github.com/marc-hanheide/ros_gh_mgr', scopes = ['user', 'repo']):
        if self._user is None:
            raise Exception('new tokens can only be generated when logged in using user/passwd credentials')
        auth = self._gh.authorize(self._user, self.__password, scopes, note, note_url)
        return auth

if __name__ == "__main__":
    ghm = github_manager(user='marc-hanheide')
    ri = ghm.query_orga_repos('strands-project')
    print ri
