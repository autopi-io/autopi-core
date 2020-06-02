
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

# Force update release
force-release-updated:
  module.run:
    - name: minionutil.update_release
    - force: true

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

# Delete 'pi' user files
/home/pi/.*_history:
  file.absent
/home/pi/.nano:
  file.absent

# Delete 'root' user files
/root/.*_history:
  file.absent
/root/.nano/:
  file.absent

# Flush all Redis data 
redis-flushed:
  module.run:
    - name: redis.flushall
    - host: localhost
    - port: 6379
    - db: 0

# Delete archived logs
"find /var/log -type f -name '*.[0-99].gz' -exec rm {} +":
  cmd.run

# Truncate log files
"truncate -s 0 /var/log/*.log":  # First level
  cmd.run
"truncate -s 0 /var/log/**/*.log":  # Nested folders
  cmd.run
"truncate -s 0 /var/log/salt/*":  # Salt
  cmd.run

audio-checkout-done:
  module.run:
    - name: audio.play
    - audio_file: /opt/autopi/audio/sound/notification.wav
