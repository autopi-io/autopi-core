salt-common-configured:
  file.managed:
    - name: /etc/logrotate.d/salt-common
    - source: salt://logrotate/salt-common.jinja
    - template: jinja

rsyslog-configured:
  file.managed:
    - name: /etc/logrotate.d/rsyslog
    - source: salt://logrotate/rsyslog.jinja
    - template: jinja

logrotate-timer-configured:
  file.managed:
    - name: /etc/systemd/system/logrotate.timer
    - source: salt://logrotate/logrotate.timer.jinja
    - template: jinja

systemd-reload:
  cmd.run:
   - name: systemctl --system daemon-reload 
   - onchanges:  
     - file: logrotate-timer-configured
