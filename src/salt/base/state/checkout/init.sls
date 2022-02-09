
include:
  - .test

# Calibrate STN voltage
stn-voltage-calibrated:
  stn.voltage_calibrated:
    - url: {{ salt['pillar.get']('reference_voltage_url') }}
    - samples: 20
    - retry:
        attempts: 10
        interval: 1

spm-bod-fuse-configured:
  module_extra.configured:
    - name: spm.fuse
    - args:
      - h
      - t88
    - kwargs:
        value: "0xdd"
        confirm: true

# Force update release
force-release-updated:
  module.run:
    - name: minionutil.update_release
    - force: true
    - require:
      - sls: checkout.test

# Restart minion if restart is pending (after running pending SLS or update release)
restart-minion-if-pending-after-release-updated:
  module.run:
    - name: minionutil.request_restart
    - pending: false
    - immediately: true
    - reason: changes_during_checkout

states-locally-cached:
  module.run:
    - name: cp.cache_dir
    - path: salt://checkout

# Re-generate ssh host keys
"rm -v /etc/ssh/ssh_host_*":
  cmd.run
"dpkg-reconfigure openssh-server":
  cmd.run

audio-checkout-done:
  module.run:
    - name: audio.play
    - audio_file: /opt/autopi/audio/sound/notification.wav
