
minion-client-certificate-created:
  cert_auth.client_certificate_signed:
    - name: /opt/autopi/client.crt
    - ca_url: {{ salt['pillar.get']('ca:url', None) }}
    - ca_fingerprint: {{ salt['pillar.get']('ca:fingerprint', None) }}
    - token: {{ salt['pillar.get']('ca:client_certificate_token', None) }}
    - force: false

minion-private-key-copied:
  file.managed:
    - name: /opt/autopi/client.pem
    - source: /etc/salt/pki/minion/minion.pem
    - user: root
    - group: root
    - mode: 644
