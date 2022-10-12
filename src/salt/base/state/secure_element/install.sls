
{%- if salt["pillar.get"]("minion:secure_element") == 'nxp05x' %}

packages_installed:
  pkg.installed:
    - name: libffi-dev

sss_dir_downloaded:
  file.recurse:
    - name: /opt/autopi/se05x_sss
    - source: salt://secure_element/se05x_sss

pip_requirements_installed:
  pip.installed:
    - editable: /opt/autopi/se05x_sss
    - require:
      - pkg: packages_installed
      - file: sss_dir_downloaded

{%- endif %}

{%- if salt["pillar.get"]("minion:secure_element") == 'softhsm' %}

edge-identity-extracted:
  archive.extracted:
    - name: /opt/autopi/bin/edge-identity/
    - source: https://github.com/DIMO-Network/edge-identity/releases/download/v0.1.2/edge-identity-v0.1.2-linux-amd64.tar.gz
    - source_hash: https://github.com/DIMO-Network/edge-identity/releases/download/v0.1.2/edge-identity-v0.1.2-linux-amd64.tar.gz.md5
    - keep_source: true
    - clean: true

edge-identity-made-executable:
  file.managed:
    - name: /user/bin/edge-identity
    - replace: true
    - user: root
    - group: root
    - mode: 555

edge-identity-linked:
  file.symlink:
    - name: /user/bin/edge-identity
    - target: /opt/autopi/bin/edge-identity/edge-identity
    - force: true
    - require:
      - archive: edge-identity-extracted

{%- endif %}