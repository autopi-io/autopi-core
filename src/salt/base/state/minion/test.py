# This Python file uses the following encoding: utf-8
import json

class bcolors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'


def get_unit_id():
        url = 'http://localhost:9000'
        req = urllib2.Request(url)
        f = urllib2.urlopen(req)
        response = f.read()
        f.close()
        return uuid.UUID(json.loads(response).get('unit_id'))


def run_tests(unit_id):
        url = 'http://localhost:9000/dongle/{:}/execute/'.format(unit_id)
        #print('Running tests via API: ' + url)
        data = json.dumps({ "command": "state.sls", "arg":["test"], "kwarg":{}})
        req = urllib2.Request(url, data, {'Content-Type': 'application/json', 'Content-Length': len(data) })
        f = urllib2.urlopen(req)
        response = f.read()
        f.close()

        return json.loads(response)
        

print(bcolors.OKGREEN + 'Initializing tests.' + bcolors.ENDC)
import urllib2
import uuid
import time
import sys

unit_id = ''
retry_counter = 0
print('Attempting to retrieve unit_id from API')
while True:
        try:
                retry_counter += 1
                unit_id = get_unit_id()
                print('Retrieved unit_id successfully, API is ready')
                print('')
                break
        except:
                if retry_counter > 50:
                        print(bcolors.FAIL + 'API retried 50 times, stopping' + bcolors.ENDC)
                        sys.exit('API was not ready')
                if retry_counter == 1:
                        print(bcolors.WARNING + 'API was not ready yet, retrying every 2 sec' + bcolors.ENDC)
                else:
                        sys.stdout.write('.')
                time.sleep(2)

print('Running tests')
result = run_tests(unit_id)

errordetails = []

for key in result.keys():
        if result[key]['result']:
                print('{:} ✔  {:}{:}'.format(bcolors.OKGREEN, result[key]['comment'], bcolors.ENDC))
        else:
                print('{:} ✘  {:}{:}'.format(bcolors.FAIL, result[key]['comment'], bcolors.ENDC))
                errordetails.append(result[key])

print('')

if errordetails:
        print (bcolors.FAIL + 'Error details' + bcolors.ENDC)
        for errordetail in errordetails:
                print('{:}{:}{:}'.format(bcolors.FAIL, json.dumps(errordetail, indent=4), bcolors.ENDC))
        print('')
else:
        print (bcolors.OKGREEN + 'Success' + bcolors.ENDC)

succeded = len(result.keys()) - len(errordetails)
print('Finished running {:} states, succeded: {:}, failed: {:}'.format(len(result.keys()), succeded, len(errordetails)))