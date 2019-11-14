#!/usr/bin/env python

import argparse
from pprint import pprint
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

    def __init__(self, distro='kinetic', orgas=['lcas'], tags=['lcas']):
        self._distro_name = distro
        self._distro = get_distro(distro)
        self._max_depth = 5
        self._orgas = orgas
        self._pkgs = {}
        self._repos = defaultdict(set)
        self._repo_deps = defaultdict(set)
        self._pkg2repo = defaultdict(str)
        self._orga_url = defaultdict(str)
        self._roots = []
        self._index = get_index(get_index_url())
        self._distributions = get_distribution_files(self._index, distro)
        self._distribution = None
        for d in self._distributions:
            if set(d.tags).intersection(set(tags)):
                self._distribution = d
                break


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

    def analyse_non_released_repos(self):
        def __checkout(url, branch, name, dir):
            check_call(["git", "clone", '--depth', '1', '-b', branch, url, name], cwd=dir)

        tmp_dir = mkdtemp()
        deps = {}
        rep2pkg = {}
        rep2pkg_names = {}
        pkg2rep = {}
        all_pkg = []

        try:
            for k, sg in self._distribution.repositories.items():
                #print sg.__dict__
                # if not released but source available, check it out and go over all
                # the packages within
                if sg.release_repository is None and sg.source_repository is not None:  # not released
                    try:
                        __checkout(
                            sg.source_repository.url,
                            sg.source_repository.version,
                            k, tmp_dir)
                        rep2pkg[k] = [
                            p[1] for p in topological_order.topological_order(
                            join(tmp_dir, k))]
                        rep2pkg_names[k] = [p.name for p in rep2pkg[k]]
                        for p in rep2pkg_names[k]:
                            pkg2rep[p] = k
                        all_pkg.extend(rep2pkg[k])
                        break  # FOR DEBUG ONLY
                    except Exception as e:
                        print(str(e))
                        continue
            for pkg in all_pkg:
                deps[pkg.name] = set([str(d.name) for d in pkg.build_depends]
                                      + [str(d.name) for d in pkg.exec_depends])
                # remove all dependencies in the same repository
                pkg_repo = pkg2rep[pkg.name]
                deps[pkg.name] = list(deps[pkg.name].difference(rep2pkg_names[pkg_repo]))
            pprint(deps)
        finally:
            rmtree(tmp_dir)


    def generate_repo_dep_graph(self):
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
        '--mode', choices=['repo', 'pkg', 'markdown'],
        help='display on repo or package level, default is "repo"',
        default='repo'
    )
    parser.add_argument(
        '--distro',
        help='name of ROS distro, default: kinetic',
        default='kinetic'
    )
    parser.add_argument(
        '--root',
        help='name of package from which the traversal starts,'
             ' default: empty (all)',
        default=''
    )
    parser.add_argument(
        '--orgas',
        help='list of git organisations to filter, space-separated',
        default='lcas iliad strands-project orebrouniversity'
                ' iliad-project federicopecora marc-hanheide'
    )
    parser.add_argument(
        '--tags',
        help='list of repository tags, space-separated',
        default='lcas'
    )
    args = parser.parse_args()

    _orgas = args.orgas.split(' ') if len(args.orgas)>0 else []
    _roots = args.root.split(' ') if len(args.root)>0 else []
    _tags = args.tags.split(' ') if len(args.tags)>0 else []
    #print _orgas
    ca = CacheAnalyser(distro=args.distro, orgas=_orgas, tags=_tags)
    ca.analyse_non_released_repos()
    return
    #ca.analyse('strands_apps')
    #print(get_package_names(ca._distro))
    ca.analyse_pkg(_roots)

    dot = ca.generate_repo_dep_graph()
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

