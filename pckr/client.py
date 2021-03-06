"""

this file contains all scaffolding code for the pckr client.

everything required to parse command line arguments and run commands is contained here.

"""

import argparse
import os
import pprint
import sys
import json
import random

from termcolor import colored

from .surface import Surface, SurfaceUserThread, SeekUsersThread
from .frame import Frame
from .user import User
from .utilities import command_header, send_frame_users
from .utilities.logging import surface_logger
from .message import Message


def init_user(args: argparse.Namespace) -> bool:
    """
    initialize a user with args.username as their username.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)

    if user.exists:
        print(colored("this user already exists: {}".format(args.username), "red"))
    else:
        user.init_directory_structure()
        user.init_rsa()
        print(colored("created user: {}".format(args.username), "green"))

    return True


def challenge_user_pk(args: argparse.Namespace) -> bool:
    """
    challenge a user's public key... ie: send them a challenge asking them if they can decrypt a challenge.

    the challenge is what we encrypted with what we believe is their public key

    the challenged user is specified by args.user2

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    result = user.challenge_user_pk(args.user2)

    if result:
        print(colored("good", "green"))
    else:
        print(colored("bad", "red"))

    return True


def challenge_user_has_pk(args: argparse.Namespace) -> bool:
    """
    challenge a user to ask if they have our public key. they can try to encrypt some text.

    with what they believe is our public key. if we can decrypt it we know they have our
    public key

    the challenged user is specified by args.user2

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    result = user.challenge_user_has_pk(args.user2)
    if result:
        print(colored("good", "green"))
    else:
        print(colored("bad", "red"))

    return True


def request_public_key(args: argparse.Namespace) -> bool:
    """
    request another user's public key.

    the requested user is specified by args.user2

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    public_key_text = user.get_contact_public_key(args.user2)

    # check to see if we don't already have it... if we do we can skip
    # asking them safely
    if public_key_text is None:
        frame = Frame(
            action="request_public_key",
            payload=dict(
                user2=args.username,
                public_key=user.public_key_text
            )
        )

        response = send_frame_users(frame, user, args.user2)
        pprint.pprint(response, indent=4)

        # after that, they have a public_key_request.... they will answer
        # it when they want, and we'll get a public_key_response
    return True


def surface_user(args: argparse.Namespace) -> bool:
    """
    expose the user surface (ie: args.username has joined the network).

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    surface = Surface(args.username, args.port)
    surface.start()

    user = User(args.username)
    path = os.path.join(user.path, "current_ip_port.json")
    with open(path, "w+") as f:
        f.write(json.dumps(dict(
            ip=surface.serversocket.getsockname()[0],
            port=surface.port)
        ))

    print(colored("surfaced on {}:{}".format(surface.serversocket.getsockname()[0], surface.port), "green"))
    surface_logger.info("{} surfaced on {}:{}".format(
        args.username,
        surface.serversocket.getsockname()[0],
        surface.port)
    )

    surface_user_thread = SurfaceUserThread(user)
    surface_user_thread.start()

    seek_users_thread = SeekUsersThread(user)
    seek_users_thread.start()

    seek_users_thread.join()
    surface_user_thread.join()
    surface.join()

    return True


def add_ipcache(args: argparse.Namespace)-> bool:
    """
    add args.user2 to your ipcache at args.ip and args.port.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    user.set_contact_ip_port(args.user2, args.ip, args.port)
    print(user.ipcache)

    return True


def remove_ipcache(args: argparse.Namespace)-> bool:
    """
    remove args.user2 from your ipcache.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    user.remove_contact_ip_port(args.user2)
    print(user.ipcache)

    return True


def seek_user(args: argparse.Namespace)-> bool:
    """
    seek args.user2 by sending out seek_user frames to your network.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    user.seek_user(args.user2)

    return True


def ping_user(args: argparse.Namespace) -> bool:
    """
    ping args.user2.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    user.ping_user(args.user2)

    return True


def send_message(args: argparse.Namespace) -> bool:
    """
    send a message from username to user2.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    return Message(
        User(args.username),
        args.filename,
        args.mime_type,
        args.user2
    ).send()


def process_public_key_responses(args: argparse.Namespace) -> bool:
    """
    interactively process the public key responses.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    for response in user.public_key_responses:
        if user.process_public_key_response(response):
            user.remove_public_key_response(response)

    return True


def process_public_key_requests(args: argparse.Namespace) -> bool:
    """
    interactively process the public key requests.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """
    user = User(args.username)
    for request in user.public_key_requests:
        if user.process_public_key_request(request):
            user.remove_public_key_request(request)

    return True


def pulse_network(args: argparse.Namespace) -> bool:
    """
    pulse the network (send out a tracer frame).

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    assert user.exists

    user.pulse_network()

    return True


def check_net_topo(args: argparse.Namespace) -> bool:
    """
    check the topology of the user's network.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    user.check_net_topo()

    return True


def public_keys(args: argparse.Namespace) -> bool:
    """
    print out the user public keys.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    for pk in user.public_keys:
        print("{} at {}".format(pk['username'], pk['modified_at'].isoformat()))

    return True


def ipcache(args: argparse.Namespace) -> bool:
    """
    print out the user ip cache.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    for username, ip in user.ipcache.items():
        print("{} at {}:{}".format(username, ip['ip'], ip['port']))

    return True


def messages(args: argparse.Namespace) -> bool:
    """
    print out the user messages.

    Parameters
    ----------
    args : argparse.Namespace
        the arguments

    Returns
    -------
    bool
        usually True
    """

    user = User(args.username)
    for message in user.messages:
        print(message)

    return True


def massage_args(argparser: argparse.ArgumentParser) -> argparse.Namespace:
    """
    allow the username to be specified by the os env PCKR_USERNAME.

    Parameters
    ----------
    argparser: ArgumentParser
        the ArgumentParser that the username must be added to

    Returns
    -------
    argparse.Namespace
        the massaged arguments
    """

    args = argparser.parse_args()
    if args.username is None:
        username = os.getenv('PCKR_USERNAME', None)
        if username:
            # TODO JHILL: error_exit
            print(colored("used ENV to get username: {}".format(username), "yellow"))
            sys.argv.extend(['--username', username])
        else:
            # TODO JHILL: error_exit
            print(colored("no username found on command line or in ENV", "red"))
            sys.exit(1)

    # then reparse them to grab any --username that might have been added
    return argparser.parse_args()


# these are the accepted commands, anything else won't run
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
    'check_net_topo',
    'public_keys',
    'ipcache',
    'messages',
    'current_ip'
]

# these are the short codes for the above accepted commands. the user
# can specify one of these instead of the longer form above.
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
    cnt='check_net_topo',
    pks='public_keys',
    ipc='ipcache',
    ms='messages',
    cip='cip'
)


def main() -> None:
    """
    the main handler function for the pckr client.

    TODO JHILL: much better documentation
    """

    # first we try to tweeze out what command they want.
    argparser = argparse.ArgumentParser()
    argparser.add_argument('command')
    args, _ = argparser.parse_known_args()

    # the command could have a short name. if so find the long name of the command.
    command = args.command
    if command not in COMMANDS:
        alias_command = COMMAND_ALIASES.get(command, None)
        if alias_command is None:
            # TODO JHILL: error_exit
            print(colored("unrecognized command: {}".format(command), "red"))
            sys.exit(1)
        else:
            command = alias_command

    # TODO JHILL: check for username?
    argparser.add_argument("--username", required=False, default=None)

    # before running most of these commands we need to check if the specified user exists.
    # we keep this boolean around to determine if we want to check that based on the command type.
    check_user_exists = True

    # each command has special arguments that we need to add to the argparser. parse the command name
    # and mark up the arguments as required
    if command == 'init_user':
        check_user_exists = False

    elif command == 'seek_user':
        argparser.add_argument("--user2", required=True)

    elif command == 'surface_user':
        argparser.add_argument("--port", type=int, required=False, default=random.randint(8000, 9000))

    elif command == 'ping_user':
        argparser.add_argument("--user2", required=True)

    elif command == 'send_message':
        argparser.add_argument("--user2", required=True)
        argparser.add_argument("--filename", required=True)
        argparser.add_argument("--mime_type", required=False, default='image/png')

    elif command == 'challenge_user_pk':
        argparser.add_argument("--user2", required=True)

    elif command == 'challenge_user_has_pk':
        argparser.add_argument("--user2", required=True)

    elif command == 'request_public_key':
        argparser.add_argument("--user2", required=True)

    elif command == 'process_public_key_requests':
        pass

    elif command == 'process_public_key_responses':
        pass

    elif command == 'add_ipcache':
        argparser.add_argument("--user2", required=True)
        argparser.add_argument("--ip", required=True)
        argparser.add_argument("--port", required=True)

    elif command == 'remove_ipcache':
        argparser.add_argument("--user2", required=True)

    elif command == 'pulse_network':
        pass

    elif command == 'check_net_topo':
        pass

    elif command == 'public_keys':
        pass

    elif command == 'ipcache':
        pass

    elif command == 'messages':
        pass

    else:
        assert False

    # enforce existence of the command.
    if command not in globals():
        # TODO JHILL: write this function
        # error_exit("{} is unimplemented".format(command))
        sys.exit(1)

    # it might be that their username is defined in an environment variable.
    # this function will add it to the arguments if so.
    # this function will also re-enforce the command-specific arguments added above.
    args = massage_args(argparser)
    print(command_header(command, args))

    # we are now done processing the arguments

    run_command = True

    # finally check if the user exists here
    if check_user_exists is True:
        user = User(args.username)
        if user.exists is False:
            print(colored("user {} does not exist".format(args.username), "red"))
            run_command = False

    # we can now run the command by name, looking for it in the dictionary of functions
    # that are loaded as globals.
    if run_command:
        globals()[command](args)

    # TODO JHILL: put in the utilities file, command_header
    print("\n")
    print(colored("*" * 100, "blue"))
    print(colored("* end command", "blue"))
    print(colored("*" * 100, "blue"))
    print("\n")

    sys.exit(0)
