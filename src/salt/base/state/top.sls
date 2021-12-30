
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
    - network.wlan.client.config
    - network.wlan.hotspot.install
    - network.firewall.config
    - obd.install
    - audio.install
    - redis.server
    - mosquitto
    {%- if salt["pillar.get"]("docker:enabled", default=False) %}
    - docker.install
    {%- else %}
    - docker.uninstall
    {%- endif %}
    {%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") in ["ec2x", "bg96"] %}
    - ec2x.config
    {%- endif %}
    {%- if salt["pillar.get"]("ble:enabled", default=False) %}
    - ble.install
    {%- endif %}
    - ui.install
    - power.sleep_timer.config
    - power.spm.install
    - power.config