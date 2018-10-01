
include:
  - .patch

minion-id-cron-configured:
  cron.present:
    - identifier: minion-id-setup
    - name: "grep Serial /proc/cpuinfo | awk '{print $3}' | md5sum | awk '{print $1}' > /etc/salt/minion_id"
    - special: "@reboot"

minion-start-before-network:
  file.replace:
    - name: /lib/systemd/system/salt-minion.service
    - pattern: "^After=.*$"
    - repl: "Before=network-pre.target"

# Ensure valid pillar data is present to prevent writing an empty minion config file 
minion-pillar-data-present:
  module.run:
    - name: pillar.keys
    - key: minion
    - prereq:
      - file: /etc/salt/minion

minion-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.bak
    - source: /etc/salt/minion
    - force: true
    - prereq:
      - file: /etc/salt/minion

minion-configured:
  file.serialize:
    - name: /etc/salt/minion
    - dataset_pillar: minion
    - formatter: yaml
    - show_changes: True
    - onlyif:
      - {{ salt['pillar.filter_by']('{"*": True, default: False}', 'minion:master') }}

minion-api-call-script-installed:
  file.managed:
    - name: /usr/bin/autopi
    - source: salt://minion/api-call.py
    - mode: 755
    - user: root
    - group: root

minion-restart-after-config-changes-required:
  module.wait:
    - name: minionutil.request_restart
    - watch:
      - file: /etc/salt/minion
