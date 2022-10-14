
include:
  - .patch
  - .config
  - .ext.sync

minion-id-cron-configured:
  cron.present:
    - identifier: minion-id-setup
    - name: "grep Serial /proc/cpuinfo | awk '{print $3}' | md5sum | awk '{print $1}' | tee /etc/salt/minion_id | sed 's/^/autopi-/g' > /etc/hostname"
    - special: "@reboot"

#minion-start-before-network:
#  file.replace:
#    - name: /lib/systemd/system/salt-minion.service
#    - pattern: "^After=.*$"
#    - repl: "Before=network-pre.target"

minion-host-aliases-configured:
  file.managed:
    - name: /boot/host.aliases
    - source: salt://minion/host.aliases.jinja
    - template: jinja
    - mode: 755

minion-service-configured:
  file.managed:
    - name: /lib/systemd/system/salt-minion.service
    - source: salt://minion/minion.service

minion-api-call-script-installed:
  file.managed:
    - name: /usr/bin/autopi
    - source: salt://minion/api-call.py
    - mode: 755
    - user: root
    - group: root
    - watch_in:
      - module: minion-restart-after-config-changes-required
