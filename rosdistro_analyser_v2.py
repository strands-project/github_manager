#!/usr/bin/env python

import argparse
from pprint import pprint, pformat
from sys import stderr
from shutil import rmtree

from rosinstall_generator.distro import get_distro, get_package_names
from rosinstall_generator.distro import get_recursive_dependencies, get_release_tag

from collections import defaultdict
import pygraphviz as pgv

from rosdistro import get_distribution_files, get_index, get_index_url
from tempfile import mkdtemp

import xml.etree.ElementTree as ET
from subprocess import check_call
from os.path import join
from copy import copy
from catkin_pkg import topological_order


class Graph: 
    def __init__(self): 
        self.graph = defaultdict(set) #dictionary containing adjacency List 
        #self.V = vertices #No. of vertices 

    def __str__(self):
        return pformat(dict(self.graph))
  
    # function to add an edge to graph 
    def addEdge(self,u,v): 
        self.graph[u].add(v) 
  
    # A recursive function used by topologicalSort 
    def topologicalSortUtil(self,v,visited,stack, level): 
  
        # Mark the current node as visited. 
        visited[v] = level
        # Recur for all the vertices adjacent to this vertex 
        if v in self.graph:
            for i in self.graph[v]: 
                if visited[i] < 0: 
                    self.topologicalSortUtil(i,visited,stack, level + 1) 
  
        # Push current vertex to stack which stores result 
        stack.insert(0,v) 
  
    # The function to do Topological Sort. It uses recursive  
    # topologicalSortUtil() 
    def topologicalSort(self): 
        # Mark all the vertices as not visited 
        visited = defaultdict(lambda: -1)
        #for v in self.graph: 
        #    visited[v] = False
        stack =[] 
  
        # Call the recursive helper function to store Topological 
        # Sort starting from all vertices one by one 
        for i in self.graph: 
            if visited[i] < 0 and i in self.graph: 
                self.topologicalSortUtil(i,visited,stack,1) 
  
        # Print contents of stack 
        return stack , visited



def dictify(r, root=True):
    if root:
        return {r.tag: dictify(r, False)}
    d = copy(r.attrib)
    if r.text:
        d["_text"] = r.text
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag] = []
        d[x.tag].append(dictify(x, False))
    return d


class CacheAnalyser:

    def __init__(self, distro='kinetic', tags=['lcas']):
        self._distro_name = distro
        self._distro = get_distro(distro)
        self._pkgs = {}
        __repo_template = {
            'packages': {},
            'type': 'git',
            'url': None,
            'version': 'master',
            'requires_repositories': set([]),
            'required_by_repositories': set([]),
            'status': 'unknown',
            'jenkins_job': None
        }
        __pkg_template = {
            'name': None,
            'authors': [],
            'maintainers': [],
            'description': '',
            'license': 'unknown',
            'status': 'unknown',
            'deps': set([]),
            'repository': None
        }
        self._repositories = defaultdict(lambda: dict(__repo_template))
        self._pkgs = defaultdict(lambda: dict(__pkg_template))


        self._repo_deps = {}
        self._pkg2repo = defaultdict(lambda: None)
        self._index = get_index(get_index_url())
        self._distributions = get_distribution_files(self._index, distro)

        self._distribution = None
        for d in self._distributions:
            if set(d.tags).intersection(set(tags)):
                self._distribution = d
                break
        # find only the first release platform and assume it's the right one...
        self._release_platform = self._distribution.release_platforms['ubuntu'][0]
        self.__jenkins_url_template_dev = (
            'https://lcas.lincoln.ac.uk/buildfarm/job/%sdev__%%s__ubuntu_%s_amd64/'
            % (
                self._distro_name[0].upper(),
                self._release_platform
                )
            )

        self._distro_repositories = self._distribution.repositories
        self._released_packages_set = set(self._distribution.release_packages)
        self.pkg_requires_graph = Graph()
        self.rep_requires_graph = Graph()                
        self.pkg_required_by_graph = Graph()
        self.rep_required_by_graph = Graph()                

    def _analyse_repos(self):
        tmp_dir = mkdtemp()
        try:
            for r, sg in self._distro_repositories.items():
                try:
                    if sg.release_repository is not None:  # released
                        self._repositories[r]['packages'] = self._analyse_released_repo(sg)
                        self._repositories[r]['status'] = 'released'
                    elif sg.source_repository is not None:  # not released but source available
                        self._repositories[r]['packages'] = self._analyse_non_released_repo(sg, tmp_dir)
                        self._repositories[r]['status'] = 'source'
                    if sg.source_repository:
                        self._repositories[r]['type'] = sg.source_repository.type
                        self._repositories[r]['url'] = sg.source_repository.url
                        self._repositories[r]['version'] = sg.source_repository.version
                        self._repositories[r]['jenkins_job'] = self.__jenkins_url_template_dev % (
                            r
                        )
                        
                    self._pkgs.update(self._repositories[r]['packages'])
                except Exception  as e:
                    print "skipping %s as exception occured: %s" % (r, str(e))

        finally:
            rmtree(tmp_dir)
        pprint(dict(self._repositories))

    def _extract_from_package_xml(self, px):
        return {
            'authors': ([a['_text']
                            for a in px['author']]
                        if 'author' in px
                        else ''),
            'maintainers': ([a['_text']
                                for a in px['maintainer']]
                            if 'maintainer' in px
                            else ''),
            'description': (' '.join(
                            [a['_text']
                                for a in px['description']])
                            if 'description' in px
                            else ''),
            'license': (' '.join(
                            [a['_text']
                                for a in px['license']])
                        if 'license' in px
                        else '')
        }

    def _analyse_released_repo(self, sg):
        _pkg={}
        for p in sg.release_repository.package_names:
            deps = get_recursive_dependencies(self._distro, [p], limit_depth=1)
            e = {
                'name': p,
                'status': 'released',
                'deps': deps,  
                'repository': self._distribution.release_packages[p].repository_name
            }
            px = self.parse_package_xml(p)['package']
            e.update(self._extract_from_package_xml(px))


            _pkg[p] = e 
            # only create graph for packages in this distribution
            for d in deps.intersection(self._released_packages_set):
                self.pkg_requires_graph.addEdge(p, d)
                self.pkg_required_by_graph.addEdge(d, p)
                if self._distribution.release_packages[d].repository_name != self._distribution.release_packages[p].repository_name:
                    self.rep_requires_graph.addEdge(
                        self._distribution.release_packages[p].repository_name,
                        self._distribution.release_packages[d].repository_name,
                    )
                    self.rep_required_by_graph.addEdge(
                        self._distribution.release_packages[d].repository_name,
                        self._distribution.release_packages[p].repository_name,
                    )
            return _pkg

    def _analyse_non_released_repo(self, sg, tmp_dir):
        _pkgs={}

        try:
            self.__checkout(
                sg.source_repository.url,
                sg.source_repository.version,
                sg.name, tmp_dir)
            pkgs = [
                p[1] for p in topological_order.topological_order(
                    join(tmp_dir, sg.name))
                    ]
            pkgs_names = [p.name for p in pkgs]
        except Exception as e:
            print(str(e))
            return

        for pkg in pkgs:
            e = {
                'name': pkg.name,
                'status': 'source',
                'deps': set([str(d.name) for d in pkg.build_depends]
                            + [str(d.name) for d in pkg.exec_depends]),
                'repository': sg.name,
                'authors': [str(a.name) for a in pkg.authors],
                'maintainers': [str(a.name) for a in pkg.maintainers],
                'license': ', '.join(pkg.licenses)
            }
            _pkgs[pkg.name] = e 
        
        return _pkgs

    def __checkout(self, url, branch, name, dir):
        check_call(["git", "clone", '--depth', '1', '-b', branch, url, name], cwd=dir)


####################

    def parse_package_xml(self, package):
        xml = self._distro.get_release_package_xml(package)
        root = ET.fromstring(xml)
        return dictify(root)

    def clean_out(self):
        for rd in self._repo_deps:
            self._repo_deps[rd] = self._repo_deps[rd].intersection(self._repos)
            if rd in self._repo_deps[rd]:
                self._repo_deps[rd].remove(rd)

    def repo_collect(self):
        d = {}
        for r in self._repos:

            d[r] = {
                'deps': self._repo_deps[r],
                'name': r,
                'url': self._distro.repositories[r].source_repository.url,
                'version':
                    self._distro.repositories[r].source_repository.version,
                'packages_depended_on': self._repos[r],
                'packages': {p: self._pkgs[p] for p in self._repos[r]},
                'contained_packages':
                    self._distro.repositories[r]
                    .release_repository.package_names
            }
        return d

    def analyse_pkg(self, pkg_names=[]):
        if not pkg_names:
            pkg_names = set(self._distribution.release_packages)
        self._roots = pkg_names
        for p in pkg_names:
            self._analyse_pkg(p)
        self.clean_out()
        self.repos = self.repo_collect()

        #self.repo_collect()

    def generate_md_package(self, pkg):
        str = '| [`%s`](apt://ros-%s-%s): _%s_ | %s | %s | %s | %s |\n' % (
            pkg['name'],
            self._distro_name,
            pkg['name'].replace('_', '-'),
            pkg['package']['description'],
            ', '.join(pkg['package']['maintainers']),
            ', '.join(pkg['package']['authors']),
            pkg['package']['license'],
            ', '.join(
                ['[`%s`](#%s) ' % (d, self._pkg2repo[d])
                    for d in pkg['depends']]
            )
        )
        # str  = '  * Depends on pkgs: '
        # for d in pkg['depends']:
        #     str += '[`%s`](#package-%s) ' % (d, d)
        # str += '\n'
        # str += '  * Maintainers: %s\n' % ', '.join(pkg['package']['maintainers'])
        # str += '  * Authors: %s\n' % ', '.join(pkg['package']['authors'])
        # str += '  * License: %s\n' % pkg['package']['license']
        return str

    def generate_rosinstall(self, repo):
        str = (
            "- git:\n"
            "    local-name: %s\n"
            "    uri: %s\n"
            "    version: %s\n")
        str = str % (
            repo['name'],
            repo['url'],
            repo['version']
        )
        return str

    def generate_md_repo(self, repo):
        str = '---\n\n# [%s](%s)\n' % (repo['name'], repo['url'])
        str += 'Source Code: %s (branch: %s)\n\n' % (
            repo['url'], repo['version']
        )

        str += '\n__`rosinstall` definition:__\n'
        str += '\n```\n%s```\n' % (
            self.generate_rosinstall(repo)
        )
        str += '\n__included packages:__\n\n'

        tablehead = '| package | maintainer | authors | licence | depends on |\n'
        tableline = '| ------- | ---------- | ------- | ------- | ---------- |\n'
        str += tablehead + tableline
        for p in repo['packages']:
            # str+='## Package **%s**\n*%s*\n' % (
            #     p, repo['packages'][p]['package']['description']
            # )
            str+=self.generate_md_package(repo['packages'][p])
        return str

    def generate_markdown_repos(self):
        repos = self.repos
        # outstr = u''
        # tablehead = '| package | maintainer | authors | licence | depends on |\n'
        # tableline = '| ------- | ---------- | ------- | ------- | ---------- |\n'
        outstr = u''
        outstr += ('\n'
                   '## Install released packages\n'
                   'See the [documentation]'
                   '(https://github.com/LCAS/rosdistro/wiki'
                   '#using-the-l-cas-repository-if-you-'
                   'just-want-to-use-our-software) '
                   'to enable the Ubuntu repositories to be ready to '
                   'install binary releases. '
                   'To install all packages documented here, '
                   'simply run \n\n```\n'
                   'sudo apt install <PACKAGENAME>\n```\n\n'
                   'after having enabled the repositories.\n\n')
        outstr += ('\n'
                   '## Cloning all repositories\n'
                   'Copy the following code block into the file '
                   '`.rosinstall` in your `src/` directory of your '
                   'workspace and run `wstool up` to pull in all '
                   'sources at once. An easy way to do it is '
                   '`cat >> .rosinstall` and pasting the block below, '
                   'followed by `[Ctrl-D]`, and then runnning `wstool up`. '
                   'In order to the install all dependencies required '
                   'to compile the code, simply do this in your source dir:\n'
                   '1. `rosdep update`\n'
                   '2. `rosdep install -i --from-paths .`\n'
                   )
        outstr += '\n\n```\n'
        for repo in repos:
            outstr += self.generate_rosinstall(repos[repo])
        outstr += '\n```\n\n'

        for repo in repos:
            outstr += self.generate_md_repo(repos[repo])

        return outstr

    def _analyse_pkg(self, pkg_name, depth=0):
        if depth > self._max_depth:
            return
        deps = get_recursive_dependencies(self._distro,
                                          [pkg_name], limit_depth=1)
        pkg = self._distro.release_packages[pkg_name]
        repo = self._distro.repositories[pkg.repository_name]
        s = {
            'depth': depth,
            'depends': list(deps),
            'name': pkg_name
        }

        if repo.source_repository:
            s['source'] = {
                #'repo': repo.source_repository,
                'name': repo.source_repository.name,
                'url': repo.source_repository.url,
                'orga': repo.source_repository.url.split('/')[3],
                'branch': repo.source_repository.version
            }
            if s['source']['orga'].lower() in self._orgas:
                self._orga_url[s['source']['orga'].lower()] =\
                    '/'.join(
                        repo.source_repository.url.split('/')[:4]
                    )
                if repo.release_repository:
                    s['release'] = {
                    #    'repo': repo.release_repository,
                        'name': repo.release_repository.name,
                        'url': repo.release_repository.url,
                        'version': repo.release_repository.version
                    }
                s['package_xml'] = self.parse_package_xml(pkg_name)
                px = s['package_xml']['package']
                s['package'] = {
                    'authors': ([a['_text']
                                 for a in px['author']]
                                if 'author' in px
                                else ''),
                    'maintainers': ([a['_text']
                                     for a in px['maintainer']]
                                    if 'maintainer' in px
                                    else ''),
                    'description': (' '.join(
                                    [a['_text']
                                     for a in px['description']])
                                    if 'description' in px
                                    else ''),
                    'license': (' '.join(
                                    [a['_text']
                                     for a in px['license']])
                                if 'license' in px
                                else '')
                }
                self._repos[repo.name].add(pkg_name)
                self._pkg2repo[pkg_name] = repo.name

                self._pkgs[pkg_name] = s
                for p in deps:
                    d_pkg = self._distro.release_packages[p]
                    d_repo = self._distro.repositories[d_pkg.repository_name]
                    self._repo_deps[repo.source_repository.name].add(d_repo.name)
                    self._analyse_pkg(p, depth + 1)

    def analyse_repo(self, repo):
        pprint(self._distro.repositories[repo].source_repository.__dict__)
        pprint(self._distro.repositories[repo].release_repository.__dict__)


    def analyse(self):
        released_names, unreleased_names = get_package_names(self._distro)
        pprint(
            unreleased_names
            #get_recursive_dependencies(self._distro, ['strands_apps'], source=True)
        )


    def generate_repo_requires_graph(self):
        dot = pgv.AGraph(label="<<B>Dependency Graph of Repositories</B>>",
                         directed=True,
                         strict=True,
                         splines='True',
                         compound=True,
                         rankdir='TB',
                         concentrate=False)

        for k, sg in self.repos.items():
            pstr = ''
            for pname, pkg in sg['packages'].items():
                # pstr += '  <I>%s </I>(%s)<BR ALIGN="LEFT"/>' % (
                #     pname, ', '.join(pkg['package']['maintainers']))
                pstr += '  <I>%s</I><BR ALIGN="LEFT"/>' % (
                    pname)
            pstr += ''
            # maintainers = ''
            # for pn in sg['packages']:
            #     p = sg['packages']
            #     for m in p['maintainers']:
            #         maintainers += '  ' + pn + ': ' + m + '<br align="left"/>'
            #     if p['release_status'] is None:
            #         nc = 'red'
            #     else:
            #         if p['release_status'] == 'release':
            #             nc = 'green'
            #         else:
            #             nc = 'yellow'
            #dot.add_node(k, label='<<I>'+k.upper()+'</I><br align="left"/>'+maintainers+'>', color=nc)
            label = ('<<B>%s</B><BR ALIGN="LEFT"/>'
                        '<FONT POINT-SIZE="8">%s</FONT>>' %
                        (k.lower(), pstr))

            dot.add_node(k,
                         label=label)

            for dr in sg['deps']:
                dot.add_edge(k, dr, weight=10, constraint=True)

        # for pname, pkg in self._pkgs.items():
        #     for dpkg in pkg['depends']:
        #         if dpkg in self._pkgs:
        #             #dot.node(dpkg)
        #             #nodes.append(dpkg)
        #             repo1 = pkg['repo']
        #             repo2 = self._pkgs[dpkg]['repo']
        #             rs = self._pkgs[dpkg]['release_status']
        #             if not repo1 == repo2:
        #                 if rs is None:
        #                     ec = 'red'
        #                 else:
        #                     if rs == 'release':
        #                         ec = 'green'
        #                     else:
        #                         ec = 'yellow'
        #                 dot.add_edge(repo1, repo2, weight=10, constraint=True, color=ec)
        return dot

    def preamble(self):
        ostr = ''
        for o in self._orgas:
            if self._orga_url[o.lower()] is not '':
                ostr += '[%s](%s) ' % (
                    o,
                    self._orga_url[o.lower()]
                )

        return ('This is an overview of repositories and packages '
                'that form part of the distribution. Included are '
                'all repositories and packages that are '
                'hosted under one of the following organisations:\n'
                '%s\n'
                '_This page is autogenerated for ROS distribution `%s`._\n'
                '\n'
                '_Dependency Graph (download as [PDF](repos-%s.pdf))_\n'
                '[![repos](repos-%s.png)](repos-%s.png)' %
                (
                    ostr,
                    self._distro_name, self._distro_name, self._distro_name, self._distro_name
                    )
                )


def main():
    parser = argparse.ArgumentParser(
        description='analyse a rosdistro',
        epilog='(c) Marc Hanheide 2017',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--distro',
        help='name of ROS distro, default: kinetic',
        default='kinetic'
    )
    parser.add_argument(
        '--tags',
        help='list of repository tags, space-separated',
        default='lcas'
    )
    args = parser.parse_args()

    _tags = args.tags.split(' ') if len(args.tags)>0 else []
    #print _orgas
    ca = CacheAnalyser(distro=args.distro, tags=_tags)
    ca._analyse_repos()
    #ca.analyse_non_released_repos()
    return
    #ca.analyse('strands_apps')
    #print(get_package_names(ca._distro))
    ca.analyse_pkg(_roots)

    dot = ca.generate_repo_requires_graph()
    dot.layout(prog='dot')
    dot.draw('repos-%s.png' % args.distro)
    dot.draw('repos-%s.pdf' % args.distro)

    print(ca.preamble())
    print(ca.generate_markdown_repos())
    #pprint(ca._pkgs)
    #pprint(dict(ca._repo_deps))
    #pprint(dict(ca._repos))

if __name__ == "__main__":
    main()

