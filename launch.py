import boto3
import json
import time

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
# get server info and wait until running
AS_id = []
AS_ip = []
for instance in appServer['Instances']:
    AS_id.append(instance['InstanceId'])
    AS_pubip.append(instance['PublicIpAddress'])
    AS_priip.append(instance['PrivateIpAddress'])
print 'ID:', AS_id
print 'public IP:', AS_pubip
print 'private IP:', AS_priip
running_count = 0
while running_count != ins_num:
    time.sleep(1)
    appServer = ec2_client.describe_instances(InstanceIds=AS_id)
    running_count = 0
    for i in range(ins_num):
        if appServer['Instances'][i]['State']['Name'] == 'running':
            running_count += 1

# send source code and execute
ssm_client = boto3.client('ssm')
for id, pub_ip, pri_ip in zip(AS_id, AS_pubip, AS_priip):
    response = ssm_client.send_command(
        InstanceIds=[id],
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands':[
                'scp -i ~/.ssh/aws_vm1.pem /home/ubuntu/app_server.py ubuntu@' + pub_ip + ':/home/ubuntu',
                'python /home/ubuntu/app_server.py ' + pri_ip + ' 3333'
            ]
        }
    )
# get current time
localtime = time.asctime( time.localtime(time.time()) )
print "Local current time :", localtime
