import argparse
from github_manager import *

def main():
    parser = argparse.ArgumentParser(description='generate new app token for later authentication',
                                     epilog='(c) Marc Hanheide 2014, see https://github.com/marc-hanheide/ros_gh_mgr')
    parser.add_argument('user', help='the github user name', default=None)
    parser.add_argument('--scopes', help='setting the scope of the auth token, default=[\'user\', \'repo\']', default=['user', 'repo'])
    parser.add_argument('--note', help='additional note to be displayed on github.com', default='github_manager_app')
    args = parser.parse_args()

    ghm = github_manager(user=args.user)
    auth = ghm.generate_app_token(note=args.note, scopes=args.scopes)
    print auth.token



if __name__ == "__main__":
    main()