
tailscale-installed:
  cmd.run:
    - name: curl -fsSL https://tailscale.com/install.sh | sh
    - unless: "tailscale version"

tailscale-flags-ensure:
  file.replace:
    - name: /etc/default/tailscaled
    - pattern: '^\s*FLAGS="([^"]*)"\s*$'
    - repl: 'FLAGS="\1 --no-logs-no-support"'
    - append_if_not_found: True
    - not_found_content: 'FLAGS="--no-logs-no-support"'
    - flags:
      - MULTILINE
    - unless: |
        grep -Eq '^\s*FLAGS="[^"]*--no-logs-no-support[^"]*"' /etc/default/tailscaled

tailscaled-service:
  service.running:
    - name: tailscaled
    - enable: True
    - watch:
      - file: tailscale-flags-ensure