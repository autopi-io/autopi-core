
include:
  - .test

# Calibrate
spm-voltage-calibrated:
  spm.voltage_calibrated:
    - url: {{ salt['pillar.get']('reference_voltage_url') }}
    - checks: 10
    - retry:
        attempts: 10
        interval: 1
    - require:
      - sls: checkout2.test

# Update
force-release-updated:
  module.run:
    - name: minionutil.update_release
    - force: true
    - require:
      - sls: checkout2.test

# Restart minion if restart is pending (after running pending SLS or update release)
restart-minion-if-pending-after-release-updated:
  module.run:
    - name: minionutil.request_restart
    - pending: false
    - immediately: true
    - reason: changes_during_checkout

# Re-generate ssh host keys
# This takes around 30 seconds, so that's why we keep it here and not in finalize - we want to keep finalize lean
"rm -v /etc/ssh/ssh_host_*":
  cmd.run
"dpkg-reconfigure openssh-server":
  cmd.run

# Run recalibration
spm-voltage-recalibrated:
  spm.voltage_calibrated:
    - url: {{ salt['pillar.get']('reference_voltage_url') }}
    - checks: 10
    - retry:
        attempts: 10
        interval: 1
    - require:
      - sls: checkout2.test

secure-element-provisioned:
  secure_element.provisioned

assert-clock-synchronized:
  test.module:
    - name: clock.status
    - validate:
      - ret["ntp_service"] == "active"
      - ret["system_clock_synchronized"] == "yes"
