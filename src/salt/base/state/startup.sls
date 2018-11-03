
# IMPORTANT: These stats will only run when minion comes online and is connected to master 

include:
  {%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") == "ec2x" %}
  - ec2x.startup
  - ec2x.gnss.update
  {%- endif %}
#  - acc.config # TODO: Test this
  - power.stn.config

{%- if salt["pillar.get"]("release:auto_update", default=False) %}
auto-update-release-retried:
  module.run:
    - name: minionutil.update_release
    - only_retry: true

# Restart minion if restart is pending after update
restart-minion-if-pending:
  module.run:
    - name: minionutil.request_restart
    - pending: false
    - immediately: true
    - reason: auto_update_release_retried 
{%- endif %}
