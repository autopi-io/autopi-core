
finalize-spm-amp-enabled:
  test.module:
    - name: spm.query
    - args:
      - sys_pins
    - kwargs:
        high: sw_amp
    - validate: ret["output"]["sw_amp"]

finalize-audio-test:
  module.run:
    - name: audio.play
    - audio_file: /opt/autopi/audio/sound/beep.wav
    - require:
      - test: finalize-spm-amp-enabled

# Clean up wifi
wpa_supplicant:networks:
  grains.present:
    - value: null
    - force: true

/etc/wpa_supplicant/wpa_supplicant.conf:
  file.absent

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

