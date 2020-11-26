
docker-registries-logged-in:
  module.run:
    - name: docker.login

# TODO Set with all project names.
# TODO Change state to take list of known projects instead of regexes, and then remove all containers that does not start with the project slug!
{%- if salt['pillar.get']('docker:remove_unknown_containers', default=False) %}
{%- set _all_projects = [] %}
{%- for project in salt['pillar.get']('docker:projects', default=[]) %}
    {%- do _all_projects.append(project.get('name')) %}
{%- endfor %}
docker-unknown-containers-removed:
  docker_extra.container_absent_except:
    - projects: {{ _all_projects|tojson }}
    - force: True
{%- endif %}

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

# Ensure required images are pulled, first all required_tags, then the tag to run.
{%- for tag in cont.required_tags %}
docker-image-{{ cont['qname'] }}-tag-{{ tag }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ tag }}
{%- endfor %}

docker-image-{{ cont['qname'] }}-basetag-{{ cont['tag'] }}-present:
  docker_image.present:
    - name: {{ cont['image_full'] }}:{{ cont['tag'] }}

# TODO: If purge_data == true, move directories to FILE/DIR+.bak
# On fail move it back

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

# On release failure restart obsolete containers that were stopped
{%- for qname in proj.get('obsolete_containers', []) %}
docker-obsolete-container-{{ qname }}-started-after-release-failure:
  module.run:
    - name: docker.start
    - kwargs:
        name: {{ qname }}
    - requre:
      - docker_container: docker-obsolete-container-{{ qname }}-stopped
    - onfail:
      - test: docker-project-{{ proj['name'] }}-version-{{ proj['version'] }}-released
{%- endfor %}

{%- endfor %}