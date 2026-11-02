"""The contexts as the product's spec, description and glossaries hold them."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.context_spec import ContextSpec, SharedKernel


class ContextSpecs(OutputPort, typing.Protocol):
    """Every bounded context the spec or the designed domain names, read as the project keeps them."""

    def contexts(self) -> typing.Sequence[ContextSpec]:
        """Each context once, in the designed domain's order, then any the spec alone holds."""
        ...

    def shared_kernel(self) -> typing.Optional[SharedKernel]:
        """The model the contexts share, as its glossary names it — None where it has none."""
        ...
