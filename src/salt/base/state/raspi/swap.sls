
{%- if salt["pillar.get"]("rpi:swap", default=False) %}
dphys-swapfile-running:
  service.running:
    - name: dphys-swapfile
    - enable: true
    - unmask: true
{%- else %}
dphys-swapfile-disabled:
  service.disabled:
    - name: dphys-swapfile
dphys-swapfile-masked:
  service.masked:
    - name: dphys-swapfile
{%- endif %}
