from ..user import User
from ..utilities import hexstr2bytes, encrypt_symmetric, decrypt_symmetric, bytes2hexstr, send_frame
from ..frame import Frame
from ..ipcache import IPCache

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from termcolor import colored

import binascii
import json
import os
import socket
import threading
import uuid


class SocketThread(threading.Thread):
    clientsocket = None
    user = None

    def __init__(self, clientsocket, username):
        super(SocketThread, self).__init__()
        self.clientsocket = clientsocket
        self.user = User(username)

        # TODO JHILL: assert the user exists?

    def _receive_ping(self, request):
        return dict(
            success=True,
            message="pong"
        )

    def _receive_seek_user(self, request):
        responded = False

        if request['payload']['skip_count'] > 5:
            return dict(
                success=True,
                message_id=request['message_id']
            )

        # 1) try to decrypt the message using our own private key
        # if we can decrypt it we should answer the other host
        try:
            password_decrypted = self.user.private_rsakey.decrypt(hexstr2bytes(request['payload']['password']))

            # now we have to open up the message and challenge that user
            decrypted_text = decrypt_symmetric(hexstr2bytes(request['payload']['host_info']), password_decrypted)
            host_info = json.loads(decrypted_text)

            password = str(uuid.uuid4())
            rsa_key = RSA.importKey(host_info['public_key'])
            rsa_key = PKCS1_OAEP.new(rsa_key)

            password_encrypted = rsa_key.encrypt(password.encode())
            password_encrypted = bytes2hexstr(password_encrypted)

            path = os.path.join(self.user.path, "current_ip_port.json")
            data = json.loads(open(path).read())

            our_ip_port = dict(
                ip=data['ip'],
                port=data['port']
            )

            host_info_encrypted = bytes2hexstr(encrypt_symmetric(
                json.dumps(our_ip_port).encode(),
                password.encode()
            ))

            seek_token_encrypted = bytes2hexstr(encrypt_symmetric(
                host_info['seek_token'],
                password.encode()
            ))

            # TODO JHILL: before we do this, challenge the user...
            response_dict = dict(
                seek_token=seek_token_encrypted,
                password=password_encrypted,
                host_info=host_info_encrypted
            )

            # now send back a response
            frame = Frame(
                action='seek_user_response',
                content=response_dict
            )
            response = send_frame(frame, host_info['ip'], int(host_info['port']))
            
            # TODO JHILL: we can also put that host_info into our own ipcache...
            responded = True

        except ValueError as e:
            pass

        if responded == False:
            # 2) if we can't decrypt and respond we should pass the message along
            ipcache = IPCache(self.user)
            request['payload']['skip_count'] = request['payload']['skip_count'] + 1
            for k, v in ipcache.data.items():
                frame = Frame(
                    action=request['action'],
                    message_id=request['message_id'],
                    content=request['payload']
                )

                response = send_frame(frame, v['ip'], int(v['port']))
                print(response)


        return dict(success=True)

    def _receive_request_public_key(self, request):
        self.user.store_public_key_request(request)

        # TODO JHILL: make this nicer
        return dict(
            success=True,
            message_id=request['message_id']
        )


    def _receive_public_key_response(self, request):
        self.user.store_public_key_response(request) 
        return dict(success=True, message_id=request['message_id'])


    def _receive_challenge_user(self, request):
        # TODO JHILL: move this somewhere
        # TODO JHILL: obviously this could fail if we don't know their public_key
        # TODO JHILL: also be more careful about charging into dictionaries
        public_key = self.user.get_contact_public_key(request["payload"]["from_username"])

        # TODO JHILL: check if the file exists, don't just charge through it
        rsa_key = RSA.importKey(public_key)
        rsa_key = PKCS1_OAEP.new(rsa_key)

        challenge_rsaed = rsa_key.encrypt(request["payload"]["challenge_text"].encode())
        challenge_rsaed = bytes2hexstr(challenge_rsaed)

        return dict(
            success=True,
            encrypted_challenge=challenge_rsaed
        )


    def _receive_send_message(self, request):
        # TODO JHILL: definitely put this all away behind a message object
        print(request)

        # TODO JHILL: get the key from the user object?
        # TODO JHILL: a function to just get a message key?
        if request['payload']['mime_type'] == 'image/png':
            filename = "out.png"
        else:
            filename = "out.txt"

        # TODO JHILL: make this better.... maybe have a transfer facade?
        path = os.path.join(self.user.messages_path, request['message_id'])
        if not os.path.exists(path):
            os.makedirs(path)
        path = os.path.join(path, filename)

        # TODO JHILL: obviously split the handling on binary or not, mime_types!
        # and yeah this would be as good a time as any to introduce a transfer object
        if payload['mime_type'] == 'image/png':
            with open(path, "ab+") as f:
                f.write(hexstr2bytes(request['payload']['content']))
        else:
            with open(path, "a+") as f:
                f.write(payload['content'])

        return dict(
            success=True,
            filename=path
        )

    def _receive_send_message_key(self, request):
        # TODO JHILL: hide this all in the user object or a message object?
        payload = hexstr2bytes(request['payload'])
        payload_data = json.loads(self.user.private_rsakey.decrypt(payload))

        key_path = os.path.join(self.user.message_keys_path, request['message_id'])
        if not os.path.exists(key_path):
            os.makedirs(key_path)

        with open(os.path.join(key_path, "key.json"), "w+") as f:
            f.write(json.dumps(payload_data['content']))

        return dict(
            success=True,
            message_id=request['message_id']
        )
    
    def _receive_seek_user_response(self, request):
        assert type(request) == dict
        password = self.user.private_rsakey.decrypt(hexstr2bytes(request['payload']['password']))

        seek_token_decrypted = decrypt_symmetric(
            hexstr2bytes(request['payload']['seek_token']),
            password
        )
        host_info_decrypted = decrypt_symmetric(
            hexstr2bytes(request['payload']['host_info']),
            password
        )

        print(seek_token_decrypted)
        print(host_info_decrypted)

        # TODO JHILL: check the token here....
        return dict(
            success=True,
            message_id=request['message_id']
        )

    def process_request(self, request_text):
        print("*"*100)
        try:
            request_data = json.loads(request_text)

            if request_data['action'] == 'ping':
                return self._receive_ping(request_data)
            elif request_data['action'] == 'send_message':
                return self._receive_send_message(request_data)
            elif request_data['action'] == 'send_message_key':
                return self._receive_send_message_key(request_data)
            elif request_data['action'] == 'request_public_key':
                return self._receive_request_public_key(request_data)
            elif request_data['action'] == 'public_key_response':
                return self._receive_public_key_response(request_data)
            elif request_data['action'] == 'challenge_user':
                return self._receive_challenge_user(request_data)
            elif request_data['action'] == 'seek_user':
                return self._receive_seek_user(request_data)
            elif request_data['action'] == 'seek_user_response':
                return self._receive_seek_user_response(request_data)
            else:
                return dict(
                    success=False,
                    error="unknown action '{}'".format(request_data['action'])
                )
        except json.decoder.JSONDecodeError as e:
            return dict(
                success=False,
                error=str(e),
                request_text=request_text
            )

    def run(self):
        request_text = self.clientsocket.recv(int(65536 / 2)).decode()
        response = self.process_request(request_text)

        if type(response) == dict:
            response = json.dumps(response)
        else:
            print(colored("passing anything but dicts is deprecated", "red"))
            assert False

        self.clientsocket.sendall(response.encode())
        self.clientsocket.close()


class Surface(threading.Thread):
    login_token = None
    serversocket = None
    hostname = None
    username = None

    def __init__(self, username, port):
        super(Surface, self).__init__()
        self.port = port
        self.username = username

        while True:
            try:
                self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.serversocket.bind((socket.gethostname(), self.port))
                self.serversocket.listen(5)
                break
            except OSError:
                print(colored("trying next port", "yellow"))
                self.port = self.port + 1

        self.hostname = socket.gethostname()

    def run(self):
        while True:
            try:
                # print("*" * 100)
                (clientsocket, address) = self.serversocket.accept()
                st = SocketThread(clientsocket, self.username)
                st.start()
            except ConnectionAbortedError:
                pass