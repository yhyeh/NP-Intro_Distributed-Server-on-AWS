#coding=utf-8
import socket
import json
import sys
import os
import uuid
import stomp
import time
import boto3

scale = 10
# response items
STATUS = 'status'
MESSAGE = 'message'
TOKEN = 'token'
INVITE = 'invite'
FRIEND = 'friend'
POST = 'post'
SUBSCRIBE = 'subscribe'
GROUP = 'group'
APPSERVER = 'appserver'
REARRANGE = 'rearrange'
app_cmd = [
    'invite', 'accept-invite', 'list-invite',
    'list-friend', 'post', 'receive-post',
    'send', 'create-group', 'list-group',
    'list-joined', 'join-group', 'send-group'
]
def launch_AS():
    # get current time
    localtime = time.asctime( time.localtime(time.time()) )
    print "Local current time :", localtime

    # launch app server
    ec2_client = boto3.client('ec2')
    ins_num = 1
    appServer = ec2_client.run_instances(
        LaunchTemplate={
            'LaunchTemplateName': 'AppServerTemplate',
        },
        MaxCount=ins_num,
        MinCount=1
    )
    print 'App Server launched'
    # get id
    AS_id = []
    for instance in appServer['Instances']:
        AS_id.append(instance['InstanceId'])
    # check status
    running_count = 0
    while running_count != ins_num:
        time.sleep(1)
        appServer = ec2_client.describe_instances(InstanceIds=AS_id)
        running_count = 0
        for instance in appServer['Reservations'][0]['Instances']:
            print instance['State']['Name']
            if instance['State']['Name'] == 'running':
                running_count += 1
    # ready -> get id, ip again
    AS_id = []
    AS_pubip = []
    AS_priip = []
    for instance in appServer['Reservations'][0]['Instances']:
        AS_id.append(instance['InstanceId'])
        AS_pubip.append(instance['PublicIpAddress'])
        AS_priip.append(instance['PrivateIpAddress'])
    print 'ID:', AS_id
    print 'public IP:', AS_pubip
    print 'private IP:', AS_priip

    # send source code and execute
    ssm_client = boto3.client('ssm')
    for id, pub_ip, pri_ip in zip(AS_id, AS_pubip, AS_priip):
        id_list = []
        id_list.append(id)
        os.system('scp -i ~/.ssh/aws_vm1.pem /home/ubuntu/app_server.py ubuntu@' + pub_ip + ':/home/ubuntu')
        online = 0
        while online != 1:
            time.sleep(1)
            os.system('aws ssm describe-instance-information > /home/ubuntu/ins_info.txt')
            fr = open('/home/ubuntu/ins_info.txt')
            server_rsp = json.loads(fr.read())
            fr.close()
            for ins in server_rsp['InstanceInformationList']:
                if ins['InstanceId'] == id:
                    print ins['PingStatus']
                    if ins['PingStatus'] == 'Online':
                        online = 1
                    break
        time.sleep(60)
        response = ssm_client.send_command(
            InstanceIds=id_list,
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands':[
                    'python /home/ubuntu/app_server.py ' + pri_ip + ' 3333 > /home/ubuntu/out.txt'
                ]
            }
        )
        time.sleep(150)
    # get current time
    localtime = time.asctime( time.localtime(time.time()) )
    print "Local current time :", localtime

    return (AS_id[0], AS_pubip[0])

listen_ip = sys.argv[1]
listen_port = int(sys.argv[2])

# listen to mq
class MyListener(stomp.ConnectionListener):
    def __init__(self):
        self.updated_user_db = json.dumps({'SYSTEMgrouplist':[]})
        self.user_db_update_flag = 1
    def on_error(self, headers, message):
        print('received an error "%s"' % message)
    def on_message(self, headers, message):
        type = headers['type']
        sender = headers['sender']
        if type == 'user_db' and sender != listen_ip:
            self.updated_user_db = message
            self.user_db_update_flag = 1

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

# user_db ... username:user_struct
user_struct = {
    'passwd' : None,
    'incoming_invitation' : None,
    'outgoing_invitation' : None,
    'friends' : None,
    'posts' : None,
    'groups' : None
}
login_db = {} # token : username
AS_status = {}
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
    # processing command
    if cmd == 'register':
        if len(brok_rqst) == 3:
            username = brok_rqst[1]
            if username not in user_db:
                user_db.update({brok_rqst[1] : dict(user_struct)})
                user_db[username]['passwd'] = brok_rqst[2]
                user_db[username]['incoming_invitation'] = list()
                user_db[username]['outgoing_invitation'] = list()
                user_db[username]['friends'] = list()
                user_db[username]['posts'] = list()
                user_db[username]['groups'] = list()
                rsp[STATUS] = 0
                rsp[MESSAGE] = 'Success!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = username + ' is already used'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Usage: register ​<id>​ ​<password>​'
    elif cmd == 'login':
        if len(brok_rqst) == 3:
            username = brok_rqst[1]
            if username in user_db and username not in login_db.values() and brok_rqst[2] == user_db[username]['passwd']:
                token = str(uuid.uuid4())
                login_db.update({token:username})
                rsp.update({TOKEN:token})
                rsp.update({GROUP:user_db[username]['groups']})
                # judge if app server enough
                if len(login_db) > len(AS_status)*scale:
                    (as_id, as_ip) = launch_AS()
                    AS_status.update({as_id:{'ip':as_ip, 'users':[username]}})
                else:
                    for as_id, as_data in AS_status.items():
                        if len(as_data['users']) < scale:
                            AS_status[as_id]['users'].append(username)
                            as_id = as_id
                            as_ip = as_data['ip']
                            break

                rsp.update({APPSERVER:as_ip})
                rsp[STATUS] = 0
                rsp[MESSAGE] = 'Success!​'
            elif username in user_db and username in login_db.values() and brok_rqst[2] == user_db[username]['passwd']:
                for tok, name in login_db.items():
                    if name == username:
                        token = tok
                        break
                rsp.update({TOKEN:token})
                rsp.update({GROUP:user_db[username]['groups']})
                for as_data in AS_status.values():
                    if username in as_data['users']:
                        rsp.update({APPSERVER:as_data['ip']})
                        break
                rsp[STATUS] = 0
                rsp[MESSAGE] = 'Success!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'No such user or password error'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Usage: login ​<id>​ ​<password>​'
    elif cmd == 'delete':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            if len(brok_rqst) == 2:
                username = login_db[brok_rqst[1]]
                for friend in user_db[username]['friends']:
                    user_db[friend]['friends'].remove(username)
                for invitee in user_db[username]['outgoing_invitation']:
                    user_db[invitee]['incoming_invitation'].remove(username)
                rsp.update({GROUP:user_db[username]['groups']})
                user_db.pop(username)
                login_db.pop(brok_rqst[1])
                rsp[STATUS] = 0
                rsp[MESSAGE] = 'Success!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: delete ​<user>​'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd == 'logout':
        if len(brok_rqst) >= 2 and brok_rqst[1] in login_db:
            username = login_db[brok_rqst[1]]
            if len(brok_rqst) == 2:
                login_db.pop(brok_rqst[1])
                rsp[STATUS] = 0
                rsp.update({GROUP:user_db[username]['groups']})
                rsp[MESSAGE] = 'Bye!​'
            else:
                rsp[STATUS] = 1
                rsp[MESSAGE] = 'Usage: logout ​<user>​'
        else:
            rsp[STATUS] = 1
            rsp[MESSAGE] = 'Not login yet'
    elif cmd in app_cmd:
        rsp[STATUS] = 1
        rsp[MESSAGE] = 'Not login yet'
    else:
        rsp[STATUS] = 1
        rsp[MESSAGE] = 'Unknown command ' + cmd
    # advertise DB
    actvmq.send(
        body = json.dumps(user_db),
        destination = '/topic/public/user_db',
        headers = {'sender':listen_ip, 'type':'user_db'}
    )
    actvmq.send(
        body = json.dumps(login_db),
        destination = '/topic/public/login_db',
        headers = {'sender':listen_ip, 'type':'login_db'}
    )
    # remove user from app server
    if (cmd == 'logout' or cmd == 'delete') and rsp[STATUS] == 0:
        for as_id, as_data in AS_status.items():
            if username in as_data['users']:
                AS_status[as_id]['users'].remove(username)
                break
        # check if need to shrink app server
        if len(login_db) <= (len(AS_status)-1)*scale:
            for as_id, as_data in AS_status.items():
                closed_users = as_data['users']
                AS_status.pop(as_id)
                '''
                terminate one app server
                '''
                ec2_client = boto3.client('ec2')
                response = ec2_client.terminate_instances(
                    InstanceIds=[as_id],
                )
                print 'terminate', as_id, as_data['ip']
                '''
                while True:
                    time.sleep(1)
                    try:
                        ins = response['TerminatingInstances'][0]
                        print ins['CurrentState']['Name']
                        if ins['CurrentState']['Name'] == 'terminated':
                            break
                    except:
                        print 'responce has no instance'
                '''
                break
            # rearrange no home user
            rearrange_ip = {}
            for usr in closed_users:
                for as_id, as_data in AS_status.items():
                    if len(as_data['users']) < scale:
                        AS_status[as_id]['users'].append(usr)
                        rearrange_ip.update({usr:as_data['ip']})
                        break
            rsp.update({REARRANGE:rearrange_ip})

    # store user_db
    print json.dumps(user_db, indent=2, sort_keys=True)
    print json.dumps(login_db, indent=2, sort_keys=True)
    print json.dumps(AS_status, indent=2, sort_keys=True)
    print json.dumps(rsp, indent=2, sort_keys=True)

    connect_sk.sendall(json.dumps(rsp).encode())
    connect_sk.close()
sk.close()
actvmq.disconnect()
