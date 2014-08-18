from github3 import login, user
from getpass import getpass


class github_manager:

    _gh = None
    __password = None

    def __init__(self, user):
        while not self.__password:
            self.__password = getpass('Password for {0}: '.format(user))

        self._gh = login(user, password=self.__password)


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