
{%- for bus in salt['pillar.get']('obd:buses', default=[]) %}
{%- if bus.get('has_can_msgs', False) %}
obd-can-db-{{ bus['id'] }}-synced:
  file.managed:
    - name: /opt/autopi/obd/can/db/{{ bus['protocol_id'] }}.dbc
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/obd/bus/{{ bus['id'] }}/can/db?format=dbc
    - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/obd/bus/{{ bus['id'] }}/can/db?format=sha1sum
    - makedirs: true
{%- else %}
obd-can-db-{{ bus['id'] }}-removed:
  file.absent:
    - name: /opt/autopi/obd/can/db/{{ bus['protocol_id'] }}.dbc
{%- endif %}
{%- endfor %}
