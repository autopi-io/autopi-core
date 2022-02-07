
avrdude-configured:
  file.managed:
    - name: /etc/avrdude.conf
    - source: salt://power/spm/avrdude.conf

{%- if salt["pillar.get"]("power:firmware:auto_update", default=False) %}
spm-release-distributed:
  file.managed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.hex
    - source: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.hex
    - source_hash: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.hex.sha1
    - makedirs: True

spm-release-installed:
  spm.firmware_flashed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.hex
    {%- if salt["pillar.get"]("power:firmware:version").startswith("1.") %}
    - part_id: t24
    {%- else %}
    - part_id: t88
    {%- endif %}
    - version: "{{ salt["pillar.get"]("power:firmware:version") }}"
{%- endif %}

{%- if salt["pillar.get"]("power:firmware:version")|float >= 3.0 %}
spm-bod-fuse-configured:
  module_extra.configured:
    - name: avrdude.fuse
    - args:
      - h
    - kwargs:
        value: "0xdd"
{%- endif %}
