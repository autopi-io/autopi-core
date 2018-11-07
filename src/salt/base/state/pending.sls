
{%- set pending_sls = salt["pillar.get"]("minion_ext:pending_sls", default=[]) %}
{%- if pending_sls %}
include:
  {%- for sls in pending_sls %}
  - {{ sls }}
  {%- endfor %}
{%- endif %}