client-cert-created:
  cert_auth.client_certificate_signed:
    - name: /opt/autopi/client.crt
    - ca_url: https://device-root.autopi.ca.smallstep.com
    - ca_fingerprint: e4a1ca5b6dc6055fea9bfcd414158cbe0992141a0516c2dfb3aea220324cebb7
    - token: {{ salt['pillar.get']('client_certificate_token', None) }}
    - force: false