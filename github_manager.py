from github3 import login
from github3.repos.contents import Contents
from getpass import getpass
import os
import argparse
import yaml
import requests
import time


class github_manager:

    _gh = None
    __password = None
    _user = None
    _jenkins_prefix = 'http://lcas.lincoln.ac.uk/jenkins/'
    _ros_dist = ['hydro', 'indigo']

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

    def jenkins_job_url(self, repo_name, ros_distro):
        return self._jenkins_prefix+'job/'+'devel-'+ros_distro+'-'+repo_name

    def jenkins_job_exists(self, repo_name, ros_distro):
        r = requests.get(self.jenkins_job_url(repo_name, ros_distro))
        return r.status_code == 200

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
                           note='github_manager',
                           note_url='https://github.com/strands-project/github_manager',
                           scopes=['user', 'repo']):
        if self._user is None:
            raise Exception('new tokens can only be generated'
                            + 'when logged in using user/passwd credentials')
        auth = self._gh.authorize(self._user,
                                  self.__password,
                                  scopes,
                                  note=note,
                                  note_url=note_url)
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
            time.sleep(0.2)

    def create_repo(
        self,
        name,
        organisation=None,
        owners=None,
        description=None
    ):
        if organisation is not None:
            org = self._gh.organization(organisation)
        else:
            org = self._gh
        repo = {}
        repo['name'] = name
        repo['description'] = description
        repo['has_issues'] = False
        repo['has_wiki'] = False
        repo['has_downloads'] = False
        repo['private'] = False
        repo = org.create_repo(
            name,
            description=description,
            has_issues=False,
            has_wiki=False,
            auto_init=True
        )
        if organisation is not None:
            team = org.create_team(
                name+'_admins',
                repo_names=[organisation + '/' + name],
                permission='admin'
            )
            for o in owners:
                team.add_member(o)

        else:
            for o in owners:
                repo.add_collaborator(o)
            #, 'description', 'homepage', 'private', 'has_issues','has_wiki', 'has_downloads']

    def generate_html_report(self, organisation=None, filter='all'):
        if organisation is not None:
            org = self._gh.organization(organisation)
        else:
            org = self._gh
        repos = org.iter_repos(filter)
        out = '<html><body><table>'
        for repo in repos:
            out += '<tr>'
            out += '<td><a href="' + str(repo.html_url) + '">' + repo.name + '</a></td>'
            out += '<td>' + repo.default_branch + '</td>'
            for rd in self._ros_dist:
                if self.jenkins_job_exists(str(repo.name), rd):
                    url = str(self.jenkins_job_url(str(repo.name), rd))
                    out += '<td><a href="' + url + '">'
                    out += '<img src="'+url+'/badge/icon"></a></td>'
                else:
                    out += '<td>---</td>'
            out += '</tr>'
        out += '</table></body></html>'
        return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='generate new app token for later authentication',
        epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr'
    )
    subparsers = parser.add_subparsers(help='commands', dest='command')
    #####
    gen_token_parser = subparsers.add_parser(
        'gen-token',
        help='generate a rosinstall output for all repositories of an organisation')
    gen_token_parser.add_argument(
        '--note',
        default='github_manager',
        help='note string for the app token. Default: github_manager')
    gen_token_parser.add_argument(
        '--note-url',
        default='github_manager',
        help='note url for the app token. Default: https://github.com/strands-project/github_manager')
    gen_token_parser.add_argument(
        '--scopes',
        default=['user', 'repo'],
        nargs='+',
        help='permission scopes for the app token. Default: [\'user\', \'repo\']')
    #####
    rosinstall_parser = subparsers.add_parser(
        'rosinstall',
        help='generate a rosinstall output for all repositories of an organisation')
    rosinstall_parser.add_argument(
        'organisation',
        help='organisation to look for')
    #####
    checkout_parser = subparsers.add_parser(
        'package-xml',
        help='checkout all package.xml in all repos of an organisation')
    checkout_parser.add_argument(
        'organisation',
        help='organisation to look for')
    checkout_parser.add_argument(
        'workspace',
        help='where to check out')
    #####
    repo_parser = subparsers.add_parser(
        'create-repo',
        help='checkout all package.xml in all repos of an organisation')
    repo_parser.add_argument(
        '--organisation',
        default=None,
        help='organisation to create in')
    repo_parser.add_argument(
        '--description', '-d',
        help='description of the repository')
    repo_parser.add_argument(
        '--owners', '-o',
        default=[],
        nargs='+',
        help='member with access to the repository')
    repo_parser.add_argument(
        'name',
        help='name of repository')
    #####
    report_parser = subparsers.add_parser(
        'report',
        help='generate HTML report about repositories')
    report_parser.add_argument(
        'organisation',
        help='organisation to look for')

    github_manager.config_argparse(parser)
    args = parser.parse_args()
    ghm = github_manager(args)
    if args.command == 'gen-token':
        token = ghm.generate_app_token(
            note=args.note,
            note_url=args.note_url,
            scopes=args.scopes)
        print token.token

    if args.command == 'rosinstall':
        ri = ghm.query_orga_repos(args.organisation)
        print yaml.dump(ri)

    if args.command == 'package-xml':
        ghm.checkout_all_package_xml(args.organisation, args.workspace)

    if args.command == 'create-repo':
        ghm.create_repo(
            args.name,
            args.organisation,
            args.owners,
            args.description)

    if args.command == 'report':
        report = ghm.generate_html_report(args.organisation)
        print report
