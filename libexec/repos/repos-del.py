#!/usr/bin/env python3
import sys
import yaml
import argparse
import os
import subprocess
import shutil
import logging
import pathlib

import _repos_logging

logger = _repos_logging.logger

DESCRIPTION = """
Delete a repo from disc and from the repos config file.  NOTE: Although this
tool performs some checks to prevent work from being lost, only use it if you
would be willing to rm -rf the repo."""

def get_args():
    p = argparse.ArgumentParser(description=DESCRIPTION)
    p.add_argument("-F", help="Specify alternate file to ~/.config/repos.yml")
    p.add_argument("--path", help="Specify the repository, defaults to $PWD", nargs='?')
    p.add_argument("--name", help="Specify name for repo in config file")
    p.add_argument("--debug", action='store_true')

    args = p.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    return args

def find_repo_by_path(repos, path):
    for name, repo in repos.items():
        if repo['path'] == path:
            return name, repo
    return None, None

def main():
    args = get_args()
    repo_file = args.F if args.F else os.path.expanduser("~/.config/repos.yml")
    with open(repo_file) as y:
        d = yaml.safe_load(y)

    repos = d['repos']
    if not args.name:
        if not args.path:
            name, repo = find_repo_by_path(repos, os.environ['PWD']) or find_repo_by_path(repos, os.getcwd())
        else:
            name, repo = find_repo_by_path(args.path) or find_repo_by_path(os.path.realpath(args.path))
        args.name = name
    else:
        repo = repos.get(args.name)

    if repo is None:
        logger.error(f"No such repo '{args.name}'")
        return 1

    logger.info(f"Repo '{args.name}' at path '{repo['path']}'")

    try:
        if not can_erase(repo):
            logger.info("Refusing to delete.  If you are sure, you can 'rm -rf' it yourself then remove the entry in the config file with `repos del --name NAME`")
            return 1
        resp = input("Are you sure you want to delete this repo? [yes|no] > ")
        if resp.lower() != 'yes':
            return 0
        shutil.rmtree(repo['path'])
        logger.info(f"Repo '{repo['path']}' deleted")
        # TODO: If repo-dir-scheme is URL and repo path is inside repo-dir,
        #       remove all empty directories up-to but excluding repo-dir.
        if 'repo-dir' in d['config'] and d['config'].get('repo-dir-scheme', None) == 'url':
            path = pathlib.Path(repo['path']).resolve()
            repo_dir = pathlib.Path(d['config']['repo-dir']).resolve()
            if path.is_relative_to(repo_dir):
                rel = path.relative_to(repo_dir)
                for p in rel.parents:
                    try:
                        p.rmdir()
                        logger.info(f"Removing empty directory '{repo_dir.joinpath(p)}'")
                    except OSError as e:
                        break

    except FileNotFoundError as e:
        logger.info(f"Repo not found: {e}")

    del d['repos'][args.name]

    with open(repo_file, 'w') as y:
        yaml.dump(d,y)

    logger.info(f"Repo removed from repo_file '{repo_file}'")

def can_erase(repo):
    result = True

    status = subprocess.run('git status',
        shell=True,
        cwd=repo['path'],
        check=True,
        stdout=subprocess.PIPE,
        universal_newlines=True
    ).stdout

    if 'Untracked files' in status:
        logger.error(f"There are untracked files, please cleanup first")
        result = False

    if 'Your branch is behind' in status:
        logger.error(f"Current branch is behind its remote counterpart, push first")
        result = False

    if 'Changes not staged' in status:
        logger.error(f"There are unstaged changes, make a commit first")
        result = False

    if 'Changes to be committed' in status:
        logger.error(f"There are staged changes, make a commit first")
        result = False

    return result

sys.exit(main())



