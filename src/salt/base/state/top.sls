
base:
  '*':
    - requirements
    - raspi.config
    - minion.config
    - network.wwan.qmi
    - network.wlan.hotspot.config
    - audio.config
    - redis.server
    - ec2x.config
    - ui
    - power.config  # Highest risk last
