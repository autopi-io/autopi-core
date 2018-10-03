
avrdude-configured:
  file.managed:
    - name: /etc/avrdude.conf
    - source: salt://power/spm/avrdude.conf

{%- if salt["pillar.get"]("power:firmware:auto_update", default=False) %}
spm-release-distributed:
  file.managed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.hex
    - source: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.hex
    - makedirs: True

spm-release-installed:
  spm.firmware_flashed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.hex
    - version: {{ salt["pillar.get"]("power:firmware:version") }}
{%- endif %}