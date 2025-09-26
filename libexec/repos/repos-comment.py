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
    p.add_argument("--debug", action='store_true')
    action = p.add_mutually_exclusive_group()
    action.add_argument("--get", help="Get comment for repo", action='store_true')
    action.add_argument("--set", help="Set comment for repo", metavar='COMMENT')
    action.add_argument("--clear", help="Remove comment from repo", action='store_true')
    return p

def main():
    args = arg_parser().parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
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

    repos = database['repos']
    try:
        repo = repos[args.name]
    except KeyError as e:
        logger.error(f"Repo '${args.name}' not found in repos section of repo_file '{repo_file}'")
        return 1

    if args.set or args.clear:
        if args.set == "":
            logger.error(f"Use --del to remove comments", file=sys.stderr)
            return 1
        if args.set:
            if 'comment' in repo:
                logger.error(f"Replacing previous comment '{repo['comment']}'")
            logger.info(f"Setting comment to '{args.set}'")
            repo['comment'] = args.set
        elif args.clear:
            if 'comment'in repo:
                logger.info(f"Removing comment '{repo['comment']}'")
                del repo['comment']
        with open(repo_file, 'w') as f:
            yaml.dump(database, f)
    elif args.get:
        if 'comment' in repo:
            print(repo['comment'])
        else:
            logger.error("The repo '{args.name}' has no comment", file=sys.stderr)
            return 1

if __name__ == "__main__":
    sys.exit(main())


