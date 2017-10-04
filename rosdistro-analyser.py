#!/usr/bin/env python

import argparse
from pprint import pprint

from rosinstall_generator.distro import get_distro, get_package_names
from rosinstall_generator.distro import get_recursive_dependencies, get_release_tag

from collections import defaultdict


import xml.etree.ElementTree as ET

from copy import copy


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

    def __init__(self, distro='kinetic', orgas='lcas'):
        self._distro = get_distro(distro)
        self._max_depth = 5
        self._orgas = orgas
        self._pkgs = {}
        self._repos = defaultdict(set)
        self._repo_deps = defaultdict(set)
        self._pkg2repo = defaultdict(str)
        self._orga_url = defaultdict(str)

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

    def analyse_pkg(self, pkg_name):
        self._analyse_pkg(pkg_name)
        self.clean_out()
        self.repo_collect()

    def generate_md_package(self, pkg):
        str = '| [%s](apt://ros-kinetic-%s) | %s | %s | %s | %s |\n' % (
            pkg['name'],
            pkg['name'].replace('_', '-'),
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

        str += '\n## `rosinstall` definition:\n'
        str += '\n```\n%s```\n' % (
            self.generate_rosinstall(repo)
        )
        str += '\n## Included Packages:\n'

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
        repos = self.repo_collect()
        # outstr = u''
        # tablehead = '| package | maintainer | authors | licence | depends on |\n'
        # tableline = '| ------- | ---------- | ------- | ------- | ---------- |\n'
        outstr = u''
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


    def analyse(self, root_pkg):
        released_names, unreleased_names = get_package_names(self._distro)
        pprint(
            unreleased_names
            #get_recursive_dependencies(self._distro, ['strands_apps'], source=True)
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
             ' default: iliad_restricted',
        default='iliad_distribution'
    )
    parser.add_argument(
        '--orgas',
        help='list of git organisations to filter, space-separated',
        default='lcas iliad strands-project orebrouniversity'
                ' iliad-project federicopecora marc-hanheide'
    )
    args = parser.parse_args()

    _orgas = args.orgas.split(' ')
    ca = CacheAnalyser(distro=args.distro, orgas=_orgas)
    #ca.analyse('strands_apps')
    ca.analyse_pkg(args.root)

    ostr = ''
    for o in _orgas:
        if ca._orga_url[o.lower()] is not '':
            ostr += '* [%s](%s)\n' % (
                o,
                ca._orga_url[o.lower()]
            )

    print ('This is an overview of repositories and packages '
           'that form part of the `%s` distribution. Included are '
           'all repositories and packages that `%s` depends on '
           'and are hosted under one of the following organisations:\n'
           '%s\n'
           '_This page is auto-generated for ROS distribution `%s`._\n\n' %
           (args.root, args.root, ostr, args.distro)
           )

    print(ca.generate_markdown_repos())
    #pprint(ca._pkgs)
    #pprint(dict(ca._repo_deps))
    #pprint(dict(ca._repos))

if __name__ == "__main__":
    main()

