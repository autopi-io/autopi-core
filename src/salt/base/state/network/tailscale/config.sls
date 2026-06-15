{%- if salt["pillar.get"]("tailscale:enabled", False) %}

tailscale-service-running:
  service.running:
    - name: tailscaled
    - enable: True

tailscale-configured:
  cmd.run:
    - name: "tailscale up --authkey={{ salt['pillar.get']('tailscale:auth_key', '') }} --ssh=false --advertise-tags= --advertise-exit-node=false --advertise-routes= --accept-dns=false --timeout=30s"
    - unless: "tailscale status 2>/dev/null"
    - require:
      - service: tailscaled

{%- else %}

tailscale-service-stopped:
  service.dead:
    - name: tailscaled
    - enable: false

{%- endif %}