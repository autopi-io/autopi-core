# ATTENTION: This checkout flow is only compatible with >=7.0 boards

include:
  - .test

# Force re-flash of SPM firmware
checkout-spm-release-distributed:
  file.managed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.bin
    - source: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.bin
    - source_hash: salt://power/spm/firmware-{{ salt["pillar.get"]("power:firmware:version") }}.bin.sha1
    - makedirs: True
checkout-spm-release-installed:
  spm.firmware_flashed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("power:firmware:version") }}.bin
    - part_id: rp2040
    - version: "{{ salt["pillar.get"]("power:firmware:version") }}"
    - force: True

# SPM voltage calibrate
checkout-spm-voltage-calibrated:
  spm.voltage_calibrated:
    - url: {{ salt['pillar.get']('reference_voltage_url') }}
    - checks: 10
    - retry:
        attempts: 10
        interval: 1
    - require:
      - sls: checkout2.test

# Update
checkout-force-release-updated:
  module.run:
    - name: minionutil.update_release
    - force: true
    - require:
      - sls: checkout2.test

# Restart minion if restart is pending (after running pending SLS or update release)
checkout-restart-minion-if-pending-after-release-updated:
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
checkout-spm-voltage-recalibrated:
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
