
filebeat-installed:
  pkg.installed:
    - name: filebeat
    - sources:
      - filebeat: http://autopi.io/media/rpi/elastic/filebeat-7.11_armhf.deb
    - unless: test -x /usr/share/filebeat/bin/filebeat && /usr/share/filebeat/bin/filebeat version | grep "filebeat version 7.11.0"

{%- if salt["pillar.get"]("filebeat_scrubber") %}
filebeat-scrubber-pip3-requirement-installed:
  pkg.installed:
    - name: python3-pip
    - unless: which pip3

filebeat-scrubber-installed:
  cmd.run:
    - name: pip3 install git+git://github.com/autopi-io/filebeat-scrubber@9f73fe11ab90f1ff38fadeec667b8ebb8b9411fe#filebeat_scrubber
    - unless: "pip3 show filebeat_scrubber | grep 'Version: 1.3.1'"
    - require:
      - pkg: python3-pip
{%- endif %}