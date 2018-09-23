from .surface import Surface, SurfaceUserThread, SeekUsersThread
from .frame import Frame
from .user import User
from .utilities import hexstr2bytes, bytes2hexstr, str2hashed_hexstr
from .utilities import encrypt_rsa, encrypt_symmetric, decrypt_rsa
from .utilities import command_header, send_frame_users
from .message import Message

from termcolor import colored

import argparse
import os
import pprint
import uuid
import sys
import json
import random

def init_user(args):
    user = User(args.username)

    if user.exists:
        # TODO JHILL: ALSO CHECK SERVER
        print(colored("this user already exists: {}".format(args.username), "red"))
    else:
        user.initiate_directory_structure()
        user.initiate_rsa()
        print(colored("created user: {}".format(args.username), "green"))

    return True


def challenge_user_pk(args):
    user = User(args.username)
    result = user.challenge_user_pk(args.u2)

    if result:
        print(colored("good", "green"))
    else:
        print(colored("bad", "red"))


def challenge_user_has_pk(args):
    user = User(args.username)
    result = user.challenge_user_has_pk(args.u2)
    if result:
        print(colored("good", "green"))
    else:
        print(colored("bad", "red"))


def request_public_key(args):
    user = User(args.username)
    public_key_text = user.get_contact_public_key(args.u2)

    if public_key_text is None:
        frame = Frame(
            payload=dict(
                from_username=args.username,
                public_key=user.public_key_text
            ), 
            action="request_public_key"
        )

        response = send_frame_users(frame, user, args.u2)
        pprint.pprint(response, indent=4)


def surface_user(args):
    # TODO JHILL: verify the user exists, both here and on the server!
    surface = Surface(args.username, args.port)
    surface.start()

    # TODO JHILL: remove this, the stitcher can read the current_ip.json file
    # instead
    path = os.path.expanduser("~/pckr/surfaced.json")
    data = dict()
    try:
        data = json.loads(open(path).read())
    except:
        pass

    data[args.username] = dict(
        ip=surface.serversocket.getsockname()[0],
        port=surface.port
    )

    with open(path, "w+") as f:
        f.write(json.dumps(data))

    # TODO JHILL: don't remove this...
    user = User(args.username)
    path = os.path.join(user.path, "current_ip_port.json")
    with open(path, "w+") as f:
        f.write(json.dumps(dict(ip=surface.serversocket.getsockname()[0], port=surface.port)))

    print(colored("surfaced on {}:{}".format(surface.serversocket.getsockname()[0], surface.port), "green"))

    surface_user_thread = SurfaceUserThread(user)
    surface_user_thread.start()

    seek_users_thread = SeekUsersThread(user)
    seek_users_thread.start()

    seek_users_thread.join()
    surface_user_thread.join()
    surface.join()


def add_ipcache(args):
    user = User(args.username)
    user.set_contact_ip_port(args.u2, args.ip, args.port)
    print(user.ipcache)


def remove_ipcache(args):
    user = User(args.username)
    user.remove_contact_ip_port(args.u2)
    print(user.ipcache)


def seek_user(args):
    user = User(args.username)
    user.seek_user(args.u2)


def ping_user(args):
    user = User(args.username)
    frame = Frame(payload=dict(), action="ping")
    response = send_frame_users(frame, user, args.u2)
    pprint.pprint(response, indent=4)


def send_message(args):
    user = User(args.username)
    message = Message(
        user,
        args.filename,
        args.mime_type,
        args.u2
    )

    print(message)
    message.send()

def process_public_key_responses(args):
    user = User(args.username)
    for response in user.public_key_responses:
        if user.process_public_key_response(response):
            user.remove_public_key_response(response)


def process_public_key_requests(args):
    user = User(args.username)
    for request in user.public_key_requests:
        if user.process_public_key_request(request):
            user.remove_public_key_request(request)


def pulse_network(args):
    user = User(args.username)
    assert user.exists

    user.pulse_network()


def nt(args):
    user = User(args.username)
    user.nt()

def massage_args(argparser):
    args = argparser.parse_args()
    if args.username is None:
        username = os.getenv('PCKR_USERNAME', None)
        if username:
            print(colored("used ENV to get username: {}".format(username), "yellow"))
            sys.argv.extend(['--username', username])
        else:
            print(colored("no username found on command line or in ENV", "red"))
            sys.exit(1)

    # then reparse them to grab any --username that might have been added
    return argparser.parse_args()


COMMANDS = [
    'init_user',
    'surface_user',
    'seek_user',
    'ping_user',
    'send_message',
    'challenge_user_pk',
    'challenge_user_has_pk',
    'request_public_key',
    'process_public_key_requests',
    'process_public_key_responses',
    'add_ipcache',
    'remove_ipcache',
    'pulse_network',
    'nt'
]


COMMAND_ALIASES = dict(
    iu='init_user',
    surface='surface_user',
    seek='seek_user',
    pu='ping_user',
    sm='send_message',
    cupk='challenge_user_pk',
    cuhpk='challenge_user_has_pk',
    rpk='request_public_key',
    ppk_req='process_public_key_requests',
    ppk_resp='process_public_key_responses',
    aip='add_ipcache',
    rip='remove_ipcache',
    pn='pulse_network',
    nt='nt'
)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('command')
    args, _ = argparser.parse_known_args()
    
    command = args.command
    if command not in COMMANDS:
        alias_command = COMMAND_ALIASES.get(command, None)
        if alias_command is None:
            print(colored("unrecognized command: {}".format(command), "red"))
            sys.exit(1)
        else:
            command = alias_command

    # TODO JHILL: check for username?
    argparser.add_argument("--username", required=False, default=None)

    check_user_exists = True
    if command == 'init_user':
        check_user_exists = False

    elif command == 'seek_user':
        argparser.add_argument("--u2", required=True)

    elif command == 'surface_user':
        argparser.add_argument("--port", type=int, required=False, default=random.randint(8000, 9000))

    elif command == 'ping_user':
        argparser.add_argument("--u2", required=True)

    elif command == 'send_message':
        argparser.add_argument("--u2", required=True)
        argparser.add_argument("--filename", required=True)
        argparser.add_argument("--mime_type", required=False, default='image/png')

    elif command == 'challenge_user_pk':
        argparser.add_argument("--u2", required=True)

    elif command == 'challenge_user_has_pk':
        argparser.add_argument("--u2", required=True)

    elif command == 'request_public_key':
        argparser.add_argument("--u2", required=True)

    elif command == 'process_public_key_requests':
        pass

    elif command == 'process_public_key_responses':
        pass

    elif command == 'add_ipcache':
        argparser.add_argument("--u2", required=True)
        argparser.add_argument("--ip", required=True)
        argparser.add_argument("--port", required=True)

    elif command == 'remove_ipcache':
        argparser.add_argument("--u2", required=True)
    
    elif command == 'pulse_network':
        pass
    
    elif command == 'nt':
        pass

    else:
        assert False

    if command not in globals():
        error_exit("{} is unimplemented".format(command))

    args = massage_args(argparser)
    print(command_header(command, args))

    run_command = True
    if check_user_exists is True:
        user = User(args.username)
        if user.exists is False:
            print(colored("user {} does not exist".format(args.username), "red"))
            run_command = False

    if run_command:
        globals()[command](args)

    print("\n")
    print(colored("*" * 100, "blue"))
    print(colored("* end command", "blue"))
    print(colored("*" * 100, "blue"))
    print("\n")
