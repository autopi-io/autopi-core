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
{%- endif %}

{%- if certificate_mode == 'web3' %}

minion-client-certificate-removed-if-corrupt-or-wrong-common-name:
  file.absent:
    - name: {{ client_cert_path }}
    - unless: openssl x509 -in {{ client_cert_path }} -subject -noout | grep -iF "CN = 0x"

private-key-generated:
  cmd.run:
    - name: |
        if [ ! -f /opt/autopi/client.pem ] || ! openssl ec -in /opt/autopi/client.pem -noout -check; then
            openssl ecparam -name prime256v1 -genkey -noout -out /opt/autopi/client.pem
        fi
    - shell: /bin/bash

private-key-permissions-set:
  file.managed:
    - name: /opt/autopi/client.pem
    - mode: '0644'
    - replace: False
    - onlyif:
      - test -f /opt/autopi/client.pem
      
# This handles situations where the old private key (i.e. token is set instead of web3 for cert_mode setting)
# is still present and was used to generate the certificate
minion-client-certificate-removed-if-wrong-private-key-type:
  file.absent:
    - name: {{ client_cert_path }}
    - unless: 'openssl x509 -in {{ client_cert_path }} -text | grep -iF "Public Key Algorithm: id-ecPublicKey"'

{%- if salt['pillar.get']('state', default='REGISTERED') == 'REGISTERED' %}
# Prevent this from running if device is not minted.
web3-minion-client-certificate-created:
  cert_auth.client_certificate_web3_signed:
    - name: {{ client_cert_path }}
    - oauth_url: {{ salt['pillar.get']('ca:oauth_url', None) }}
    - oauth_client_id: {{ salt['pillar.get']('ca:oauth_client_id', None) }}
    - oauth_client_secret: {{ salt['pillar.get']('ca:oauth_client_secret', None) }}
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - force: {{ salt['pillar.get']('ca:force_overwrite', False) }}
    - require:
      - cmd: private-key-generated
      - file: minion-client-certificate-removed-if-wrong-private-key-type

mosquitto-service-restart-if-exists:
  cmd.run:
    - name: |
        if systemctl --quiet is-enabled mosquitto; then
            systemctl restart mosquitto
        fi
    - shell: /bin/bash
    - watch:
      - cert_auth: web3-minion-client-certificate-created
{%- endif %}

{% elif certificate_mode == 'token' %}

{%- if dashed_minion_id %}
minion-client-certificate-removed-if-corrupt-or-wrong-common-name:
  file.absent:
    - name: {{ client_cert_path }}
    - unless: openssl x509 -in {{ client_cert_path }} -text | grep -iF "CN = {{ dashed_minion_id }}"
{%- endif %}

minion-private-key-copied:
  file.managed:
    - name: /opt/autopi/client.pem
    - source: /etc/salt/pki/minion/minion.pem
    - user: root
    - group: root
    - mode: 644

minion-client-certificate-created:
  cert_auth.client_certificate_signed:
    - name: {{ client_cert_path }}
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - token: {{ salt['pillar.get']('ca:client_certificate_token', None) }}
    - force: {{ salt['pillar.get']('ca:force_overwrite', False) }}
    - require_in:
      - cmd: minion-client-certificate-common-name-verified

minion-client-certificate-common-name-verified:
  cmd.run:
    - name: openssl x509 -in {{ client_cert_path }} -text | grep -iF "CN = {{ dashed_minion_id }}"

mosquitto-service-restart-if-exists:
  cmd.run:
    - name: |
        if systemctl --quiet is-enabled mosquitto; then
            systemctl restart mosquitto
        fi
    - shell: /bin/bash
    - watch:
      - cert_auth: minion-client-certificate-created
{%- endif %}

# Required to signal that SLS 'minion.certs' has run
certs-configured:
  test.succeed_without_changes:
    - comment: {{ certificate_mode }}
