
{%- for key, val in (salt["pillar.get"]("grains", {}) or {}).iteritems() %}
minion-grains-{{ loop.index }}-managed:
  {%- if val %}
  grains.present:
    - value: {{ val|tojson }}
  {%- else %}
  grains.absent:
    - destructive: true
  {%- endif %} 
    - name: {{ key }}
    - delimiter: "\\."
    - force: true
    - watch_in:
      - module: minion-grains-refreshed
{%- endfor %}

minion-grains-refreshed:
  module.wait:
    - name: saltutil.refresh_grains
    - refresh_pillar: false