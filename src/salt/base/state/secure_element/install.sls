
{%- if salt["pillar.get"]("minion:hw.version") > 6.1 %} # Se05x version

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