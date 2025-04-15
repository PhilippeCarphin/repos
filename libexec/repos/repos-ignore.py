#!/usr/bin/env python3
import yaml
import os
import sys
import argparse
import logging

import _repos_logging
import _repos_base

logger = _repos_logging.logger

def arg_parser():
    p = argparse.ArgumentParser(description="Set the ignore flag of a repo to true")
    p.add_argument("-F", help="Specify alternate file to ~/.config/repos.yml")
    p.add_argument("--name", help="Specify name for repo in config file.  Defaults to basename(os.getcwd())")
    p.add_argument("--unignore", help="Unignore the repo", action='store_true')
    p.add_argument("--debug", action='store_true')
    return p

def get_args():
    args = arg_parser().parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    return args

def main():
    args = get_args()
    repo_file = args.F if args.F else os.path.expanduser("~/.config/repos.yml")

    if args.name is None:
        repo_root = _repos_base.get_repo_root(os.getcwd())
        if repo_root is None:
            logger.error(f"No --name provided and could not find repo root starting at PWD")
            return 1
        logger.info(f"Using basename(REPO_ROOT): '{repo_root.name}' as repo name to commment")
        args.name = os.path.basename(repo_root.name)

    with open(repo_file) as f:
        database = yaml.safe_load(f)

    if args.name not in database['repos'] :
        logger.error(f"No repo with name '{args.name}' in repo file '{repo_file}'")
        return 1

    repo = database['repos'][args.name]
    if args.unignore:
        if 'ignore' in repo:
            del repo['ignore']
    else:
        if 'ignore' in repo and repo['ignore']:
            logger.warning(f"Repo is already ignored")
        else:
            logger.info(f"Adding 'ignore: true' to repo '{args.name}'")
            repo['ignore'] = True


    with open(repo_file, 'w') as f:
        yaml.dump(database, f)

if __name__ == "__main__":
    sys.exit(main())


