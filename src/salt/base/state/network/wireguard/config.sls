
{%- if salt["pillar.get"]("wireguard:enabled", default=False) %}

{%- for interface, config in salt["pillar.get"]("wireguard:interfaces", {}).items() %}
wireguard-interface-{{ interface }}-configured:
  file.managed:
    - name: /etc/wireguard/{{ interface }}.conf
    - source: salt://network/wireguard/interface.jinja
    - template: jinja
    - mode: 700
    - context:
        config: {{ config|yaml }}

wireguard-interface-{{ interface }}-service-running:
  service.running:
    - name: wg-quick@{{ interface }}
    - enable: True
    - watch:
      - file: /etc/wireguard/{{ interface }}.conf
{%- endfor %}

{%- else %}

{%- for interface, config in salt["pillar.get"]("wireguard:interfaces", {}).items() %}
{%- if interface %}
wireguard-interface-{{ interface }}-configuration-absent:
  file.absent:
    - name: /etc/wireguard/{{ interface }}.conf

wireguard-interface-{{ interface }}-service-dead:
  service.dead:
    - name: wg-quick@{{ interface }}
    - enable: false
{%- endif %}
{%- endfor %}

{%- endif %}