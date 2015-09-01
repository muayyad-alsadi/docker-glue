import sys, os, os.path

def resolve_dotted_name(name):
    """Return object referenced by dotted name.
    :param name: dotted name as a String.
    :return: Resolved Python object.
    :raises ImportError: If can't resolve ``nane``
    Examples:
        >>> resolve_dotted_name('sys.exit')
        <built-in function exit>
        >>> resolve_dotted_name('xml.etree.ElementTree')  # doctest: +ELLIPSIS
        <module 'xml.etree.ElementTree' ...>
        >>> resolve_dotted_name('distconfig.backends.zookeeper.ZooKeeperBackend')
        <class 'distconfig.backends.zookeeper.ZooKeeperBackend'>
    """
    paths = name.split('.')
    current = paths[0]
    found = __import__(current)
    for part in paths[1:]:
        current += '.' + part
        try:
            found = getattr(found, part)
        except AttributeError:
            found = __import__(current, fromlist=part)
    return found


def factory(dotted_name, *args, **kw):
    return resolve_dotted_name(dotted_name)(*args, **kw)

def relative_to_exec_dirs(dirs, suffix=''):
    # os.path.join: If a component is an absolute path, all previous components are thrown away
    exec_prefix = os.path.dirname(sys.argv[0])
    paths = map(lambda d: os.path.realpath(os.path.normpath(os.path.join(exec_prefix, d+suffix))), dirs)
    paths = filter(lambda d: os.path.isdir(d), paths)
    return paths
