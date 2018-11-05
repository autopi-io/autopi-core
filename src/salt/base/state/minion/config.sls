
# Ensure valid pillar data is present to prevent writing an empty minion config file 
minion-pillar-data-present:
  module.run:
    - name: pillar.keys
    - key: minion
    - prereq:
      - file: /etc/salt/minion

minion-configured:
  file.serialize:
    - name: /etc/salt/minion
    - dataset_pillar: minion
    - formatter: yaml
    - show_changes: True

minion-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.bak
    - source: /etc/salt/minion
    - force: true
    - onchanges:
      - file: /etc/salt/minion

minion-restart-after-config-changes-required:
  module.wait:
    - name: minionutil.request_restart
    - watch:
      - file: /etc/salt/minion
