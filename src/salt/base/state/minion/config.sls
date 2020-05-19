
# Ensure valid pillar data is present to prevent writing an empty minion config file 
minion-pillar-data-present:
  module.run:
    - name: pillar.keys
    - key: minion
    - prereq:
      - file: minion-configured

minion-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.bak
    - source: /etc/salt/minion
    - force: true
    - prereq:
      - file: minion-configured
minion-configured:
  file.serialize:
    - name: /etc/salt/minion
    - dataset_pillar: minion
    - formatter: yaml
    - show_changes: True
    - require:
      - file: minion-engines-configured  # As an initial precaution only update minion config if engines are configured correctly

minion-engines-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.d/engines.conf.bak
    - source: /etc/salt/minion.d/engines.conf
    - force: true
    - onlyif: test -f /etc/salt/minion.d/engines.conf
    - prereq:
      - file: minion-engines-configured
minion-engines-configured:
  file.managed:
    - name: /etc/salt/minion.d/engines.conf
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/engines?format=yaml
    - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/engines?format=sha1sum
    - makedirs: true

minion-schedule-config-backed-up:
  file.copy:
    - name: /etc/salt/minion.d/schedule.conf.bak
    - source: /etc/salt/minion.d/schedule.conf
    - force: true
    - onlyif: test -f /etc/salt/minion.d/schedule.conf
    - prereq:
      - file: minion-schedule-configured
minion-schedule-configured:
  file.managed:
    - name: /etc/salt/minion.d/schedule.conf
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/schedule?format=yaml
    - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/schedule?format=sha1sum
    - makedirs: true
minion-schedule-cache-cleared-before-changes:
  file.absent:
    - name: /etc/salt/minion.d/_schedule.conf
    - onchanges:
      - file: minion-schedule-configured

minion-restart-after-config-changes-required:
  module.wait:
    - name: minionutil.request_restart
    - reason: minion_config_changes
    - watch:
      - file: /etc/salt/minion
      - file: /etc/salt/minion.d/engines.conf
      - file: /etc/salt/minion.d/schedule.conf
