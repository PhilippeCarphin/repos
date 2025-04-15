#!/usr/bin/env python3
import os
import sys
import datetime
import subprocess
from pprint import pprint
import argparse

def arg_parser():
    p = argparse.ArgumentParser(description="Print today and yesterday's commits for a git repo")
    p.add_argument("--days", "-d", default=1, help="Number of days to go before yesterday")
    p.add_argument("--all", "-a", action='store_true', help="Check recent commits for all branches")
    return p

def main():
    args = arg_parser().parse_args()
    repo_dir = os.getcwd()
    repo = Repo(repo_dir)
    try:
        if args.all:
            repo.all_recent(days=int(args.days))
        else:
            repo.print_recent_commits(days=int(args.days))
    except subprocess.CalledProcessError as e:
        print(e.cmd, e.args, e.stderr.strip())
        return 1

class Repo:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir

    def branches(self):
        cmd = f"git branch --format='%(refname:short)'"
        result = subprocess.run(cmd,
                cwd=self.repo_dir,
                shell=True, universal_newlines=True, check=True, stdout=subprocess.PIPE)
        for l in result.stdout.splitlines():
            if 'HEAD' in l:
                continue
            if '(' in l:
                continue
            yield l

    def commits_between_dates(self, begin, end, branch="HEAD"):
        """ Yield recent commits reacheable from a certain branch made up to 'days'
        days in the past.

        YIELDS: Dictionnaries of the form

            {
                'commit': <HASH>,
                'date': <DATETIME OBJECT>,
                'message': <MESSAGE>
            }

        use commit_list = list(gen_recent_commits(...)) to get a printable list.

        Implementation details:

        We use 'git log {branch} --after={date} --pretty=format:{format} where date is
        today's date minus the prescribed number of days and {format} makes the
        output easy to parse.

        """
        # This format '%h %at %ae %an\n%s' allows me to parse the output in pairs
        # of lines to deal with fields that can contain spaces by putting them
        # at the end of the line or on its own line.
        #
        # This relies getting exactly two lines per commit which is dependant
        # on the fields not having any newline characters inside them.  The
        # only one where that could potentially happen is the author name since
        # '%s' is by definition a single line.
        #
        # Even if I configure an author name that contains newlines, the output
        # of git log does not print these newlines therefore we can safely rely
        # on this method to produce exactly two lines per commit.
        start_date = begin.strftime("%Y-%m-%d %H:%M")
        end_date = end.strftime("%Y-%m-%d %H:%M")
        cmd = f'git log --after="{start_date}" --before="{end_date}" --pretty=format:"%h %at %ae %an\n%s" {branch}'
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=self.repo_dir,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        lines = result.stdout.splitlines()
        if len(lines) % 2 != 0:
            raise RuntimeError("Expecting an even number of lines from command {cmd}.  It should produce exactly two lines per commit")
        for info, message in zip(lines[::2], lines[1::2]):
            words = info.split()
            yield {
                "date": datetime.datetime.fromtimestamp(int(words[1])),
                "hash": words[0],
                "email": words[2],
                "author": ' '.join(words[3:]),
                "message": message
            }

    def print_recent_commits(self, days=1):
        self.print_branch_recent('HEAD', days=days)

    def all_recent(self, days=2):
        for b in self.branches():
            self.print_branch_recent(b, days=days)

    def print_branch_recent(self, branch='HEAD', days=1):
        now = datetime.date.today()
        right_now = datetime.datetime.now()
        yesterday = now - datetime.timedelta(days=1)
        before_yesterday = now - datetime.timedelta(days=1+days)

        today_commits = list(self.commits_between_dates(now, right_now, branch))
        yesterday_commits = list(self.commits_between_dates(before_yesterday, now, branch))

        if today_commits:
            print(self.today_header(branch, days))
            print_list(sorted(today_commits, key=lambda c: c["date"], reverse=True))

        if yesterday_commits:
            print(self.past_header(branch, days))
            print_list(sorted(yesterday_commits, key=lambda c: c["date"], reverse=True))

    def today_header(self, branch, days):
        return f"\033[1;37mToday's commits\033[0m" \
               if branch == 'HEAD' \
               else f"\033[1;37mCommits made today on branch \033[1;35m{branch}\033[1;37m\033[0m"

    def past_header(self, branch, days):
        if branch == 'HEAD':
            if days == 1:
                return f'\033[1;37mCommits made yesterday\033[0m'
            else:
                return f'\033[1;37mCommits made between yesterday and {days} days ago\033[0m'
        else:
            if days == 1:
                return f'\033[1;37mCommits made yesterday on branch \033[1;35m{branch}\033[1;37m\033[0m'
            else:
                return f'\033[1;37mCommits made between yesterday and {days} days ago on branch \033[1;35m{branch}\033[1;37m\033[0m'

def print_list(commit_list):
    for c in commit_list:
        print_commit(c)

def print_commit(c):
    # print("\033[33m{}\033[0m {} - \033[32m{}\033[0m".format(c['hash'][:6], c['date'], c['message']))
    print("\033[33m{}\033[0m {} - \033[34m{}\033[0m - \033[32m{}\033[0m".format(c['hash'][:6],c['date'],c['author'], c['message']))

if __name__ == "__main__":
    sys.exit(main())



