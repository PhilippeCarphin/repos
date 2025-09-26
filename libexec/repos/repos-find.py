#!/usr/bin/env python3
import os
import yaml
import argparse
import pprint
import sys
import re
import _repos_logging
import logging

logger = _repos_logging.logger

def arg_parser():
    p = argparse.ArgumentParser(description="Find git repos recursively and produce YAML code for ~/.config/repos.yml on STDOUT.  Use the --merge option to merge the results into the config file")
    p.add_argument("dirs", nargs='*', default=[os.getcwd()], help="Directories to search.  Searches PWD if none are specified")
    p.add_argument("--recursive", action='store_true', help="Search recursively")
    p.add_argument("--debug", action="store_true", help="Print current search dir to STDERR")
    p.add_argument("--merge", action='store_true', help="Merge with repo file")
    p.add_argument("-F", dest='repo_file', metavar="CONFIG_FILE", help="Alternate repo-file, defaults to ~/.config/repos.yml", default=os.path.expanduser("~/.config/repos.yml"))
    p.add_argument("--exclude", help="Regular expression to exclude")
    p.add_argument("--include", help="Regular expression to include")
    p.add_argument("--cleanup", action='store_true', help="Remove repos that don't exist anymore.  Only valid when using the --merge option")

    return p

def get_args():
    args = arg_parser().parse_args()

    if args.exclude:
        if '/' in args.exclude:
            logger.warning("--exclude pattern contains a '/' but pattern is used to match on path components")
        args.exclude = re.compile(args.exclude)
    if args.include:
        if '/' in args.include:
            logger.warning("--include pattern contains a '/' but pattern is used to match on path components")
        args.include = re.compile(args.include)

    for d in args.dirs:
        if not os.path.isdir(d):
            logger.warning(f"directory '{d}' does not exist or is not a directory")

    if args.debug:
        logger.setLevel(logging.DEBUG)

    return args

def is_git_repo(path):
    try:
        if not os.path.isdir(path):
            return False
        contents = os.listdir(path)

        if '.git' in contents:
            return True

        if 'branches' in contents and 'refs' in contents and 'objects' in contents and 'packed-refs' in contents:
            return True

    except PermissionError:
        return False

    return False

def find_git_repos_in(directory, recurse, args):
    logger.debug(f"Doing directory {directory}")
    try:
        contents = os.listdir(directory)
    except PermissionError:
        return
    except NotADirectoryError:
        return
    except FileNotFoundError as e:
        logger.warn(f"FileNotFoundError: {e}")
        return

    dirs = filter(lambda c: not c.startswith("."), contents)
    dirs = set(filter(lambda d:os.path.isdir(os.path.join(directory, d)), dirs))
    if args.include and args.exclude:
        dirs = filter(lambda d: (not args.exclude.search(d)) or (args.include.search(d)), dirs)
    elif args.include:
        dirs = filter(lambda d: args.include.search(d), dirs)
    elif args.exclude:
        dirs = filter(lambda d: not args.exclude.search(d), dirs)
    for d in dirs:
        abs_dir=os.path.join(directory,d)
        if is_git_repo(abs_dir):
            name = os.path.basename(d)
            logger.debug(f"Yielding ({name}, {{'path': '{abs_dir}'}})")
            yield (name, {'path': os.path.normpath(abs_dir)})
        elif recurse:
            logger.debug(f"Recursing into directory {d}")
            yield from find_git_repos_in(os.path.join(directory, d), recurse, args)

def soft_update(original, new):
    """ Update original with keys that are in new but not already in original """

def main():
    args = get_args()
    # TODO: Should be just a list of paths
    repos = []
    try:
        for d in args.dirs:
            if not os.path.isabs(d):
                d = os.path.join(os.getcwd(), d)
            if is_git_repo(d):
                # find_git_repos_in checks if the the directory *contains* git repos
                # but not if the directory itself is a git repo.  This could be
                # made more elegant.
                repos.append((os.path.basename(d), {"path": d}))
            else:
                repos += find_git_repos_in(d, args.recursive, args)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt, results so far:")
        yaml.dump({'repos': repos})
        return 130
    if args.merge:
        clashes = []
        if not os.path.exists(args.repo_file):
            open(args.repo_file, 'w').write('repos: {}\n')
        with open(args.repo_file, 'r') as f:
            base_rf = yaml.safe_load(f)
            for k,r in repos:
                if k not in base_rf['repos']:
                    logger.info(f"Adding repo '{k}' at path '{r['path']}'")
                    base_rf['repos'][k] = r
                else:
                    original_repo = base_rf['repos'][k]
                    if os.path.realpath(original_repo['path']) != os.path.realpath(r['path']):
                        if os.path.isdir(original_repo['path']):
                            logger.warning(f"Repo under name '{k}' exists at path '{original_repo['path']}, not adding repo '{r['path']}'")
                            clashes.append((k,r))
                        else:
                            logger.info(f"Repo under name '{k}' at path '{r['path']}' doesn't exist, replacing with '{r['path']}'")
                            base_rf['repos'][k] = r
        if args.cleanup:
            for k in list(base_rf['repos'].keys()):
                v = base_rf['repos'][k]
                if not os.path.isdir(v['path']):
                    logger.info(f"Deleting key {k}: path {v['path']} does not exist")
                    del base_rf['repos'][k]
        with open(args.repo_file, 'w') as f:
            yaml.dump(base_rf, f)
    else:
        if repos:
            print("repos:")
            for k, v in repos:
                print(f"  {k}: {{path: {v['path']}}}")

if __name__ == "__main__":
    sys.exit(main())
