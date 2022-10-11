
# Only applicable to spm 3.0+

power-status-test:
  test.module:
    - name: power.status
    - validate:
      - '"rpi" in ret'
      - '"spm" in ret'
      - ret["spm"]["last_state"]["up"] == "on"
      - ret["spm"]["last_trigger"]["up"] == "plug"

