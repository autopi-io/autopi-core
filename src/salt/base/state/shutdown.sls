
include:
  - pending  # Will include pending SLS specified in pillar

{%- if salt["pillar.get"]("allow_auto_update", default=True) and salt["pillar.get"]("release:auto_update", default=False) %}
auto-update-release:
  module.run:
    - name: minionutil.update_release
{%- endif %}
