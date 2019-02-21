
base:
  '*':
    - requirements  # Most important
    - raspi.install
    - minion.install
{%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") == "ec2x" %}
    - network.wwan.qmi.install
{%- else %}
    - network.wwan.qmi.uninstall
{%- endif %}
    - network.wlan.hotspot.install
    - network.wlan.client.config
    - audio.install
    - redis.server
{%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") in ["ec2x", "bg96"] %}
    - ec2x.config
{%- endif %}
    - ui.install
    - power.stn.config
    - power.spm.install  # Highest risk last
