
docker-registries-logged-in:
  module.run:
    - name: docker.login

docker-containers-list-before-release:
  module.run:
    - name: docker.ps
    - kwargs:
        all: true

{%- for proj in salt['pillar.get']('docker:projects', default=[]) %}

# Pull images for project before stopping containers
{%- for cont in proj.get('containers', []) %}
# Ensure required images are pulled, first all required_tags, then the tag to run.
{%- for tag in cont.required_tags %}
docker-image-{{ cont['qname'] }}-tag-{{ tag }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ tag }}
{%- endfor %}

docker-image-{{ cont['qname'] }}-basetag-{{ cont['tag'] }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ cont['tag'] }}

{%- endfor %}

# First ensure all unknown containers are stopped
{%- for qname in proj.get('unknown_containers', []) %}
docker-unknown-container-{{ qname }}-stopped:
  docker_container.stopped:
    - name: {{ qname }}
    - error_on_absent: false
{%- endfor %}

# First ensure all obsolete containers are stopped
{%- for qname in proj.get('obsolete_containers', []) %}
docker-obsolete-container-{{ qname }}-stopped:
  docker_container.stopped:
    - name: {{ qname }}
    - error_on_absent: false
{%- endfor %}

# "purge" directories
{%- for dir in proj.get('purge_directories', []) %}
# Remove old bak dir if exists
docker-directory-purge-{{ dir }}-old-bak-removed:
  file.absent:
    - name: {{ dir }}_bak

# Move new dir to bak
docker-directory-purge-{{ dir }}-dir-moved-to-bak:
  file.rename:
    - name: {{ dir }}_bak
    - source: {{ dir }}
{%- endfor %}

# Ensure all containers in release are running
{%- for cont in proj.get('containers', []) %}

# Ensure container is started/running
docker-container-{{ cont['qname'] }}-running:
  docker_container.running:
    - name: {{ cont['qname'] }}
    - image: {{ cont['image_full'] }}:{{ cont['tag'] }}
    {%- for key, val in cont['startup_parameters'].iteritems() %}
    - {{ key }}: {{ val|tojson }}
    {%- endfor %}
    - require:
      - docker_image: {{ cont['image_full'] }}:{{ cont['tag'] }}
      # Always require previous container is running
      {%- if loop.index > 1 %}
      - docker_container: docker-container-{{ proj['containers'][loop.index0 - 1]['qname'] }}-running
      {%- endif %}
    - require_in:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released

{%- endfor %}

# Ensure container is stopped if start failed for some reason
docker-project-{{ proj['name'] }}@{{ proj['version'] }}-containers-stopped-after-release-failure:
  docker_container.stopped:
    - names:
      {%- for cont in proj.get('containers', []) %}
      - {{ cont['qname'] }}
      {%- endfor %}
    - onfail:
      {%- for cont in proj.get('containers', []) %}
      - docker-container-{{ cont['qname'] }}-running
      {%- endfor %}
    - error_on_absent: false

docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released:
  test.succeed_without_changes:
    - name: 'docker:{{ proj['name'] }}@{{ proj['version'] }}'
    - comment: Version {{ proj['version'] }} released of project '{{ proj['name'] }}'

# On project release success remove obsolete containers
{%- for qname in proj.get('obsolete_containers', []) %}
docker-container-obsolete-{{ qname }}-removed:
  docker_container.absent:
    - name: {{ qname }}
    - force: true
    - require:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endfor %}

# On project release success remove stopped unknown containers
{%- for qname in proj.get('unknown_containers', []) %}
docker-container-unknown-{{ qname }}-removed:
  docker_container.absent:
    - name: {{ qname }}
    - force: true
    - require:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endfor %}

# On release failure restart fallback containers
{%- for qname in proj.get('fallback_containers', []) %}
docker-container-fallback-{{ qname }}-restarted-after-release-failure:
  module.run:
    - name: docker.start
    - kwargs:
        name: {{ qname }}
    - onfail:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endfor %}

# On release failure restart any unknown containers
{%- for qname in proj.get('unknown_containers', []) %}
docker-container-unknown-{{ qname }}-restarted-after-release-failure:
  module.run:
    - name: docker.start
    - kwargs:
        name: {{ qname }}
    - onfail:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endfor %}

{%- endfor %}

docker-containers-list-after-release:
  module.run:
    - name: docker.ps
    - kwargs:
        all: true