from subprocess import Popen
from typing import Literal, overload


class Intf:
    name: str


class Node:
    name: str

    def cmd(self, *args: object, **kwargs: object) -> str | None: ...

    @overload
    def popen(self, *args: object, text: Literal[True], **kwargs: object) -> Popen[str]: ...

    @overload
    def popen(self, *args: object, universal_newlines: Literal[True], **kwargs: object) -> Popen[str]: ...

    @overload
    def popen(self, *args: object, encoding: str, **kwargs: object) -> Popen[str]: ...

    @overload
    def popen(self, *args: object, errors: str, **kwargs: object) -> Popen[str]: ...

    @overload
    def popen(
        self, *args: object, text: Literal[False] | None = None,
        universal_newlines: Literal[False] | None = None,
        encoding: None = None, errors: None = None, **kwargs: object,
    ) -> Popen[bytes]: ...

    @overload
    def popen(
        self, *args: object, text: bool | None = None,
        universal_newlines: bool | None = None, encoding: str | None = None,
        errors: str | None = None, **kwargs: object,
    ) -> Popen[str] | Popen[bytes]: ...

    def IP(self, intf: str | Intf | None = None) -> str | None: ...
    def MAC(self, intf: str | Intf | None = None) -> str | None: ...
    def intfList(self) -> list[Intf]: ...


class Host(Node):
    pass


class Switch(Node):
    pass


class OVSSwitch(Switch):
    def __init__(
        self,
        name: str,
        failMode: str = "secure",
        datapath: str = "kernel",
        **params: object,
    ) -> None: ...
