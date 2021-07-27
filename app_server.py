#coding=utf-8
import socket
import json
import sys
import os.path
import uuid
import stomp

STATUS = 'status'
MESSAGE = 'message'
TOKEN = 'token'
INVITE = 'invite'
FRIEND = 'friend'
POST = 'post'
SUBSCRIBE = 'subscribe'
GROUP = 'group'

listen_ip = sys.argv[1]
listen_port = int(sys.argv[2])


# listen to mq
class MyListener(stomp.ConnectionListener):
    def __init__(self):
        self.updated_user_db = json.dumps({'SYSTEMgrouplist':[]})
        self.updated_login_db = json.dumps({})
        self.user_db_update_flag = 1
        self.login_db_update_flag = 1
    def on_error(self, headers, message):
        print('received an error "%s"' % message)
    def on_message(self, headers, message):
        type = headers['type']
        sender = headers['sender']
        if type == 'user_db' and sender != listen_ip:
            self.updated_user_db = message
            self.user_db_update_flag = 1
        if type == 'login_db':
            self.updated_login_db = message
            self.login_db_update_flag = 1

actvmq = stomp.Connection(host_and_ports=[('18.219.36.31', 61613)])
cls_listner = MyListener()
actvmq.set_listener('', cls_listner)
actvmq.start()
actvmq.connect('admin', 'admin', wait=True)
actvmq.subscribe(
    destination = '/topic/public/user_db',
    id = listen_ip + '/user_db',
    ack = 'client-individual'
)
actvmq.subscribe(
    destination = '/topic/public/login_db',
    id = listen_ip + '/login_db',
    ack = 'client-individual'
)

# creat socket
sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sk.bind((listen_ip, listen_port))
sk.listen(100)
while True:
    (connect_sk, client) = sk.accept()
    print 'connect by', client
    request = connect_sk.recv(2048).decode()
    print 'request:', request
    brok_rqst = request.split()
    cmd = brok_rqst[0]
    rsp = {
        STATUS : -1,
        MESSAGE: ''
    }
    # update db once per request
    if cls_listner.user_db_update_flag == 1:
        user_db = json.loads(cls_listner.updated_user_db)
        print 'renew user db'
        cls_listner.user_db_update_flag = 0
    if cls_listner.login_db_update_flag == 1:
        login_db = json.loads(cls_listner.updated_login_db)
        print 'renew login db'
        cls_listner.login_db_update_flag = 0
    # processing command
    if cmd == 'invite':
        if 2 <= len(brok_rqst) and brok_rqst[1] in login_db:
            if len(brok_rqst) == 3:
                username = login_db[brok_rqst[1]]
                invitee = brok_rqst[2]

                if invitee in user_db[username]['friends']:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = invitee + ' is already your friend'
                elif invitee not in user_db:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = invitee + ' does not exist'
                elif username == invitee:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = 'You cannot invite yourself'
                elif invitee in user_db[username]['outgoing_invitation']:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = 'Already invited'
                elif invitee in user_db[username]['incoming_invitation']:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = invitee + ' has invited you'
                else:
                    user_db[username]['outgoing_invitation'].append(invitee)
                    user_db[invitee]['incoming_invitation'].append(username)
                    rsp[STATUS] = 0
                    rsp[MESSAGE] = 'Success!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: invite ​<user>​ ​<id>​'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'accept-invite':
        if 2 <= len(brok_rqst) and brok_rqst[1] in login_db:
            if len(brok_rqst) == 3:
                username = login_db[brok_rqst[1]]
                inviter = brok_rqst[2]

                if inviter not in user_db[username]['incoming_invitation']:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = inviter + ' did not invite you'
                else:
                    user_db[username]['incoming_invitation'].remove(inviter)
                    user_db[username]['friends'].append(inviter)
                    user_db[inviter]['outgoing_invitation'].remove(username)
                    user_db[inviter]['friends'].append(username)
                    rsp[STATUS] = 0
                    rsp[MESSAGE] = 'Success!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: accept-invite ​<user>​ ​<id>​'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'list-invite':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            if len(brok_rqst) == 2:
                username = login_db[brok_rqst[1]]
                rsp[STATUS] = 0
                rsp.update({INVITE : user_db[username]['incoming_invitation']})
                rsp.pop(MESSAGE)
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: list-invite ​<user>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'list-friend':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            if len(brok_rqst) == 2:
                username = login_db[brok_rqst[1]]
                rsp[STATUS] = 0
                rsp.update({FRIEND : user_db[username]['friends']})
                rsp.pop(MESSAGE)
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: list-friend ​<user>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'post':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) != 2:
                sentence = request.split(' ', 2)[2]
                user_db[username]['posts'].append(sentence)
                rsp[STATUS] = 0
                rsp[MESSAGE] = 'Success!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: post ​<user> ​​<message>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'receive-post':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            if len(brok_rqst) == 2:
                username = login_db[brok_rqst[1]]
                received = []
                for friend in user_db[username]['friends']:
                    for post in user_db[friend]['posts']:
                        formed_post = {
                            'id' : friend,
                            'message' : post
                        }
                        received.append(formed_post)
                rsp[STATUS] = 0
                rsp.update({POST : received})
                rsp.pop(MESSAGE)
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: receive-post ​<user>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'send':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) >= 4:
                receiver = brok_rqst[2]
                if receiver in user_db:
                    if receiver in user_db[username]['friends']:
                        if receiver in login_db.values():
                            sentence = request.split(' ', 3)[3]
                            actvmq.send(body = sentence, destination = '/topic/private/' + receiver, headers = {'sender':username, 'type':'private'})
                            rsp[STATUS] = 0
                            rsp[MESSAGE] = 'Success!​'
                        else:
                            rsp[STATUS] = 1
                            rsp[MESSAGE] = receiver + ' is not online'
                    else:
                        rsp[STATUS] = 1
                        rsp[MESSAGE] = receiver + ' is not your friend'
                else:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = 'No such user exist'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: send ​<user> <friend> ​​<message>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'create-group':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) == 3:
                group_name = brok_rqst[2]
                if group_name not in user_db['SYSTEMgrouplist']:
                    user_db[username]['groups'].append(group_name)
                    user_db['SYSTEMgrouplist'].append(group_name)
                    rsp[STATUS] = 0
                    rsp.update({SUBSCRIBE:group_name})
                    rsp[MESSAGE] = 'Success!​'
                else:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = group_name + ' already exist'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: create-group <user> <group>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'list-group':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            if len(brok_rqst) == 2:
                rsp[STATUS] = 0
                rsp.update({GROUP:user_db['SYSTEMgrouplist']})
                rsp.pop(MESSAGE)
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: list-group ​<user>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'list-joined':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) == 2:
                rsp[STATUS] = 0
                rsp.update({GROUP:user_db[username]['groups']})
                rsp.pop(MESSAGE)
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: list-joined ​<user>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'join-group':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) == 3:
                group_name = brok_rqst[2]
                if group_name in user_db['SYSTEMgrouplist']:
                    if group_name not in user_db[username]['groups']:
                        user_db[username]['groups'].append(group_name)
                        rsp[STATUS] = 0
                        rsp.update({SUBSCRIBE:group_name})
                        rsp[MESSAGE] = 'Success!​'
                    else:
                        rsp[STATUS] = 1
                        rsp[MESSAGE] = 'Already a member of ' + group_name
                else:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = group_name + ' does not exist'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: join-group <user> <group>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'send-group':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) >= 4:
                group = brok_rqst[2]
                if group in user_db['SYSTEMgrouplist']:
                    if group in user_db[username]['groups']:
                        sentence = request.split(' ', 3)[3]
                        actvmq.send(body = sentence, destination = '/topic/public/' + group, headers = {'sender':username, 'type':'group'})
                        rsp[STATUS] = 0
                        rsp[MESSAGE] = 'Success!​'
                    else:
                        rsp[STATUS] = 1
                        rsp[MESSAGE] = 'You are not the member of ' + group
                else:
                    rsp[STATUS] = 1
                    rsp[MESSAGE] = 'No such group exist'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: send-group ​<user> <group> ​​<message>'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    else:
        rsp[STATUS] = 1
        rsp[MESSAGE] = 'Unknown command ' + cmd

    # store user_db
    actvmq.send(
        body = json.dumps(user_db),
        destination = '/topic/public/user_db',
        headers = {'sender':listen_ip, 'type':'user_db'}
    )

    print json.dumps(user_db, indent=2, sort_keys=True)
    print json.dumps(login_db, indent=2, sort_keys=True)
    print json.dumps(rsp, indent=2, sort_keys=True)

    connect_sk.sendall(json.dumps(rsp).encode())
    connect_sk.close()
sk.close()
actvmq.disconnect()
