
salt-source-repo-file-removed:
  file.absent:
    - name: /etc/apt/sources.list.d/saltstack.list

pending-packages-configured:
  cmd.run:
    - name: "dpkg --configure -a"

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
      {%- for entry in salt['pillar.get']('pkg_requirements', []) %}
      - {{ entry }}
      {%- endfor %}

# Ensure valid pillar data is present to prevent writing an empty requirements file 
pip-requirements-pillar-data-present:
  module.run:
    - name: pillar.keys
    - key: minion
    - prereq:
      - file: pip-requirements-distributed

pip-requirements-distributed:
  file.managed:
    - name: /etc/pip-requirements.txt
    - source: salt://requirements.txt.jinja
    - template: jinja

pip-requirements-installed:
  pip.installed:
    - requirements: /etc/pip-requirements.txt
    - upgrade: true  # Needed in order to get newest changes from git repos
    - require:
      - file: /etc/pip-requirements.txt
    - unless: diff /etc/pip-requirements.txt /etc/pip-requirements-installed.txt

pip-requirements-installation-completed:
  file.managed:
    - name: /etc/pip-requirements-installed.txt
    - source: /etc/pip-requirements.txt
    - watch:
      - pip: pip-requirements-installed

minion-restart-after-pip-requirements-installed:
  module.wait:
    - name: minionutil.request_restart
    - reason: pip_requirements_installed
    - watch:
      - pip: pip-requirements-installed
