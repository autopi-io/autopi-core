
{% set _timestamp = None|strftime("%Y%m%d%H%M%S") %}

minion-restart-requested-after-patching:
  module.wait:
    - name: minionutil.request_restart
    - reason: minion_patched

minion-restart-requested-immediately-after-patching:
  module.wait:
    - name: minionutil.request_restart
    - immediately: true  # Restart minion service immediately because patch changes are crucial
    - reason: minion_patched

minion-script-001-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/minion.py
    - force: true
    - prereq:
      - file: minion-script-001-patched
minion-script-001-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py
    - source: salt://minion/patch/minion.py.patch001
    - hash: 36d5e76a283786e8040f2576e3ebd52910326d31
    # Only apply this patch if hash matches specific version
    - onlyif: cd /usr/lib/python2.7/dist-packages/salt/ && echo '31fa372f166f5d1e27394022780709de6e03e337 minion.py' | sha1sum -c -
    - watch_in:
      - module: minion-restart-requested-after-patching
minion-script-001-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py
    - source: /usr/lib/python2.7/dist-packages/salt/minion.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: minion-script-001-patched
minion-script-002-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/minion.py
    - force: true
    - prereq:
      - file: minion-script-002-patched
minion-script-002-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py
    - source: salt://minion/patch/minion.py.patch002
    - hash: 422b3a0877b468ad09327b50322274cc71b829f4
    # IMPORTANT: No 'onlyif' requisite for latest patch
    - watch_in:
      - module: minion-restart-requested-after-patching
minion-script-002-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/minion.py
    - source: /usr/lib/python2.7/dist-packages/salt/minion.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: minion-script-002-patched

fileclient-script-001-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/fileclient.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/fileclient.py
    - force: true
    - prereq:
      - file: fileclient-script-001-patched
fileclient-script-001-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/fileclient.py
    - source: salt://minion/patch/fileclient.py.patch001
    - hash: 2ed2f597d4f69ec85bc65e8a7002ca507c3cfc9a
    # Only apply this patch if hash matches specific version
    - onlyif: cd /usr/lib/python2.7/dist-packages/salt/ && echo '08413a2972ac91821ed06f0b0a9bd92c314cbf80 fileclient.py' | sha1sum -c -
    - watch_in:
      - module: minion-restart-requested-after-patching
fileclient-script-001-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/fileclient.py
    - source: /usr/lib/python2.7/dist-packages/salt/fileclient.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: fileclient-script-001-patched
fileclient-script-002-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/fileclient.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/fileclient.py
    - force: true
    - prereq:
      - file: fileclient-script-002-patched
fileclient-script-002-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/fileclient.py
    - source: salt://minion/patch/fileclient.py.patch002
    - hash: a8b8890707ff803e9e068b0d1d3ce51c4c44c844
    # IMPORTANT: No 'onlyif' requisite for latest patch
    - watch_in:
      - module: minion-restart-requested-after-patching
fileclient-script-002-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/fileclient.py
    - source: /usr/lib/python2.7/dist-packages/salt/fileclient.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: fileclient-script-002-patched

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

utils-files-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/files.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/utils/files.py
    - force: true
    - prereq:
      - file: utils-files-script-patched
utils-files-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/files.py
    - source: salt://minion/patch/utils/files.py.patch
    - hash: 6de59a409eb74cbff965f7b5961c88f2825fada9
    - watch_in:
      - module: minion-restart-requested-immediately-after-patching
utils-files-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/files.py
    - source: /usr/lib/python2.7/dist-packages/salt/utils/files.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: utils-files-script-patched

utils-systemd-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/systemd.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/utils/systemd.py
    - force: true
    - prereq:
      - file: utils-systemd-script-patched
utils-systemd-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/systemd.py
    - source: salt://minion/patch/utils/systemd.py.patch
    - hash: 457281e669b913245cc2b2f9201e65f51539642d
    - watch_in:
      - module: minion-restart-requested-after-patching
utils-systemd-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/utils/systemd.py
    - source: /usr/lib/python2.7/dist-packages/salt/utils/systemd.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: utils-systemd-script-patched

log-setup-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/log/setup.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/log/setup.py
    - force: true
    - prereq:
      - file: log-setup-script-patched
log-setup-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/log/setup.py
    - source: salt://minion/patch/log/setup.py.patch
    - hash: 3dfe270678c4bff4247fdb35e41f887c7938d332
    - watch_in:
      - module: minion-restart-requested-after-patching
log-setup-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/log/setup.py
    - source: /usr/lib/python2.7/dist-packages/salt/log/setup.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: log-setup-script-patched

config-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/config/__init__.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/config/__init__.py
    - force: true
    - prereq:
      - file: config-script-patched
config-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/config/__init__.py
    - source: salt://minion/patch/config/__init__.py.patch
    - hash: 5aee3a232231b656d06591964ffdf6b6397db3a1
    - watch_in:
      - module: minion-restart-requested-after-patching
config-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/config/__init__.py
    - source: /usr/lib/python2.7/dist-packages/salt/config/__init__.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: config-script-patched

loader-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/loader.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/loader.py
    - force: true
    - prereq:
      - file: loader-script-patched
loader-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/loader.py
    - source: salt://minion/patch/loader.py.patch
    - hash: aa05c84b5a3a22a8861c41d1e4b7029ea3f4a7ee
    - watch_in:
      - module: minion-restart-requested-after-patching
loader-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/loader.py
    - source: /usr/lib/python2.7/dist-packages/salt/loader.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: loader-script-patched

modules-dockermod-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/modules/dockermod.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/modules/dockermod.py
    - force: true
    - prereq:
      - file: modules-dockermod-script-patched
modules-dockermod-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/modules/dockermod.py
    - source: salt://minion/patch/modules/dockermod.py.patch
    - hash: 61aa034a35139aa3646f7a6a2a3ffe6e2e50ea4f
    - watch_in:
      - module: minion-restart-requested-after-patching
modules-dockermod-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/modules/dockermod.py
    - source: /usr/lib/python2.7/dist-packages/salt/modules/dockermod.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: modules-dockermod-script-patched

modules-pip-script-backed-up:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/modules/pip.py.{{ _timestamp }}
    - source: /usr/lib/python2.7/dist-packages/salt/modules/pip.py
    - force: true
    - prereq:
      - file: modules-pip-script-patched
modules-pip-script-patched:
  file.patch:
    - name: /usr/lib/python2.7/dist-packages/salt/modules/pip.py
    - source: salt://minion/patch/modules/pip.py.patch
    - hash: a469353832b60f4c1a0d08bc67a84679159e9a00
    - watch_in:
      - module: minion-restart-requested-after-patching
modules-pip-script-rolled-back:
  file.copy:
    - name: /usr/lib/python2.7/dist-packages/salt/modules/pip.py
    - source: /usr/lib/python2.7/dist-packages/salt/modules/pip.py.{{ _timestamp }}
    - force: true
    - onfail:
      - file: modules-pip-script-patched
