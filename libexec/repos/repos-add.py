#!/usr/bin/env python3

import sys
import yaml
import argparse
import os
import _repos_logging

logger = _repos_logging.logger

def arg_parser():
    p = argparse.ArgumentParser(description="Add a repo to the repos.yml config file")

    p.add_argument("-F", help="Specify alternate file to ~/.config/repos.yml")
    p.add_argument("repo", help="Specify the repository, defaults to $PWD", nargs='?')
    p.add_argument("--name", help="Specify name for repo in config file")
    return p
def get_args():
    p = arg_parser()

    if "FROM_REPOS" in os.environ:
        logger.debug(f"Called by repos executable by doing 'repos add'")

    args = p.parse_args()

    if not args.repo:
        args.repo = os.environ['PWD']

    if not os.path.isabs(args.repo):
        args.repo = os.path.normpath(os.path.join(os.environ['PWD'], args.repo))

    if not args.name:
        args.name = os.path.basename(args.repo)

    return args

def main(args):

    repo_file = args.F if args.F else os.path.expanduser("~/.config/repos.yml")

    #
    # Create config file if it doesn't exist
    #
    if not os.path.isfile(repo_file):
        os.makedirs(os.path.expanduser("~/.config"), exist_ok=True)
        with open(repo_file, 'w') as f:
            f.write('repos: {}\n')

    #
    # Load repofile
    #
    with open(repo_file) as y:
        repo_dict = yaml.safe_load(y)

    #
    # Check that it is a git repo by checking for a .git directory
    #
    if not (os.path.isdir(os.path.join(args.repo, '.git')) or os.path.isfile(os.path.join(args.repo, '.git'))):
        logger.error(f"It seems repo '{args.repo}' is not a git repository, skipping ...")
        return 1

    #
    # Check if the repo is already there
    #
    if args.name in repo_dict['repos']:
        logger.warn(f"Repo '{args.repo}' is already in '{repo_file}' under name '{args.name}' skipping ...")
        return 0

    #
    # Add to the repo database
    #
    repo_dict['repos'][args.name] = {"path": args.repo}
    logger.info(f"Added '{args.repo}' to '{repo_file}' under name '{args.name}'")


    #
    # Save back to file
    #
    with open(repo_file, 'w') as y:
        yaml.dump(repo_dict,y)

if __name__ == "__main__":
    sys.exit(main(get_args()))
