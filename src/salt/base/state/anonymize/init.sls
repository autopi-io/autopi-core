# Delete 'pi' user files
/home/pi/.*_history:
  file.absent
/home/pi/.nano:
  file.absent

# Delete 'root' user files
/root/.*_history:
  file.absent
/root/.nano:
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

# Flush all ssh keys
"rm -v /etc/ssh/ssh_host_*":
  cmd.run

# Truncate log files
"truncate -s 0 /var/log/*.log":  # First level
  cmd.run
"truncate -s 0 /var/log/**/*.log":  # Nested folders
  cmd.run
"truncate -s 0 /var/log/syslog":  # syslog
  cmd.run
"truncate -s 0 /var/log/messages":  # messages
  cmd.run
"truncate -s 0 /var/log/salt/*":  # Salt
  cmd.run

# reset hosts entry
hosts-file-reset:
  host.only:
    - name: 127.0.1.1
    - hostnames:
      - autopi-initial

# reset hostname
"echo 'autopi-initial' > /etc/hostname":
  cmd.run

set-passphrase-to-default:
  file.replace:
    - name: "/etc/hostapd/hostapd_uap0.conf"
    - pattern: "wpa_passphrase=.*"
    - repl: "wpa_passphrase=autopi2018"
  
set-ssid-to-initial:
  file.replace:
    - name: "/etc/hostapd/hostapd_uap0.conf"
    - pattern: "ssid=.*"
    - repl: "ssid=AutoPi-Initial"

regenerate-ssh-host-keys-configured:
  file.managed:
    - name: /lib/systemd/system/regenerate-ssh-host-keys.service
    - source: salt://anonymize/reconfigure-ssh-host-keys.service
    - mode: 777
    - user: root
    - group: root

regenerate-ssh-host-keys-enabled:
  service.enabled:
    - name: regenerate-ssh-host-keys
    - enable: true
    - require:
      - file: /lib/systemd/system/regenerate-ssh-host-keys.service

# Delete Salt files
/etc/salt/pki/minion/:
  file.absent
/etc/salt/minion_id:
  file.absent
# This is commented out because clearing grains will also make it forget which version it is currently running.
# /etc/salt/grains:
#   file.absent
/etc/salt/minion.d/:
  file.absent
# /var/cache/salt/minion/:
#   file.absent

salt-minion:
  service.dead