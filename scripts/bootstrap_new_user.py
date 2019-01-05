import subprocess
from argparse import ArgumentParser
from utils import aip, rpk, gather_user_ip_ports


def main():
    argparser = ArgumentParser()
    argparser.add_argument("--username", required=True)
    args = argparser.parse_args()

    subprocess.check_call([
        'pckr',
        'init_user',
        '--username={}'.format(args.username)
    ])

    users = gather_user_ip_ports()

    for i in users.keys():
        aip(users, args.username, i)

    for i in users.keys():
        rpk(args.username, i)


if __name__ == '__main__':
    main()
