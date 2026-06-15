# Ensure apt keyring is readable
include:
  - apt.keyring.readable

# Set environment variables
{% for key, val in salt["pillar.get"]("envvar_requirements", {}).iteritems() %}
requirements-envvar-{{ loop.index0 }}:
   environ.setenv:
     - name: {{ key }}
     - value: "{{ val }}"
     - update_minion: True
{% endfor %}

salt-source-repo-file-removed:
  file.absent:
    - name: /etc/apt/sources.list.d/saltstack.list

{%- if salt["grains.get"]("osmajorrelease") == 9 %}
update_raspbian_stretch_sources_list:
  cmd.run:
    - name: 'sed -i.bak "s|http://raspbian.raspberrypi.org/raspbian/|http://legacy.raspbian.org/raspbian/|" /etc/apt/sources.list'
    - onlyif: 'grep -q "http://raspbian.raspberrypi.org/raspbian/" /etc/apt/sources.list'
{%- endif %}

{%- if salt['grains.get']('osmajorrelease') == 10 %}
update_raspbian_buster_sources_list:
  pkgrepo.managed:
    - name: deb http://legacy.raspbian.org/raspbian buster main contrib non-free rpi
    - file: /etc/apt/sources.list
    - refresh: false

remove_archive_rapbian_sources_list:
  pkgrepo.absent:
    - name: deb http://archive.raspbian.org/raspbian buster main contrib non-free rpi
    - file: /etc/apt/sources.list
    - refresh: false

expired-backports-repo-removed:
  pkgrepo.absent:
    - name: deb http://deb.debian.org/debian buster-backports main
    - refresh: false
{%- endif %}

pending-packages-configured:
  cmd.run:
    - name: "dpkg --configure -a"

packages-installed:
  pkg.installed:
    {%- if salt["pillar.get"]("state", default="REGISTERED") == "NEW" %}
    - refresh: true
    {%- endif %}
    - pkgs:
      {%- if salt['grains.get']('osmajorrelease') < 11 %}
      - python-pip
      - python-smbus
      - python-pygame
      {%- else %}
      - openocd
      {%- endif %}
      - raspi-gpio
      - lighttpd
      - git
      - avrdude
      - espeak
      {%- if salt['pillar.get']('pkg_requirements') %}
      {%- for entry in salt['pillar.get']('pkg_requirements', []) %}
      - {{ entry }}
      {%- endfor %}
      {%- endif %}

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
