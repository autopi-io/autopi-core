
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
    - require:
      - file: /etc/pip-requirements.txt
    - onlyif: diff /etc/pip-requirements.txt /etc/pip-requirements-installed.txt

pip-requirements-installation-logged:
  file.copy:
    - name: /etc/pip-requirements-installed.txt
    - source: /etc/pip-requirements.txt
    - force: true
    - watch:
      - pip: pip-requirements-installed
