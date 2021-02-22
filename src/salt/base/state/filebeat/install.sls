
filebeat-installed:
  pkg.installed:
    - name: filebeat
    - sources:
      - filebeat: http://autopi.io/media/rpi/elastic/filebeat-7.11_armhf.deb

filebeat-scrubber-pip3-requirement-installed:
  pkg.installed:
    - name: python3-pip

filebeat-scrubber-installed:
  cmd.run:
    - name: pip3 install git+git://github.com/autopi-io/filebeat-scrubber@cd3da7250d57e1181648e93c2a9de54455dae6c7#filebeat_scrubber
    - unless: "pip3 show filebeat_scrubber | grep 'Version: 1.3.0'"
    - require:
      - pkg: python3-pip