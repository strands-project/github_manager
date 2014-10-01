from catkin_pkg import topological_order

import argparse
import os

import pygraphviz as pgv

from rosdistro import get_distribution_file, get_index, get_index_url


class dependency_report_generator:

    _workspace = '.'
    _index = None
    _distribution = None

    def __init__(self, workspace='.', distro='hydro'):
        self._workspace = workspace
        self._index = get_index(get_index_url())
        self._distribution = get_distribution_file(self._index, distro)
        self._get_packages()

    def _get_release_status(self, repo_name):
        if repo_name in self._distribution.repositories:
            r = self._distribution.repositories[repo_name]
            if r.release_repository:
                return 'release'
            if r.source_repository:
                return 'source'
        return None

    def _get_packages(self):
        to = topological_order.topological_order(self._workspace)

        result = {}
        for pname, pkg in to:
            pkg_info = {}
            pkg_info['path'] = os.path.dirname(pkg.filename)
            pkg_info['depends'] = list(set([str(d.name) for d in pkg.build_depends]
                                       + [str(d.name) for d in pkg.exec_depends]))
            pkg_info['description'] = (pkg.description)
            pkg_info['licenses'] = pkg.licenses
            pkg_info['authors'] = [(a.name) for a in pkg.authors]
            pkg_info['maintainers'] = [(m.name) for m in pkg.maintainers]
            #prefix, pkg_info['package'] = os.path.split(pkg_info['path'])
            prefix, pkg_info['package'] = os.path.split(pkg_info['path'])
            prefix, pkg_info['repo'] = os.path.split(prefix)
            if pkg_info['repo'] in self._workspace:
                pkg_info['repo'] = pkg_info['package']
            if pkg_info['repo']:
                pkg_info['release_status'] = self._get_release_status(pkg_info['repo'])
            result[pkg.name] = pkg_info
        self._pkgs = result

    def _get_repos(self):
        repos = {}
        for pname, pkg in self._pkgs.items():
            repo = pkg['repo']
            if repo not in repos:
                repos[repo] = []
            repos[repo].append(pname)
        return repos

    def generate_repo_dep_graph(self):
        dot = pgv.AGraph(directed=True,
                         strict=True,
                         splines='True',
                         compound=True,
                         rankdir='LR',
                         concentrate=False)

        sub_graphs = self._get_repos()

        for k, sg in sub_graphs.items():
            maintainers = ''
            for pn in sg:
                p = self._pkgs[pn]
                for m in p['maintainers']:
                    maintainers += '  ' + pn + ': ' + m + '<br align="left"/>'
                if p['release_status'] is None:
                    nc = 'red'
                else:
                    if p['release_status'] == 'release':
                        nc = 'green'
                    else:
                        nc = 'yellow'
                #break # it's enough to read one package of a repo...
            dot.add_node(k, label='<<I>'+k.upper()+'</I><br align="left"/>'+maintainers+'>', color=nc)

        for pname, pkg in self._pkgs.items():
            for dpkg in pkg['depends']:
                if dpkg in self._pkgs:
                    #dot.node(dpkg)
                    #nodes.append(dpkg)
                    repo1 = pkg['repo']
                    repo2 = self._pkgs[dpkg]['repo']
                    rs = self._pkgs[dpkg]['release_status']
                    if not repo1 == repo2:
                        if rs is None:
                            ec = 'red'
                        else:
                            if rs == 'release':
                                ec = 'green'
                            else:
                                ec = 'yellow'
                        dot.add_edge(repo1, repo2, weight=10, constraint=True, color=ec)
        return dot


    def generate_pkg_dep_graph(self, within_repo=True, between_repos=None):
        dot = pgv.AGraph(directed=True,
                         strict=True,
                         splines=True,
                         compound=True,
                         rankdir='LR',
                         concentrate=True,
                         overlap='scale')
        nodes = []
        for pname, pkg in self._pkgs.items():
            if pname not in nodes:
                repo = pkg['repo']
                nodes.append(pname)
                dot.add_node(pname, group=repo, label=pname + ' ['
                                                            + pkg['maintainers'][0]
                                                            + ', lic='
                                                            + pkg['licenses'][0]
                                                            + ']')

        sub_graphs = self._get_repos()

        for k, sg in sub_graphs.items():
            dot.add_subgraph(nbunch=sg,
                             name='cluster_'+k,
                             label=k,
                             style='filled',
                             fillcolor='lightgrey',
                             concentrate=True)
        for pname, pkg in self._pkgs.items():
            for dpkg in pkg['depends']:
                if dpkg in nodes:
                    #dot.node(dpkg)
                    #nodes.append(dpkg)
                    dp = self._pkgs[dpkg]
                    if within_repo and pkg['repo'] == dp['repo']:
                        dot.add_edge(pname, dpkg, constraint=True)
                    if not between_repos is None and not pkg['repo'] == dp['repo']:
                        if pkg['repo'] in between_repos or dp['repo'] in between_repos:
                            dot.add_edge(pname, dpkg, constraint=True)
        return dot


    def generate_markdown(self):
        repos = self._get_repos()
        outstr = u''
        tablehead = '| package | maintainer | authors | licence | depends on |\n'
        tableline = '| ------- | ---------- | ------- | ------- | ---------- |\n'

        for repo, pkgs in repos.iteritems():
            outstr += '\n# {0}\n\n'.format(repo)
            outstr += tablehead + tableline
            for p in pkgs:
                pkg = self._pkgs[p]
                
                outstr += u'| {0} | {1} | {2} | {3} | {4} |\n'.format(
                    p,
                    u', '.join(pkg['maintainers']),
                    u', '.join(pkg['authors']),
                    ', '.join(pkg['licenses']),
                    ', '.join(pkg['depends'])
                )
        return outstr






def main():
    parser = argparse.ArgumentParser(description='find all dependencies for packages within one path prefix',
                                     epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mode', choices=['repo', 'pkg','markdown'], help='display on repo or package level, default is "repo"', default='repo')
    parser.add_argument('--workspace', help='catkin workspace to parse default=\'.\'', default=os.getcwd())
    parser.add_argument('--output', help='name of the generated PDF, default is output.pdf', default='output.pdf')
    parser.add_argument('--distro', help='name of ROS distro, default: hydro', default='hydro')
    parser.add_argument('--inter-repos', nargs='+', help='show also inter-repository dependencies for these repositories in pkg mode')
    args = parser.parse_args()

    drg = dependency_report_generator(args.workspace, args.distro)
    if args.mode == 'pkg':
        dot = drg.generate_pkg_dep_graph(between_repos=args.inter_repos)
        dot.layout(prog='dot')
        dot.draw(args.output)
    if args.mode == 'repo':
        dot = drg.generate_repo_dep_graph()
        dot.layout(prog='dot')
        dot.draw(args.output)

    if args.mode == 'markdown':
        md = drg.generate_markdown()
        print md



if __name__ == "__main__":
    main()
