
include:
  - pending  # Will include pending SLS specified in pillar

{%- if salt["pillar.get"]("allow_auto_update", default=True) %}
{%- if salt["pillar.get"]("update_release:automatic", default=False) %}
auto-update-release:
  module.run:
    - name: minionutil.update_release
{%- elif salt["pillar.get"]("update_release:demand", default=False) %}
demand-update-release:
  module.run:
    - name: minionutil.update_release
{%- endif %}
{%- endif %}
