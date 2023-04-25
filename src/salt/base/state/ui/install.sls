{%- set frontend_version = "2021-09-21" %}
{%- set frontend_hash    = "4e2a6833f2fdd3672441583e7cd956d174343c9d" %}

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
