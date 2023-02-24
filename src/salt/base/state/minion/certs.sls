
{%- if salt['pillar.get']('minion_ext:root_cert_bundle', []) %}
minion-root-cert-bundle-created:
  file.managed:
    - name: /opt/autopi/root_cert_bundle.crt
    - contents: |
        {%- for cert in salt['pillar.get']('minion_ext:root_cert_bundle', []) %}
        -----BEGIN CERTIFICATE-----
        {{ cert|replace(" ", "\n        ") }}
        -----END CERTIFICATE-----
        {%- endfor %}
    - user: root
    - group: root
    - mode: 644
{%- endif %}

{%- if salt['pillar.get']('ca:client_certificate_token', None) %}
{%- set dashed_minion_id = salt['config.get']('id') | regex_replace('(\S{8})(\S{4})(\S{4})(\S{4})(.*)', '\\1-\\2-\\3-\\4-\\5', ignorecase=True) %}
minion-client-certificate-removed-if-empty:
  file.absent:
    - name: /opt/autopi/client.crt
    - unless: test -s /opt/autopi/client.crt

minion-client-certificate-removed-if-corrupt-or-wrong-unit_id:
  file.absent:
    - name: /opt/autopi/client.crt
    - unless: openssl x509 -in /opt/autopi/client.crt -text | grep {{ dashed_minion_id }}

minion-client-certificate-created:
  cert_auth.client_certificate_signed:
    - name: /opt/autopi/client.crt
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - token: {{ salt['pillar.get']('ca:client_certificate_token', None) }}
    - force: false

minion-client-certificate-verified:
  cmd.run:
    - name: openssl x509 -in /opt/autopi/client.crt -text | grep {{ dashed_minion_id }}
{%- endif %}

minion-private-key-copied:
  file.managed:
    - name: /opt/autopi/client.pem
    - source: /etc/salt/pki/minion/minion.pem
    - user: root
    - group: root
    - mode: 644
