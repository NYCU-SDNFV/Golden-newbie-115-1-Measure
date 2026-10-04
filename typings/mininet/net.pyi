from typing import overload

from .node import Host, Node


class Mininet:
    hosts: list[Host]

    def __init__(self, *args: object, **kwargs: object) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...

    @overload
    def get(self, name: str, /) -> Node: ...

    @overload
    def get(self, name: str, name2: str, *names: str) -> list[Node]: ...
