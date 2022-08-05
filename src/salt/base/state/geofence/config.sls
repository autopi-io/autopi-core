
geofence-settings-configured:
 file.managed:
   - name: /opt/autopi/geofence/settings.yaml
   - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/geofence?format=yaml
   - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/salt/geofence?format=sha1sum
   - makedirs: true

{%- if salt['pillar.get']('setup:mpcie:module') %}
geofence-settings-loaded:
  module.run:
    {%- if salt['pillar.get']('setup:mpcie:module') in ["ec2x", "bg96"] %}
    - name: tracking.load_geofences
    {%- else %}
    - name: gnss.load_geofences 
    {%- endif %}
    - require:
      - file: geofence-settings-configured
    - onchanges:
      - file: geofence-settings-configured
{%- endif %}