
{%- if salt["pillar.get"]("minion:secure_element") == 'nxp05x' %}

packages_installed:
  pkg.installed:
    - name: libffi-dev

sss_dir_downloaded:
  file.recurse:
    - name: /opt/autopi/se05x_sss
    - source: salt://secure_element/se05x_sss

sss_base_files_copied:
  cmd.run:
    - name: "cp -f /opt/autopi/se05x_sss/lib_051/* /usr/local/lib"
    - require:
      - file: sss_dir_downloaded

sss_base_files_loaded:
  cmd.run:
    - name: ldconfig /usr/local/lib
    - require:
      - cmd: sss_base_files_copied

pip_requirements_installed:
  pip.installed:
    - editable: /opt/autopi/se05x_sss
    - require:
      - pkg: packages_installed
      - file: sss_dir_downloaded

{%- if salt["pillar.get"]("minion:hw.version") >= 7.0 %}
sss_050_build_loaded:
  cmd.run:
    - name: "cp -f /opt/autopi/se05x_sss/lib_050/* /usr/local/lib && ldconfig /usr/local/lib"
    - unless: "ssscli se05x uid | egrep 'Unique ID: [a-fA-F0-9]{36}'"
    - require:
      - pip: pip_requirements_installed
{%- endif %}

{%- elif salt["pillar.get"]("minion:secure_element") == 'softhsm' %}
dimo-edge-identity-downloaded:
  file.managed:
    - name: /opt/autopi/edge-identity_release.tar.gz
    - source: https://github.com/DIMO-Network/edge-identity/releases/download/v0.1.3/edge-identity-v0.1.3-linux-arm.tar.gz
    - source_hash: https://github.com/DIMO-Network/edge-identity/releases/download/v0.1.3/edge-identity-v0.1.3-linux-arm.tar.gz.md5

dimo-edge-identity-extracted:
  archive.extracted:
    - name: /opt/autopi/bin/edge-identity
    - source: /opt/autopi/edge-identity_release.tar.gz
    - keep_source: false
    - clean: true
    - enforce_toplevel: false
    - overwrite: true
    - require:
      - file: dimo-edge-identity-downloaded
    - onchanges:
      - file: dimo-edge-identity-downloaded

dimo-identity-made-executable:
  file.managed:
    - name: /opt/autopi/bin/edge-identity/edge-identity
    - replace: true
    - user: root
    - group: root
    - mode: 555
    - onchanges:
      - archive: dimo-edge-identity-extracted

dimo-identity-linked:
  file.symlink:
    - name: /usr/local/bin/edge-identity
    - target: /opt/autopi/bin/edge-identity/edge-identity
    - force: true
    - require:
      - archive: dimo-edge-identity-extracted
    - onchanges:
      - archive: dimo-edge-identity-extracted

{%- endif %}