rfid-settings-configured:
  file.serialize:
    - name: /opt/autopi/rfid/settings.yaml
    - makedirs: true
    - dataset_pillar: rfid
    - formatter: yaml
    - show_changes: True

{%- if salt['pillar.get']('rfid') %}
rfid-settings-loaded:
  module.run:
    - name: rfid.load_settings
    - require:
      - file: rfid-settings-configured
{%- endif %}