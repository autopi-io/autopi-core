
gnss-assist-enabled:
  ec2x.gnss_assist_enabled

gnss-auto-start-enabled:
  ec2x.gnss_auto_start:
    - enable: {{ salt['pillar.get']('ec2x:gnss:auto_start') }}

gnss-nmea-port-configured:
  module_extra.configured:
    - name: ec2x.gnss_nmea_port
    - kwargs:
        value: {{ salt['pillar.get']('ec2x:gnss:nmea_port') }}

gnss-nmea-gps-output-configured:
  module_extra.configured:
    - name: ec2x.gnss_nmea_output_gps
    - kwargs:
        value: 31

{%- if salt['pillar.get']('ec2x:gnss:fix_frequency') %}
gnss-fix-frequency-configured:
  ec2x.gnss_set_fix_frequency:
    - value: {{ salt['pillar.get']('ec2x:gnss:fix_frequency') }}
{%- endif %}
