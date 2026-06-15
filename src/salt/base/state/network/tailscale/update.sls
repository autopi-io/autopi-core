
tailscale-updated:
  cmd.run:
    - name: curl -fsSL https://tailscale.com/install.sh | sh
    - onlyif: "tailscale version"