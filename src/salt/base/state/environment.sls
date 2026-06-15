
{%- for env_var in salt["pillar.get"]("env_vars", []) %}
{%- for target_file in env_var.get("target_files", []) %}
{%- if env_var.get("enabled", True) %}
environment-variable-{{ env_var["name"] }}-present-in-{{ target_file }}:
  file.replace:
    - name: {{ target_file }}
    - pattern: "^#?export {{ env_var["name"] }}=.*$"
    - repl: "export {{ env_var["name"] }}=\"{{ env_var["value"] }}\""
    - append_if_not_found: true
{%- else %}
environment-variable-{{ env_var["name"] }}-absent-from-{{ target_file }}:
  file.replace:
    - name: {{ target_file }}
    - pattern: "^#?export {{ env_var["name"] }}=.*$"
    - repl: ""
    - append_if_not_found: false
{%- endif %}
{%- endfor %}
{%- endfor %}