#coding=utf-8
import socket
import json
import sys
import stomp
import codecs
import time

UTF8Writer = codecs.getwriter('utf8')
sys.stdout = UTF8Writer(sys.stdout)
login_serv_ip = sys.argv[1]
login_serv_port = int(sys.argv[2])

STATUS = u'status'
MESSAGE = u'message'
TOKEN = u'token'
INVITE = u'invite'
FRIEND = u'friend'
POST = u'post'
ID = u'id'
SUBSCRIBE = u'subscribe'
GROUP = u'group'
APPSERVER = u'appserver'
REARRANGE = u'rearrange'

token_dic = {}
AS_dic = {}
# listen to mq
class MyListener(stomp.ConnectionListener):
    def on_error(self, headers, message):
        print('received an error "%s"' % message)
    def on_message(self, headers, message):
        type = headers['type']
        sender = headers['sender']
        receiver = headers['destination'].split('/')[3]
        if type == 'private':
            print('<<<%s->%s: %s>>>' % (sender, receiver, message))
        if type == 'group':
            print('<<<%s->GROUP<%s>: %s>>>' % (sender, receiver, message))

actvmq = stomp.Connection(host_and_ports=[('18.219.36.31', 61613)])
actvmq.set_listener('', MyListener())
actvmq.start()
actvmq.connect('admin', 'admin', wait=True)

while True:
    # default connect to login server
    serv_ip = login_serv_ip
    serv_port = login_serv_port
    try:
        raw_in = raw_input('')
        if raw_in == '': continue # server does not handle
        usr_in = raw_in.split(' ', 2)
        command = usr_in[0]
        usr_name = usr_in[1]

        if command != 'register' and command != 'login':
            if token_dic.has_key(usr_name): # replace with token
                usr_in[1] = token_dic[usr_name]
                if command != 'logout' and command != 'delete':
                    serv_ip = AS_dic[usr_name]
                    serv_port = 3333

    except:
        if raw_in.strip() == 'exit':
            token_dic.clear()
            AS_dic.clear()
            actvmq.disconnect()
            break
        else:
            request = raw_in
    else:
        request = ' '.join(usr_in)
    # creat socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    '''
    if serv_ip == login_serv_ip:
        print 'connect to login server', serv_ip
    else:
        print 'connect to app server', serv_ip
    '''
    try:
        sk.connect((serv_ip, serv_port))
    except:
        print 'fail connection'
        break

    #print request
    sk.sendall(request)
    #print time.asctime( time.localtime(time.time()) )
    json_response = sk.recv(1024)
    sk.close()

    rsp = json.loads(json_response) # retval: dict
    # show response
    if rsp.has_key(MESSAGE):
        print rsp[MESSAGE]
    # store/remove token
    if rsp.has_key(TOKEN) and rsp[TOKEN] not in token_dic.values():
        token_dic.update({usr_name : rsp[TOKEN]})
        actvmq.subscribe(
            destination = '/topic/private/' + usr_name,
            id = rsp[TOKEN],
            ack = 'client-individual'
        )
        if rsp.has_key(GROUP):
            for group_name in rsp[GROUP]:
                actvmq.subscribe(
                    destination = '/topic/public/' + group_name,
                    id = usr_name + group_name,
                    ack = 'client-individual'
                )
    if (command == 'logout' or command == 'delete') and rsp[STATUS] == 0:
        # unsubscribe private channel
        actvmq.unsubscribe(token_dic[usr_name])
        # unsubscribe group channel
        for group_name in rsp[GROUP]:
            actvmq.unsubscribe(usr_name + group_name)
        del token_dic[usr_name]
        del AS_dic[usr_name]

    # store / remove appServer data
    if rsp.has_key(APPSERVER):
        AS_dic[usr_name] = str(rsp[APPSERVER])
    if rsp.has_key(REARRANGE):
        for usr, new_ip in rsp[REARRANGE].items():
            AS_dic[str(usr)] = new_ip
        #print 'rearranged'
    # run-time subscribe (create-group / join-group)
    if rsp.has_key(SUBSCRIBE):
        actvmq.subscribe(
            destination = '/topic/public/' + rsp[SUBSCRIBE],
            id = usr_name + rsp[SUBSCRIBE],
            ack = 'client-individual'
        )
    # show group
    if rsp.has_key(GROUP) and (command == 'list-group' or command == 'list-joined'):
        if len(rsp[GROUP]) == 0:
            print 'No groups'
        else:
            print '\n'.join(rsp[GROUP])
    # show list
    if rsp.has_key(INVITE):
        if len(rsp[INVITE]) == 0:
            print 'No invitations'
        else:
            print '\n'.join(rsp[INVITE])
    if rsp.has_key(FRIEND):
        if len(rsp[FRIEND]) == 0:
            print 'No friends'
        else:
            print '\n'.join(rsp[FRIEND])
    # show post
    if rsp.has_key(POST):
        if len(rsp[POST]) == 0:
            print 'No posts'
        else:
            for post in rsp[POST]:
                print post[ID] + ': ' + post[MESSAGE]
