fences-configured:
 file.managed:
   - name: /opt/autopi/geofence/geofences.yaml
   - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:aut
h_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/geofence?format=yaml
   - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_ap
i:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/geofence?format=sha1sum
   - makedirs: true

geofence-settings-loaded:
  module.run:
    - name: tracking.load_geofences
    - require:
      - file: /opt/autopi/geofence/geofences.yaml
    - onchanges:
      - file: /opt/autopi/geofence/geofences.yaml
