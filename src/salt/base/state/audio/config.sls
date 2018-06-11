
include:
  - .dac.config

power-on-sound-distributed:
  file.managed:
    - name: /opt/autopi/audio/power_on.wav
    - source: salt://audio/power_on.wav
    - makedirs: True
