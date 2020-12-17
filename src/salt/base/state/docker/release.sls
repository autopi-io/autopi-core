
docker-containers-list-before-release:
  module.run:
    - name: docker.ps
    - kwargs:
        all: true

docker-registries-logged-in:
  module.run:
    - name: docker.login

# Loop through all projects
{%- for proj in salt['pillar.get']('docker:projects', default=[]) %}
{%- set proj_id_prefix = 'docker-project-' ~ proj['name'] ~ '@' ~ proj['version'] %} 

# Pull images
###############################################################################

# First images for current containers
{%- for cont in proj.get('containers', []) %}

# Ensure required images are pulled, first all required tags, then the base tag to run
{%- for tag in cont.required_tags %}
{{ proj_id_prefix }}-image-{{ cont['qname'] }}-tag-{{ tag }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ tag }}
    - require:
      - module: docker-registries-logged-in 
    - require_in:
      - test: {{ proj_id_prefix }}-images-present
{%- endfor %}  # Tags loop

{{ proj_id_prefix }}-image-{{ cont['qname'] }}-basetag-{{ cont['tag'] }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ cont['tag'] }}
    - require:
      - module: docker-registries-logged-in 
    - require_in:
      - test: {{ proj_id_prefix }}-images-present
{%- endfor %}  # Current containers loop

# Then images for fallback containers
{%- for cont in proj.get('fallback_containers', []) %}

# Ensure required images are pulled, first all required tags, then the base tag to run
{%- for tag in cont.required_tags %}
{{ proj_id_prefix }}-image-{{ cont['qname'] }}-tag-{{ tag }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ tag }}
    - require:
      - module: docker-registries-logged-in
    - require_in:
      - test: {{ proj_id_prefix }}-images-present
{%- endfor %}  # Tags loop

{{ proj_id_prefix }}-image-{{ cont['qname'] }}-basetag-{{ cont['tag'] }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ cont['tag'] }}
    - require:
      - module: docker-registries-logged-in 
    - require_in:
      - test: {{ proj_id_prefix }}-images-present
{%- endfor %}  # Fallback containers loop

{{ proj_id_prefix }}-images-present:
  test.succeed_without_changes:
    - comment: All images are present for project '{{ proj['name'] }}' version {{ proj['version'] }}

# Stop any unknown containers
###############################################################################

# Ensure all unknown containers are stopped
{%- for name in proj.get('unknown_containers', []) %}
{{ proj_id_prefix }}-unknown-container-{{ name }}-stopped:
  docker_container.stopped:
    - name: {{ name }}
    - error_on_absent: false
    - require:
      - test: {{ proj_id_prefix }}-images-present
    - require_in:
      - test: {{ proj_id_prefix }}-unknown-containers-stopped
{%- endfor %}  # Unknown containers loop

{{ proj_id_prefix }}-unknown-containers-stopped:
  test.succeed_without_changes:
    - comment: {{ proj.get('unknown_containers', [])|length }} unknown container(s) stopped for project '{{ proj['name'] }}' version {{ proj['version'] }}

# Stop any obsolete containers
###############################################################################

# Ensure all obsolete containers are stopped
{%- for qname in proj.get('obsolete_containers', []) %}
{{ proj_id_prefix }}-obsolete-container-{{ qname }}-stopped:
  docker_container.stopped:
    - name: {{ qname }}
    - error_on_absent: false
    - require:
      - test: {{ proj_id_prefix }}-unknown-containers-stopped
    - require_in:
      - test: {{ proj_id_prefix }}-obsolete-containers-stopped
{%- endfor %}  # Obsolete containers loop

{{ proj_id_prefix }}-obsolete-containers-stopped:
  test.succeed_without_changes:
    - comment: {{ proj.get('obsolete_containers', [])|length }} obsolete container(s) stopped for project '{{ proj['name'] }}' version {{ proj['version'] }}

# Backup purge directories for obsolete containers
###############################################################################

{%- for dir in proj.get('purge_directories', []) %}
{{ proj_id_prefix }}-purge-directory-{{ loop.index }}-backed-up:
  file.rename:
    - name: {{ dir }}.bak
    - source: {{ dir }}
    - onlyif: test -d {{ dir }}
    - require:
      - test: {{ proj_id_prefix }}-obsolete-containers-stopped
    - require_in:
      - test: {{ proj_id_prefix }}-purge-directories-backed-up
{%- endfor %}  # Purge directories loop

{{ proj_id_prefix }}-purge-directories-backed-up:
  test.succeed_without_changes:
    - comment: {{ proj.get('purge_directories', [])|length }} purge directories backed up for project '{{ proj['name'] }}' version {{ proj['version'] }}

# Start current containers
###############################################################################

# Ensure all containers in release are started/running
{%- for cont in proj.get('containers', []) %}
{{ proj_id_prefix }}-container-{{ cont['qname'] }}-running:
  docker_container.running:
    - name: {{ cont['qname'] }}
    - image: {{ cont['image_full'] }}:{{ cont['tag'] }}
    {%- for key, val in cont['startup_parameters'].iteritems() %}
    - {{ key }}: {{ val|tojson }}
    {%- endfor %}
    - require:
      - test: {{ proj_id_prefix }}-purge-directories-backed-up
      # Also require previous container is running
      {%- if loop.index > 1 %}
      - docker_container: {{ proj_id_prefix }}-container-{{ proj['containers'][loop.index0 - 1]['qname'] }}-running
      {%- endif %}
    - require_in:
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Current containers loop

{{ proj_id_prefix }}-released:
  test.succeed_without_changes:
    - name: 'docker:{{ proj['name'] }}@{{ proj['version'] }}'
    - comment: Version {{ proj['version'] }} released of project '{{ proj['name'] }}'

# Remove any unknown containers
###############################################################################

{%- for name in proj.get('unknown_containers', []) %}
{{ proj_id_prefix }}-unknown-container-{{ name }}-removed:
  docker_container.absent:
    - name: {{ name }}
    - force: true
    - require:
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Unknown containers loop

# Remove any obsolete containers
###############################################################################

{%- for qname in proj.get('obsolete_containers', []) %}
{{ proj_id_prefix }}-obsolete-container-{{ qname }}-removed:
  docker_container.absent:
    - name: {{ qname }}
    - force: true
    - require:
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Obsolete containers loop

# Delete purge directories for obsolete containers
###############################################################################

{%- for dir in proj.get('purge_directories', []) %}
{{ proj_id_prefix }}-purge-directory-{{ loop.index }}-deleted:
  file.absent:
    - name: {{ dir }}.bak
    - require:
      - test: {{ proj_id_prefix }}-obsolete-containers-stopped
    - require:
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Purge directories loop

# Failure: Stop current containers
###############################################################################

# Ensure containers are stopped if start failed for some reason
{{ proj_id_prefix }}-containers-stopped-after-release-failure:
  docker_container.stopped:
    - names:
      {%- for cont in proj.get('containers', []) %}
      - {{ cont['qname'] }}
      {%- endfor %}
    - error_on_absent: false
    - onfail:
      - test: {{ proj_id_prefix }}-released

# Failure: Restore purge directories for obsolete containers
###############################################################################

{%- for dir in proj.get('purge_directories', []) %}
{{ proj_id_prefix }}-purge-directory-{{ loop.index }}-restored:
  file.rename:
    - name: {{ dir }}
    - source: {{ dir }}.bak
    - onlyif: test -d {{ dir }}.bak
    - onfail:
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Purge directories loop

# Failure: Restart any fallback containers
###############################################################################

{%- for cont in proj.get('fallback_containers', []) %}
{{ proj_id_prefix }}-fallback-container-{{ cont['qname'] }}-restarted:
  docker_container.running:
    - name: {{ cont['qname'] }}
    - image: {{ cont['image_full'] }}:{{ cont['tag'] }}
    {%- for key, val in cont['startup_parameters'].iteritems() %}
    - {{ key }}: {{ val|tojson }}
    {%- endfor %}
    - onfail_any:
      - test: {{ proj_id_prefix }}-obsolete-containers-stopped
      - test: {{ proj_id_prefix }}-purge-directories-backed-up
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Fallback containers loop

# Failure: Restart any unknown containers
###############################################################################

{%- for name in proj.get('unknown_containers', []) %}
{{ proj_id_prefix }}-unknown-container-{{ name }}-restarted:
  module.run:
    - name: docker.start
    - kwargs:
        name: {{ name }}
    - onfail_any:
      - test: {{ proj_id_prefix }}-unknown-containers-stopped
      - test: {{ proj_id_prefix }}-released
{%- endfor %}  # Unknown containers loop

{%- endfor %}  # Projects loop

docker-containers-list-after-release:
  module.run:
    - name: docker.ps
    - kwargs:
        all: true