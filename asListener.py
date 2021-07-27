import json
import stomp
import sys
import time

as_ip = sys.argv[1]

# listen to mq
class MyListener(stomp.ConnectionListener):
    def on_error(self, headers, message):
        print('received an error "%s"' % message)
    def on_message(self, headers, message):
        print message
        print ''

actvmq = stomp.Connection(host_and_ports=[('18.219.36.31', 61613)])
cls_listner = MyListener()
actvmq.set_listener('', cls_listner)
actvmq.start()
actvmq.connect('admin', 'admin', wait=True)
actvmq.subscribe(
    destination = '/topic/public/ASlog/' + as_ip,
    id = 'minitoring_' + as_ip,
    ack = 'client-individual'
)

print 'start listening to', as_ip
while True:
    time.sleep(2)
