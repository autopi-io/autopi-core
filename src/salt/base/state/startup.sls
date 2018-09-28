include:
  - ec2x.startup
  - ec2x.gnss.update
#  - acc.config # TODO: Test this
  - power.stn.config

{%- if salt["pillar.get"]("release:auto_update", False) %}
auto-update-release-retried:
  module.run:
    - name: minionutil.update_release
    - only_retry: true
{%- endif %}