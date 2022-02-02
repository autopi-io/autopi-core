fences-backed-up:
 file.copy:
   - name: /etc/salt/minion.d/geofences.yaml.bak
   - source: /etc/salt/minion.d/geofences.yaml
   - force: true
   - onlyif: test -f /etc/salt/minion.d/geofences.yaml
   - prereq:
     - file: fences-configured

fences-configured:
 file.managed:
   - name: /etc/salt/minion.d/geofences.yaml
   - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:aut
h_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/geofence?format=yaml
   - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_ap
i:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/geofence?format=sha1sum
   - makedirs: true

minion-fences-cache-cleared-before-changes:
  file.absent:
    - name: /etc/salt/minion.d/_geofences.yaml
    - onchanges:
      - file: fences-configured

minion-restart-after-config-changes-required:
  module.wait:
    - name: minionutil.request_restart
    - reason: geofence_config_changes
    - watch:
      - file: /etc/salt/minion.d/geofences.yaml