
{%- if salt["pillar.get"]("power:firmware:version").startswith("1.") %}
{% set file_ext = "hex" -%}
{% set part_id = "t24" -%}
{%- elif salt["pillar.get"]("power:firmware:version")|float < 4.0 %}
{% set file_ext = "hex" -%}
{% set part_id = "t88" -%}
{%- else %}
{% set file_ext = "elf" -%}
{% set part_id = "rp2040" -%}
{%- endif %}

{%- if part_id == "rp2040" %}
openocd-interface-raspberrypi-swd-configured:
  file.managed:
    - name: /usr/local/share/openocd/scripts/interface/raspberrypi-swd.cfg
    - source: salt://power/spm/openocd/raspberrypi-swd.cfg

openocd-target-rp2040-configured:
  file.managed:
    - name: /usr/local/share/openocd/scripts/target/rp2040.cfg
    - source: salt://power/spm/openocd/rp2040.cfg
{%- else %}
avrdude-configured:
  file.managed:
    - name: /etc/avrdude.conf
    - source: salt://power/spm/avrdude.conf
{%- endif %}

{%- if salt["pillar.get"]("power:firmware:auto_update", default=False) %}
spm-release-distributed:
  file.managed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.{{ file_ext }}
    - source: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.{{ file_ext }}
    - source_hash: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.{{ file_ext }}.sha1
    - makedirs: True

spm-release-installed:
  spm.firmware_flashed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.{{ file_ext }}
    - part_id: {{ part_id }}
    - version: "{{ salt["pillar.get"]("power:firmware:version") }}"

{%- if not salt["pillar.get"]("power:firmware:version").startswith("1.") and 3.0 <= salt["pillar.get"]("power:firmware:version")|float < 4.0 %}
spm-bod-fuse-configured:
  module_extra.configured:
    - name: spm.fuse
    - args:
      - h
      - t88
    - kwargs:
        value: "0xde"
        confirm: true
{%- endif %}
{%- endif %}
