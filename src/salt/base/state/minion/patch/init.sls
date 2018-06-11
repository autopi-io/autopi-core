
{% set _timestamp = None|strftime("%Y%m%d%H%M%S") %}

minion-restart-requested-after-patching:
  module.wait:
    - name: minionutil.request_restart

minion-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/minion.py
    - force: true
    - prereq:
      - file: minion-script-patched
minion-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py
    - source: salt://minion/patch/minion.py.patch
    - hash: 36d5e76a283786e8040f2576e3ebd52910326d31
    - watch_in:
      - module: minion-restart-requested-after-patching
minion-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py
    - source: /usr/lib/python2.7/dist-packages/salt/minion.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: minion-script-patched

utils-schedule-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/schedule.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/utils/schedule.py
    - force: true
    - prereq:
      - file: utils-schedule-script-patched
utils-schedule-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/schedule.py
    - source: salt://minion/patch/utils/schedule.py.patch
    - hash: e0b2c0262264ce39b50cca882cc95524fc08b4ff
    - watch_in:
      - module: minion-restart-requested-after-patching
utils-schedule-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/schedule.py
    - source: /usr/lib/python2.7/dist-packages/salt/utils/schedule.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: utils-schedule-script-patched
