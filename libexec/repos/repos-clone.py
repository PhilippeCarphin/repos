#!/usr/bin/env python3

import sys
import yaml
import argparse
import os
import subprocess
import pathlib

import _repos_logging
import logging

logger = _repos_logging.logger

class RepoError(Exception):
    pass

def get_args():
    p = argparse.ArgumentParser(description="Clone a git repo into repository tree and add it to repo file")

    p.add_argument("-F", help="Specify alternate file to ~/.config/repos.yml")
    p.add_argument("url", help="Repository URL to clone")
    p.add_argument("--dest", help="Destination")
    p.add_argument("--name", help="Specify name for repo in config file")
    p.add_argument("--debug", action='store_true')

    if "FROM_REPOS" in os.environ:
        logger.debug(f"Called by repos executable by doing 'repos clone'")

    args, others = p.parse_known_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    args.url = args.url

    return args, others

class DirectoryCreator:
    def __init__(self, path):
        logger.debug(f"Creating DirectoryCreator({path})")
        self.path = pathlib.Path(path) if path else None
        self.created = []
        self.preexisting = None
    def create_one(self, p):
        logger.debug(f"Creating directory '{p}'")
        p.mkdir()
        self.created.append(p)
    def create(self):
        for p in reversed(self.path.parents):
            if p.exists() and not p.is_dir():
                logger.debug("{p} exists and is not a directory!!")
                return False
            if p.exists() and p.is_dir():
                self.preexisting = p
                continue
            if not p.exists():
                self.create_one(p)
        if self.path.exists() and not self.path.is_dir():
            logger.debug("{p} exists and is not a directory!!")
            return False
        if not self.path.is_dir():
            self.create_one(self.path)

        if self.created:
            if self.preexisting:
                created = self.created[-1].relative_to(self.preexisting)
                logger.info(f"Created directory {created} in {self.preexisting}")
            else:
                logger.info(f"Created directory {self.created[-1]}")

    def undo(self):
        if self.created:
            if self.preexisting:
                created = self.created[-1].relative_to(self.preexisting)
                logger.info(f"Removing directory {created} from {self.preexisting}")
            else:
                logger.info(f"Removing directory {self.created[0]}")
            for p in reversed(self.created):
                logger.debug(f"Removing directory '{p}'")
                p.rmdir()

    def __enter__(self):
        if self.path:
            self.create()
    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.path and exc_value is not None:
            self.undo()

def main():
    args, clone_args = get_args()
    print(f"args={args}")
    print(f"clone_args={clone_args}")
    #
    # Load repofile
    #
    repo_file = args.F if args.F else os.path.expanduser("~/.config/repos.yml")
    with open(repo_file) as y:
        repo_dict = yaml.safe_load(y)


    if args.dest:
        repo_dest = args.dest
        dest_creator = DirectoryCreator(os.path.dirname(repo_dest))
        clone_command = ["git", "clone", args.url, repo_dest, *clone_args]
    else:
        if 'repo-dir' not in repo_dict['config']:
            clone_command = ["git", "clone", args.url, *clone_args]
            repo_dest = None # Can we figure out repo_dest, it depends on
                             # clone_args and the basename of the URL
                             # We would have to parse clone args and that would
                             # be too complicated
            dest_creator = DirectoryCreator(None)
        else:
            repo_dest = get_repo_dest(args, repo_dict)
            clone_command = ["git", "clone", args.url, repo_dest, *clone_args]
            try:
                dest_creator = DirectoryCreator(os.path.dirname(repo_dest))
            except OSError as e:
                logger.error(f"Could not create container directory: {e}")
                return 1

    with dest_creator:
        logger.debug(f"Clone command = {clone_command}")
        result = subprocess.run(clone_command)
        if result.returncode != 0:
            logger.error(f"repos-clone: failed to clone '{args.url}'")
            if dest_creator:
                dest_creator.undo()
            return 1
        if repo_dest:
            if args.name:
                result = subprocess.run(["repos", "add", repo_dest, "--name", args.name])
            else:
                result = subprocess.run(["repos", "add", repo_dest])
            if result.returncode != 0:
                logger.error(f"failed to adding repo")
                return 1

def get_repo_dest(args, repo_dict):

    repo_basename = os.path.basename(args.url)

    if 'config' not in repo_dict:
        logger.info(f"repos-clone is more useful when config file has a config section.  See section CONFIGURATION in 'man repos'")
        return os.path.join(os.environ['PWD'], repo_basename)

    config = repo_dict['config']
    if 'repo-dir' not in config:
        logger.info(f"no key 'repo-dir' in config section of config file")
        return os.path.join(os.environ['PWD'], repo_basename)

    if 'repo-dir-scheme' not in config:
        logger.info(f"key 'repo-dir-scheme' in config section of config file")
        return os.path.join(config['repo-dir'], repo_basename)

    scheme = config['repo-dir-scheme']
    if scheme == "url":
        return os.path.join(config['repo-dir'], url_to_directory(args.url))
    elif scheme == "flat":
        return os.path.join(config['repo-dir'], repo_basename)
    elif scheme == "null":
        return os.path.join(os.getcwd(), repo_basename)
    else:
        raise RuntimeError(f"repos-clone: Unrecognized value for repo-dir-scheme: '{scheme}'")

    return repo_dest


def url_to_directory(url):
    if url[0:4] == 'git@':
        return url[4:].replace(':', '/')
    elif url[:8] == 'https://':
        return url[8:]
    else:
        raise RepoError(f"URL '{url}' must begin with either 'git@' or 'https://'")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except RepoError as e:
        logger.error(e)
        sys.exit(1)
    except KeyboardInterrupt as e:
        sys.exit(130)
