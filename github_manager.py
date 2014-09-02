from github3 import login
from github3.repos.contents import Contents
from getpass import getpass
import os
import argparse
import yaml


class github_manager:

    _gh = None
    __password = None
    _user = None

    @staticmethod
    def config_argparse(parser):
        parser.add_argument('--user',
                            help='the github user name', default=None)
        parser.add_argument('--token',
                            help='the github user name', default=None)

    def __init__(self, args):
        if args.user is not None:
            self._user = args.user
            while not self.__password:
                self.__password = getpass(
                    'Password for {0}: '.format(args.user)
                )

            self._gh = login(args.user, password=self.__password)
            return
        if args.token is not None:
            self._gh = login(token=args.token)
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

    def search_file(self, repo, content, depth, max_depth, fname):
        res = []

        if isinstance(content, Contents):
            return []
        if isinstance(content, dict):
            for n, c in content.iteritems():
                if n == fname:
                    res.append(str(c.path))
                if c.type == 'dir' and depth < max_depth:
                    res = res + (self.search_file(repo,
                                 repo.contents(c.path),
                                 depth+1, max_depth, fname))
            return res
        return []

    def get_package_xmls_from_repo(self, repo, depth):
        top_level_content = repo.contents('/')
        return self.search_file(repo, top_level_content,
                                0, depth, 'package.xml')

    def get_package_xmls(self, organisation, depth):
        org = self._gh.organization(organisation)
        repos = org.iter_repos('all')

        res = {}
        for r in repos:
            print r.name
            k = str(r.name)
            res[k] = self.get_package_xmls_from_repo(r, depth)
            print res[k]
        return res

    def _checkout_text_files(self, repo, files_list, dest_dir='.'):
        for fname in files_list:
            c = repo.contents(fname)

            dn = os.path.join(dest_dir, os.path.dirname(c.path))
            if not os.path.exists(dn):
                os.makedirs(dn)
            with open(os.path.join(dest_dir, fname), "w") as text_file:
                text_file.write(c.decoded)

    def generate_app_token(self,
                           note='github_manager_app',
                           note_url='ros_gh_mgr',
                           scopes=['user', 'repo']):
        if self._user is None:
            raise Exception('new tokens can only be generated'
                            + 'when logged in using user/passwd credentials')
        auth = self._gh.authorize(self._user,
                                  self.__password,
                                  scopes,
                                  note,
                                  note_url)
        return auth

    def checkout_package_xml(self, repo, workspace):
        pxml = self.get_package_xmls_from_repo(repo, 1)
        ghm._checkout_text_files(repo, pxml, workspace)

    def checkout_all_package_xml(self, orga, workspace, filter='all'):
        org = self._gh.organization(orga)
        repos = org.iter_repos(filter)
        for repo in repos:
            print "checking out package.xmls from repository " + repo.name
            pxml = ghm.get_package_xmls_from_repo(repo, 1)
            ghm._checkout_text_files(repo, pxml,
                                     os.path.join(workspace, repo.name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='generate new app token for later authentication',
        epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr'
    )
    subparsers = parser.add_subparsers(help='commands', dest='command')

    gen_token_parser = subparsers.add_parser(
        'gen-token',
        help='generate a rosinstall output for all repositories of an organisation')

    rosinstall_parser = subparsers.add_parser(
        'rosinstall',
        help='generate a rosinstall output for all repositories of an organisation')
    rosinstall_parser.add_argument(
        'organisation',
        help='organisation to look for')

    checkout_parser = subparsers.add_parser(
        'package-xml',
        help='checkout all package.xml in all repos of an organisation')
    checkout_parser.add_argument(
        'organisation',
        help='organisation to look for')
    checkout_parser.add_argument(
        'workspace',
        help='where to check out')


    github_manager.config_argparse(parser)
    args = parser.parse_args()
    print args
    ghm = github_manager(args)
    if args.command == 'gen-token':
        token = ghm.generate_app_token()
        print token.token

    if args.command == 'rosinstall':
        ri = ghm.query_orga_repos(args.organisation)
        print yaml.dump(ri)

    if args.command == 'package-xml':
        ghm.checkout_all_package_xml(args.organisation, args.workspace)
