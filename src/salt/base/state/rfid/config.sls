
{%- if salt['pillar.get']('rfid:authorized_tokens') %}
rfid-settings-configured:
  file.serialize:
    - name: /opt/autopi/rfid/settings.yaml
    - makedirs: true
    - dataset_pillar: rfid
    - formatter: yaml
    - show_changes: True

rfid-settings-read:
  module.run:
    - name: rfid.read_settings
    - require:
      - file: rfid-settings-configured
{%- endif %}