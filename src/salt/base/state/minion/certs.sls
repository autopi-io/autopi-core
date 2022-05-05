
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
minion-client-certificate-created:
  cert_auth.client_certificate_signed:
    - name: /opt/autopi/client.crt
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - token: {{ salt['pillar.get']('ca:client_certificate_token', None) }}
    - force: false
{%- endif %}

minion-private-key-copied:
  file.managed:
    - name: /opt/autopi/client.pem
    - source: /etc/salt/pki/minion/minion.pem
    - user: root
    - group: root
    - mode: 644
