
gnss-off-before-assist-data-reset:
  ec2x.gnss_off:
    - prereq:
      - ec2x: gnss-assist-data-reset

gnss-assist-data-reset:
  ec2x.gnss_assist_data_reset:
    - type: 0

gnss-on:
  ec2x.gnss_on