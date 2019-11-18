from catkin_pkg import topological_order

import argparse
import os

from pprint import pprint
import pygraphviz as pgv

from collections import defaultdict
from rosinstall_generator.distro import get_distro, get_package_names
from rosinstall_generator.distro import get_recursive_dependencies, get_release_tag
from rosdistro import get_distribution_files, get_index, get_index_url

class Graph: 
    def __init__(self): 
        self.graph = defaultdict(set) #dictionary containing adjacency List 
        #self.V = vertices #No. of vertices 
  
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


class migration_analyser:

    _index = None
    _distribution = None

    def __init__(self, distro='kinetic', tags=['lcas']):
        self._index = get_index(get_index_url())
        self._distributions = get_distribution_files(self._index, distro)
        self._distribution = None
        for d in self._distributions:
            if set(d.tags).intersection(set(tags)):
                self._distribution = d
                break
        self._ri_dist = get_distro(distro)
        
        self._our_packages = {}

        release_packages_set = set(self._distribution.release_packages)
        pkg_dep_graph = Graph()
        rep_dep_graph = Graph()
        for p in release_packages_set:
            deps = get_recursive_dependencies(self._ri_dist, [p], limit_depth=1)
            e = {
                'name': p,
                'deps': deps.intersection(release_packages_set),  # only keep the ones in our repo file
                'repository': self._distribution.release_packages[p].repository_name
            }
            for d in e['deps']:
                pkg_dep_graph.addEdge(d, p)
                rep_dep_graph.addEdge(
                    self._distribution.release_packages[d].repository_name,
                    self._distribution.release_packages[p].repository_name,
                )
            self._our_packages[p] = e

        #pprint(g.graph)
        pkg_topo, pkg_level = pkg_dep_graph.topologicalSort()
        rep_topo, rep_level = rep_dep_graph.topologicalSort()
        #pprint(rep_topo)
        #pprint(pkg_level)

        for p in rep_topo:
            print('%s -> %d' % (p, rep_level[p]))
            #pprint(self._our_packages[p])

        

    


    def _get_release_status(self, repo_name):
        if repo_name in self._distribution.repositories:
            r = self._distribution.repositories[repo_name]
            if r.release_repository:
                return 'release'
            if r.source_repository:
                return 'source'
        return None

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







def main_old():
    parser = argparse.ArgumentParser(description='find all dependencies for packages within one path prefix',
                                     epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mode', choices=['repo', 'pkg','markdown'], help='display on repo or package level, default is "repo"', default='repo')
    parser.add_argument('--workspace', help='catkin workspace to parse default=\'.\'', default=os.getcwd())
    parser.add_argument('--output', help='name of the generated PDF, default is output.pdf', default='output.pdf')
    parser.add_argument('--distro', help='name of ROS distro, default: hydro', default='hydro')
    parser.add_argument('--inter-repos', nargs='+', help='show also inter-repository dependencies for these repositories in pkg mode')
    args = parser.parse_args()

    drg = migration_analyser(args.workspace, args.distro)
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


def main():
    drg = migration_analyser()
    #pprint(drg._our_packages)
    
    



if __name__ == "__main__":
    main()
