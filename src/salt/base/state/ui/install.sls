{%- set frontend_version = "develop" %}
{%- set frontend_hash    = "645fe43b1a4fd84063a8a01b67a8e4d44f3aa219" %}

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
