import sys
import yaml
import os

with open(os.path.expanduser("~/.config/repos.yml")) as y:
    domains = yaml.safe_load(y)['config']['domains']

def complete_domains(protocol, domain_prefix):
    for d in domains:
        if d.startswith(domain_prefix):
            if protocol == "https://":
                print(f"//{d}{domain_user_sep}")
            else:
                print(f"{protocol}{d}:")

def complete_users(protocol, domain, user_prefix):
    for u in domains[domain]:
        if u.startswith(user_prefix):
            if protocol == "https://":
                print(f"//{domain}/{u}/")
            else:
                print(f"{u}/")


if __name__ == "__main__":
    to_complete=sys.argv[1]
    if to_complete.startswith("git@"):
        protocol = "git@"
        domain_user_sep = ':'
    elif to_complete.startswith("https://"):
        protocol = "https://"
        domain_user_sep = '/'
    else:
        if "git@".startswith(to_complete):
            print("git@")
        if "https://".startswith(to_complete):
            print("https://")
        sys.exit(0)

    rest = to_complete[len(protocol):]
    if domain_user_sep in rest:
        domain, rest = rest.split(domain_user_sep, 1)
        if '/' not in rest:
            complete_users(protocol, domain, rest)
    else:
        complete_domains(protocol, rest)
