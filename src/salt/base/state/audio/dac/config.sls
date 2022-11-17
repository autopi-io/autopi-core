
audio-dac-configured:
  file.managed:
    - name: /etc/asound.conf
    - source: salt://audio/dac/asound.conf
