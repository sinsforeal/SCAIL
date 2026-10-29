"""Declared wires: what a module is handed after construction.

Most of the mind is built in `scail.App.__init__` and the program builders
and then handed its collaborators by assignment -- `persona.ledger = ledger`
-- because the objects are built in an order no constructor signature can
express. The failure mode of that is silence: a receiver reading a wire with
`getattr(self, name, None)` cannot tell "not built for this character" from
"built and never attached", and a wiring loop once ran before the object it
named existed, so a kept promise never counted for weeks.

So a receiver DECLARES its wires in a class tuple, `WIRES`; `declare(self)`
at the end of its constructor makes every declared name an attribute that
starts `None`; `wire(target, name=obj, ...)` attaches, and refuses a name the
target has not declared. A declared wire that is still `None` after the App
is built, while the App holds the thing to attach, is a fault the App reports
(`App.unwired`) and smoke fails on. A wire that is `None` because the
character has no such thing (a program slot the program did not build) is
ordinary, and the receiver reads it as a plain attribute.
"""


class WiringError(RuntimeError):
    pass


def declare(obj):
    """Every declared wire exists on `obj`, `None` unless the constructor set it."""
    for name in getattr(type(obj), "WIRES", ()):
        if not hasattr(obj, name):
            setattr(obj, name, None)


def wire(target, **objects):
    declared = getattr(type(target), "WIRES", None)
    if declared is None:
        raise WiringError(f"{type(target).__name__} declares no wires")
    for name, obj in objects.items():
        if name not in declared:
            raise WiringError(f"{type(target).__name__} declares no wire '{name}' (WIRES: {', '.join(declared)})")
        setattr(target, name, obj)
    return target


def unwired(obj):
    """Declared wires on `obj` still `None`."""
    return [n for n in getattr(type(obj), "WIRES", ()) if getattr(obj, n, None) is None]
