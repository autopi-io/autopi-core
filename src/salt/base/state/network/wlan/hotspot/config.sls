
include:
  - hostapd
  # NOTE: If additional SLS is added here WiFi connection may be down until WPA service is restarted below

# See: https://www.raspberryconnect.com/projects/65-raspberrypi-hotspot-accesspoints/158-raspberry-pi-auto-wifi-hotspot-switch-direct-connection
dns-root-data-package-absent:
  pkg.purged:
    - name: dns-root-data

hostapd-allow-list-configured:
  file.managed:
    - name: /etc/hostapd/hostapd.accept
    - source: salt://network/wlan/hotspot/hostapd.accept.jinja
    - template: jinja
    - watch_in:
      - service: hostapd_service

{%- set _wpa_service = wpa_service|default("wpa-manager") %}
active-{{ _wpa_service }}-restarted-after-hostapd-service:
  service.running:
    - name: {{ _wpa_service }}
    - onlyif: systemctl is-active {{ _wpa_service }}
    - watch:
      - service: hostapd

ensure-online-after-{{ _wpa_service }}-restarted:
  cmd.run:
    - name: ping -q -c1 google.com
    - onchanges:
      - service: {{ _wpa_service }}
    - retry:
        attempts: 20
        interval: 3