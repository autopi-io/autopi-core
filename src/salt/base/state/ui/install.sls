{%- set frontend_version = "2021-09-21.mtu-fix" %}
{%- set frontend_hash    = "3a17f59366a2dd3c81e0bbe5eb6771a75481f09f" %}

frontend-release-extracted:
  archive.extracted:
    - name: /opt/autopi/frontend/{{ frontend_version }}/
    - source: https://autopi-repo.s3.eu-west-2.amazonaws.com/frontend/release_{{ frontend_version }}.zip
    - source_hash: {{ frontend_hash }}
    - archive_format: zip
    - keep_source: true
    - clean: true

frontend-release-linked:
  file.symlink:
    - name: /var/www/html
    - target: /opt/autopi/frontend/{{ frontend_version }}/dist
    - force: true
    - require:
      - archive: frontend-release-extracted

frontend-env-file-created:
  file.managed:
    - name: /var/www/html/env.js
    - source: salt://ui/env.js.jinja
    - template: jinja
    - require:
      - file: frontend-release-linked
