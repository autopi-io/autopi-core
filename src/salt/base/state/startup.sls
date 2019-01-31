
#
# IMPORTANT: These states will only run when minion comes online and is connected to master 
#

include:
  {%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") in ["ec2x", "bg96"] %}
  - ec2x.startup
  - ec2x.gnss.update
  {%- endif %}
  - pending  # Will include pending SLS specified in pillar

# Run startup modules defined in pillar
{%- for module in salt["pillar.get"]("minion_ext:startup_modules", default=[]) %}
startup-module-{{loop.index}}-executed:
  module.run:
    {%- for key, val in module.iteritems() %}
    - {{ key }}: {{ val|tojson }}
    {%- endfor %}
{%- endfor %}

# Retry update of release if failed or pending, but only if auto update is enabled
{%- if salt["pillar.get"]("release:auto_update", default=False) %}
auto-update-release-retried:
  module.run:
    - name: minionutil.update_release
    - only_retry: true
{%- endif %}

# Restart minion if restart is pending (after running pending SLS or update release)
restart-minion-if-pending:
  module.run:
    - name: minionutil.request_restart
    - pending: false
    - immediately: true
    - reason: changes_made_during_startup
