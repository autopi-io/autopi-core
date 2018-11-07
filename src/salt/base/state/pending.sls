
include:
  {%- for sls in salt["pillar.get"]("minion_ext:pending_sls", default=[]) %}
  - {{ sls }}
  {%- endfor %}
