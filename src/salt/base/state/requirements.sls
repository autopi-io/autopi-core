
packages-installed:
  pkg.installed:
    - pkgs:
      - python-pip
      - python-smbus
      - python-pygame
      - raspi-gpio
      - lighttpd
      - git
      - avrdude
      - espeak

pip-requirements-distributed:
  file.managed:
    - name: /etc/pip-requirements.txt
    - source: salt://requirements.txt

pip-requirements-installed:
  pip.installed:
    - requirements: /etc/pip-requirements.txt
    - upgrade: true  # Needed in order to get newest changes from git repos
    - onchanges:
      - file: /etc/pip-requirements.txt
