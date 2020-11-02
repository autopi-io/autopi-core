
docker-registries-logged-in:
  module.run:
    - name: docker.login

{%- for proj in salt['pillar.get']('docker:projects', default=[]) %}

# First ensure all obsolete containers are stopped
{%- for qname in proj.get('obsolete_containers', []) %}
docker-obsolete-container-{{ qname }}-stopped:
  docker_container.stopped:
    - name: {{ qname }}
    - error_on_absent: false
{%- endfor %}

# Ensure all containers in release are running
{%- for cont in proj.get('containers', []) %}

# Ensure required images are pulled
docker-image-{{ cont['qname'] }}-basetag-{{ cont['tag'] }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ cont['tag'] }}

{%- for tag in cont.required_tags %}
docker-image-{{ cont['qname'] }}-tag-{{ tag }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ tag }}
{%- endfor %}

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
    - onfail_in:
      - docker_container: docker-container-{{ cont['qname'] }}-stopped-after-release-failure
    - require_in:
      - docker_container: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released

# Ensure container is stopped if start failed for some reason
docker-container-{{ cont['qname'] }}-stopped-after-release-failure:
  docker_container.stopped:
    - name: {{ cont['qname'] }}
    - error_on_absent: false

{%- endfor %}

docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released:
  test.succeed_without_changes:
    - name: {{ proj['name'] }}@{{ proj['version'] }}
    - comment: Version {{ proj['version'] }} released of project '{{ proj['name'] }}'

# On project release success remove obsolete containers
{%- if proj.get('obsolete_containers', []) %}
docker-project-{{ proj['name'] }}-obsolete-containers-removed:
  docker_container.absent:
    - names: {{ proj.get('obsolete_containers', [])|tojson }}
    - force: true
    - require:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endif %}

# On release failure restart obsolete containers that were stopped
{%- for qname in proj.get('obsolete_containers', []) %}
docker-obsolete-container-{{ qname }}-started-after-release-failure:
  docker_container.running:
    - name: {{ qname }}
    - onchanges:
      - docker_container: docker-obsolete-container-{{ qname }}-stopped
    - onfail:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endfor %}

{%- endfor %}
