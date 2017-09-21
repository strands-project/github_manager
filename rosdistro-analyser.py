#!/usr/bin/env python

import argparse
from pprint import pprint

from rosinstall_generator.distro import get_distro, get_package_names
from rosinstall_generator.distro import get_recursive_dependencies, get_release_tag

from collections import defaultdict


import xml.etree.ElementTree as ET

from copy import copy

def dictify(r,root=True):
    if root:
        return {r.tag : dictify(r, False)}
    d=copy(r.attrib)
    if r.text:
        d["_text"]=r.text
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag]=[]
        d[x.tag].append(dictify(x,False))
    return d

class CacheAnalyser:

    def __init__(self, distro='kinetic'):
        self._distro = get_distro(distro)
        self._max_depth = 2
        self._pkgs = {}
        self._repos = defaultdict(set)

    def parse_package_xml(self, package):
        xml = self._distro.get_release_package_xml(package)
        root = ET.fromstring(xml)
        return dictify(root)



    def analyse_pkg(self, pkg_name, depth=0):
        if depth > self._max_depth:
            return
        deps = get_recursive_dependencies(self._distro,
                                          [pkg_name], limit_depth=1)
        pkg = self._distro.release_packages[pkg_name]
        repo = self._distro.repositories[pkg.repository_name]
        s = {
            'depth': depth,
            'depends': list(deps)
        }
        self._repos[repo.name].add(pkg_name)
        if repo.release_repository:
            s['release'] = {
            #    'repo': repo.release_repository,
                'name': repo.release_repository.name,
                'url': repo.release_repository.url,
                'version': repo.release_repository.version
            }

        if repo.source_repository:
            s['source'] = {
                #'repo': repo.source_repository,
                'name': repo.source_repository.name,
                'url': repo.source_repository.url,
                'orga': repo.source_repository.url.split('/')[3],
                'branch': repo.source_repository.version
            }
            if s['source']['orga'] in ['lcas', 'iliad']:
                s['package_xml'] = self.parse_package_xml(pkg_name)
                self._pkgs[pkg_name] = s


        for p in deps:
            self.analyse_pkg(p, depth + 1)

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
    args = parser.parse_args()

    ca = CacheAnalyser(distro=args.distro)
    #ca.analyse('strands_apps')
    ca.analyse_pkg('iliad_distribution')
    pprint(ca._pkgs)
    pprint(dict(ca._repos))

if __name__ == "__main__":
    main()

