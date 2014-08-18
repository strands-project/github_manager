import rospkg
import argparse

import pygraphviz as pgv


def get_packages(prefix='/'):
    rp = rospkg.RosPack()
    pnames = rp.list()
    pkgs={}
    if not prefix[-1:] == '/':
        prefix = prefix + '/'
    for pname in pnames:
        pkg={}
        pkg['path'] = rp.get_path(pname)
        pkg['manifest'] = rp.get_manifest(pname)
        pkg['depends'] = pkg['manifest'].depends
        pkg['description'] = pkg['manifest'].description
        pkg['license'] = pkg['manifest'].license
        pkg['author'] = pkg['manifest'].author
        if pkg['path'].find(prefix) == 0:
            pkg['path'] = pkg['path'][len(prefix):]
            pkg['repo'] = pkg['path'].replace('/'+pname, '');
            pkgs[pname] = pkg

    return pkgs


def get_repos(pkgs):
    repos={}
    for pname, pkg in pkgs.items():
        repo = pkg['repo']
        if repo not in repos:
            repos[repo]=[]
        repos[repo].append(pname)
    return repos

def generate_repo_dep_graph(pkgs):
    dot = pgv.AGraph(directed=True, strict=True, splines=True, compound=True, rankdir='TB', concentrate=True )

    sub_graphs = get_repos(pkgs)

    for k,sg in sub_graphs.items():
        dot.add_node(k)        
    
    
    for pname, pkg in pkgs.items():
        for d in pkg['depends']:
            dpkg = str(d)
            if dpkg in pkgs:
                #dot.node(dpkg)
                #nodes.append(dpkg)
                repo1=pkg['repo']
                repo2=pkgs[dpkg]['repo']
                if not repo1 == repo2:
                    dot.add_edge(repo1, repo2, weight=10, constraint=True)
                
    return dot


def generate_pkg_dep_graph(pkgs):
    dot = pgv.AGraph(directed=True, strict=True, splines=True, compound=True, rankdir='LR', concentrate=True, overlap='scale' )
    nodes=[]
    for pname, pkg in pkgs.items():
        if pname not in nodes:
            repo = pkg['repo']
            nodes.append(pname)
            dot.add_node(pname,group=repo)

    sub_graphs = get_repos(pkgs)

    for k,sg in sub_graphs.items():
        s=dot.add_subgraph(nbunch=sg, name='cluster_'+k, label=k,style='filled',fillcolor='lightgrey', concentrate=True)
    
    
    for pname, pkg in pkgs.items():
        for d in pkg['depends']:
            dpkg = str(d)
            if dpkg in nodes:
                #dot.node(dpkg)
                #nodes.append(dpkg)
                repo1=pkg['repo']
                repo2=pkgs[dpkg]['repo']
                if repo1 == repo2:
                    weight=0
                else:
                    weight=10
                dot.add_edge(pname, dpkg, weight=weight, constraint=True)
                #dot.add_edge(pname, dpkg, weight=weight, ltail='cluster_'+repo1, lhead='cluster_'+repo2)
                
    return dot
    

def main():
    parser = argparse.ArgumentParser(description='find all dependencies for packages within one path prefix',
                                     epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr')
    parser.add_argument('--prefix', help='filter only packages below path prefix default=\'/\'', default='/')
    args = parser.parse_args()


    pkgs = get_packages(args.prefix)
    dot = generate_pkg_dep_graph(pkgs)
    dot.layout(prog='dot')
    #print(dot.string()) 
    dot.write('out.gv')
    dot.draw('out.pdf')


if __name__ == "__main__":
    main()
