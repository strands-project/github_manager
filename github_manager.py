from github3 import login, user
from getpass import getpass


class github_manager:

    _gh = None
    __password = None

    def __init__(self, user=None, token=None):
        if user is not None:
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


if __name__ == "__main__":
    ghm = github_manager('marc-hanheide')
    ri = ghm.query_orga_repos('strands-project')
    print ri