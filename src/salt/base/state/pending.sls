
{%- set pending_sls = salt["pillar.get"]("minion_ext:pending_sls", default=[]) %}
{%- if pending_sls %}
include:
  {%- for sls in pending_sls %}
  - {{ sls }}
  {%- endfor %}
{%- endif %}

{%- set max_pending_sync = salt["pillar.get"]("minion_ext:max_pending_sync", default=0) %}
{%- if max_pending_sync %}
max-pending-sync:
  test.succeed_without_changes:
    - comment: {{ max_pending_sync }}
{%- endif %}