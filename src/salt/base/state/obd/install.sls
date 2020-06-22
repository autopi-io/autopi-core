
stn-dump-installed:
  file.managed:
    - name: /usr/bin/stn-dump
    - source: salt://obd/stn-dump
    - source_hash: salt://obd/stn-dump.sha1
    - mode: 755
    - user: root
    - group: root
