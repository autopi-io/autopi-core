
gnss-off-before-assist-data-updated:
  ec2x.gnss_off:
    - prereq:
      - ec2x: gnss-assist-data-valid

gnss-assist-data-valid:
  ec2x.gnss_assist_data_valid:
    - name: {{ salt['pillar.get']('ec2x:gnss:assist:data_urls')|random }}
    - valid_mins: {{ salt['pillar.get']('ec2x:gnss:assist:data_valid_mins') }}

gnss-on:
  ec2x.gnss_on
