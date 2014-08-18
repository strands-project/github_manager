from github3 import login
import yaml
import sys

import argparse


from github_manager import *

def main():
    parser = argparse.ArgumentParser(description='queries all repositories registered for a certain github organisation and return a rosinstall compatible format.',
                                     epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr')
    parser.add_argument('user', help='the github user name')
    parser.add_argument('organisation', help='the github organisation the repos should be queried for')
    args = parser.parse_args()

    print args.user

    ghm = github_manager('marc-hanheide')
    ri = ghm.query_orga_repos('strands-project')
    print yaml.dump(ri)





if __name__ == "__main__":
    main()