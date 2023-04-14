{%- set client_cert_path = salt['pillar.get']('ca:client_cert_path', "/opt/autopi/client.crt") %}
{%- set certificate_mode = salt['pillar.get']('ca:certificate_mode', None) %}
{%- set dashed_minion_id = salt['config.get']('id') | regex_replace('(\S{8})(\S{4})(\S{4})(\S{4})(.*)', '\\1-\\2-\\3-\\4-\\5', ignorecase=True) %}

{%- if certificate_mode %}
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

minion-client-certificate-removed-if-empty:
  file.absent:
    - name: {{ client_cert_path }}
    - unless: test -s {{ client_cert_path }}

minion-client-certificate-removed-if-corrupt-or-wrong-unit_id:
  file.absent:
    - name: {{ client_cert_path }}
    - unless: openssl x509 -in {{ client_cert_path }} -text | grep -iF {{ dashed_minion_id }}
{%- endif %}

{%- if certificate_mode == 'web3' %}
{%- set eth_address = salt['crypto.query']('ethereum_address') %}

web3-minion-client-certificate-created:
  cert_auth.client_certificate_web3_signed:
    - name: {{ client_cert_path }}
    - oauth_url: {{ salt['pillar.get']('ca:oauth_url', None) }}
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - force: false
    - require_in:
      - file: minion-private-key-copied
      - cmd: minion-client-certificate-verified

{% elif certificate_mode == 'token' %}

minion-client-certificate-created:
  cert_auth.client_certificate_signed:
    - name: {{ client_cert_path }}
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - token: {{ salt['pillar.get']('ca:client_certificate_token', None) }}
    - force: false
    - require_in:
      - file: minion-private-key-copied
      - cmd: minion-client-certificate-verified

{%- endif %}

{%- if certificate_mode %}
minion-client-certificate-verified:
  cmd.run:
    - name: openssl x509 -in {{ client_cert_path }} -text | grep -F {{ dashed_minion_id }}

minion-private-key-copied:
  file.managed:
    - name: /opt/autopi/client.pem
    - source: /etc/salt/pki/minion/minion.pem
    - user: root
    - group: root
    - mode: 644
{%- endif %}

# Required to signal that SLS 'minion.certs' has run
certs-configured:
  test.succeed_without_changes:
    - comment: {{ certificate_mode }}