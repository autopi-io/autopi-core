
include:
  {%- if salt["pillar.get"]("docker:enabled", default=False) %}
  - .install
  {%- else %}
  - .uninstall
  {%- endif %}

# Required to signal that SLS 'docker.setup' has run
docker-setup:
  test.succeed_without_changes:
    - require:
      {%- if salt["pillar.get"]("docker:enabled", default=False) %}
      - sls: docker.install
      {%- else %}
      - sls: docker.uninstall
      {%- endif %}