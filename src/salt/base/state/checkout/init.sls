include:
  - ec2x.gnss.update
  - checkout.test

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
