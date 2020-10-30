{%- for container in salt['pillar.get']('docker:containers', default=[]) %}

# Pull required images
image-{{ container['project'] }}-{{ container['name'] }}-basetag-{{ container['tag'] }}-present:
  docker_image.present:
    - name: {{ container['image_full'] }}:{{ container['tag'] }}

{%- for tag in container.required_tags %}
image-{{ container['project'] }}-{{ container['name'] }}-{{ tag }}-present:
  docker_image.present:
    - name: {{ container['image_full'] }}:{{ tag }}
{%- endfor %}

# Clean old container
container-{{ container['project'] }}-{{ container['name'] }}-removed:
  docker_container.absent:
    - name: {{ container['name'] }}
    - force: true

# Start new containers
container-{{ container['project'] }}-{{ container['name'] }}-running:
  docker_container.running:
    - name: {{ container['name'] }}
    - image: {{ container['image_full'] }}:{{ container['tag'] }}
    {%- for key, val in container['startup_parameters'].iteritems() %}
    - {{ key }}: {{ val|tojson }}
    {%- endfor %}
    - require:
      - docker_image: {{ container['image_full'] }}:{{ container['tag'] }}

# TODO: Move data directory to "*_backup_DATE" or something
# container-{{ container['project'] }}-{{ container['name'] }}-backup-data:

{%- endfor %}

{%- for container_name in salt['pillar.get']('docker:obsolete_containers', default=[]) %}
container-cleanup-{{ container_name }}-removed:
  docker_container.absent:
    - name: {{ container_name }}
    - force: true
{%- endfor %}

# if success
    # Clean data directories if required
    # Remove all containers
# Fallback?
# Remove unreferenced images