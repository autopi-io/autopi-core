
include:
  - .hotspot

wpa-manager-service-configured:
  file.managed:
    - name: /lib/systemd/system/wpa-manager.service
    - source: salt://network/wlan/wpa-manager.service

wpa-manager-service-running:
  service.running:
    - name: wpa-manager
    - enable: true
    - require:
      - file: /lib/systemd/system/wpa-manager.service
    - watch:
      - file: /lib/systemd/system/wpa-manager.service
