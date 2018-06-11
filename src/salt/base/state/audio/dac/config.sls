/etc/asound.conf:
  file.managed:
    - source: salt://audio/dac/asound.conf
    - onchanges_in:
      - cmd: reboot-required

# TODO: Use file.replace instead, see state: obd.config
default-audio-uncommented:
  file.line:
    - name: /boot/config.txt
    - content: '#dtparam=audio=on'
    - match: 'dtparam=audio=on'
    - mode: replace
    - onchanges_in:
      - cmd: reboot-required

# TODO: Use file.replace instead, see state: obd.config
hifiberry-device-tree-entry-added:
  file.line:
    - name: /boot/config.txt
    - content: 'dtoverlay=hifiberry-dac'
    - after: '#dtparam=audio=on'
    - mode: ensure
    - require:
      - file: default-audio-uncommented
    - onchanges_in:
      - cmd: reboot-required

# TODO: Use file.replace instead, see state: obd.config
i2s-device-tree-entry-added:
  file.line:
    - name: /boot/config.txt
    - content: 'dtoverlay=i2s-mmap'
    - after: 'dtoverlay=hifiberry-dac'
    - mode: ensure
    - require:
      - file: hifiberry-device-tree-entry-added
    - onchanges_in:
      - cmd: reboot-required

reboot-required:
  cmd.run:
    - name: 'echo IMPORTANT: Reboot required due to audio config changes!'
#  module.run:
#    - name: system.reboot
