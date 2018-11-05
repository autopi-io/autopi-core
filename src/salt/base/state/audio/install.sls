
include:
  - .dac.config

sounds-distributed:
  file.recurse:
    - name: /opt/autopi/audio
    - source: salt://audio/sounds
    - clean: True
