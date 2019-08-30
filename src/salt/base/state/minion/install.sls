
include:
  - .patch
  - .config
  - .ext.sync

minion-id-cron-configured:
  cron.present:
    - identifier: minion-id-setup
    - name: "grep Serial /proc/cpuinfo | awk '{print $3}' | md5sum | awk '{print $1}' | tee /etc/salt/minion_id | cut -c21- | sed 's/^/autopi-/g' > /etc/hostname"
    - special: "@reboot"

minion-start-before-network:
  file.replace:
    - name: /lib/systemd/system/salt-minion.service
    - pattern: "^After=.*$"
    - repl: "Before=network-pre.target"

minion-api-call-script-installed:
  file.managed:
    - name: /usr/bin/autopi
    - source: salt://minion/api-call.py
    - mode: 755
    - user: root
    - group: root
