
# Below configurations are reset each time modem restarts

# TODO: Move move this to engine and run on start to make more efficient?

error-format-configured:
  module_extra.configured:
    - name: ec2x.error_format_config
    - kwargs:
        value: {{ salt['pillar.get']('ec2x:error_format') }}

# TODO: This fails when no SIM card is present
#sms-format-configured:
#  module_extra.configured:
#    - name: ec2x.sms_format_config
#    - kwargs:
#        value: 1  # Text mode