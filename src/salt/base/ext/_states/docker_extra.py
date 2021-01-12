import re

def container_absent_except(name, containers, force=False):
    '''
    Ensure that all containers except those that match the container names are absent.
    This state must be run with all container names in one go, do not use the name field.

    containers
        List of container names that will be excempted from being absent.

    force : False
        Set to ``True`` to remove the container even if it is running

    Usage Examples:

    .. code-block:: yaml

        project_slug:
          docker_extra.container_absent_except

        multiple_names:
          docker_extra.container_absent_except:
            - containers:
              - container_name
              - container_name
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not containers:
        ret['result'] = False
        ret['comment'] = (
            'No names provided to be excempt, not removing everything.'
        )
        return ret

    running_containers = __salt__['docker.list_containers'](all=True)

    if not running_containers:
        ret['result'] = True
        ret['comment'] = 'No containers exists'
        return ret

    # Find unknown containers
    to_remove = []
    for container_name in running_containers:
        if not [x for x in containers if re.match(x, container_name)]:
            to_remove.append(container_name)

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Containers \'{0}\' will be removed'.format(to_remove))
        return ret

    # Iterate over matches
    stop_errors = []
    for target in to_remove:
        try:
            changes = __salt__['docker.rm'](target, force=force)
            ret['changes'][target] = changes
        except Exception:
            stop_errors.append(changes)

    if stop_errors:
        ret['comment'] = '; '.join(stop_errors)
        return ret

    ret['result'] = True
    if to_remove:
        ret['comment'] = (
            'The following container(s) were removed: {0}'
            .format(', '.join(to_remove))
        )
    else:
        ret['comment'] = (
            'No containers were removed'
        )

    return ret
