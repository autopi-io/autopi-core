base:
  '*':
    - minion.requirements
    - redis.server
dev:
  '*':
    - simulators
    - schedules