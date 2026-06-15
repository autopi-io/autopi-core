include:
  {%- if salt["pillar.get"]("tailscale:enabled", False) %}
  - .install
  {%- endif %}
  - .config

# Required to signal that SLS 'network.tailscale.setup' has run
tailscale-setup:
  test.succeed_without_changes:
    - require:
      {%- if salt["pillar.get"]("tailscale:enabled", False) %}
      - sls: network.tailscale.install
      {%- endif %}
      - sls: network.tailscale.config
