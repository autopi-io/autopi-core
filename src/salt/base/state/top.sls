
base:
  '*':
    - requirements
    - raspi.config
    - minion.config
    - network.wwan.qmi
    - network.wlan
    - audio.config
    - redis.server
    - ec2x.config
    - ui
    - power.spm.install  # Highest risk last
