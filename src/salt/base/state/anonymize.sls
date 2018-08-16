
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

# Flush all Redis data 
redis-flushed:
  module.run:
    - name: redis.flushall
    - host: localhost
    - port: 6379
    - db: 0

# Flush all ssh keys, maybe remove this, as the regenerate-ssh-host-keys will do this once on next start.
"rm -v /etc/ssh/ssh_host_*":
  cmd.run

# Delete Salt files
/etc/salt/pki/minion/:
  file.absent
/etc/salt/minion_id:
  file.absent
/etc/salt/grains:
  file.absent
/etc/salt/minion.d/:
  file.absent
/var/cache/salt/minion/:
  file.absent

# Truncate log files
"truncate -s 0 /var/log/*.log":  # First level
  cmd.run
"truncate -s 0 /var/log/**/*.log":  # Nested folders
  cmd.run
"truncate -s 0 /var/log/salt/*":  # Salt
  cmd.run

salt-minion:
  service.dead

set-passphrase-to-default:
  file.replace:
    name: "/etc/hostapd/hostapd_wlan0.conf"
    - pattern: "wpa_passphrase=.*"
    - repl: "wpa_passphrase=autopi2018"
  
set-ssid-to-initial:
  file.replace:
    - name: "/etc/hostapd/hostapd_wlan0.conf"
    - pattern: "ssid=.*"
    - repl: "ssid=AutoPi-Initial"

regenerate-ssh-host-keys-configured:
  file.managed:
    - name: /lib/systemd/system/regenerate-ssh-host-keys.service
    - source: salt://reconfigure-ssh-host-keys.service
    - mode: 777
    - user: root
    - group: root

regenerate-ssh-host-keys-enabled:
  service.enabled:
    - name: regenerate-ssh-host-keys
    - enable: true
    - require:
      - file: /lib/systemd/system/regenerate-ssh-host-keys.service