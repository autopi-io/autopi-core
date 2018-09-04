
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

minion-configured:
  file.serialize:
    - name: /etc/salt/minion
    - dataset_pillar: minion
    - formatter: yaml
    - show_changes: True

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
