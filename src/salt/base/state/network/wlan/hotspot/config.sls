
include:
  - hostapd
  - network.firewall.config

{%- set _wpa_service = wpa_service|default("wpa-manager") %}
active-{{ _wpa_service }}-restarted-after-hostapd-service:
  service.running:
    - name: {{ _wpa_service }}
    - onlyif: systemctl is-active {{ _wpa_service }}
    - watch:
      - service: hostapd
