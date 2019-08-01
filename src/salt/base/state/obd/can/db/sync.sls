
{%- for bus in salt['pillar.get']('obd:buses', default=[]) %}
{%- if bus.get('has_can_msgs', False) %}
obd-bus-{{ bus['id'] }}-can-db-synced:
  file.managed:
    - name: /opt/autopi/obd/can/db/protocol_{{ bus['protocol_id'] }}.dbc
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/obd/bus/{{ bus['id'] }}/can/db?format=dbc
    - source_hash: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/{{ salt['grains.get']('id') }}/obd/bus/{{ bus['id'] }}/can/db?format=sha1sum
    - makedirs: true
{%- else %}
obd-bus-{{ bus['id'] }}-can-db-removed:
  file.absent:
    - name: /opt/autopi/obd/can/db/protocol_{{ bus['protocol_id'] }}.dbc
{%- endif %}
{%- endfor %}
