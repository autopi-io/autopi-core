
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
    - require:
      - file: minion-engines-configured  # As an initial precaution only update minion config if engines are configured correctly

minion-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.bak
    - source: /etc/salt/minion
    - force: true
    - onchanges:
      - file: /etc/salt/minion

minion-engines-configured:
  file.managed:
    - name: /etc/salt/minion.d/engines.conf
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/salt/{{ salt['grains.get']('id') }}/engines?format=yaml
    - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/salt/{{ salt['grains.get']('id') }}/engines?format=sha1sum
    - makedirs: true

minion-engines-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.d/engines.conf.bak
    - source: /etc/salt/minion.d/engines.conf
    - force: true
    - onlyif: test -f /etc/salt/minion.d/engines.conf
    - prereq:
      - file: minion-engines-configured

minion-restart-after-config-changes-required:
  module.wait:
    - name: minionutil.request_restart
    - reason: minion_config_changed
    - watch:
      - file: /etc/salt/minion
      - file: /etc/salt/minion.d/engines.conf
