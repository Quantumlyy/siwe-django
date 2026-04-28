"""Optional drf-spectacular decorators for the DRF view layer.

The ``openapi`` extra installs drf-spectacular and unlocks full schemas. When
drf-spectacular is not present we expose passthrough decorators so importing
``siwe_django.drf.views`` does not error in the default install.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:  # pragma: no cover - exercised only with the optional extra installed
    from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

    SPECTACULAR_INSTALLED = True
except ImportError:  # pragma: no cover

    SPECTACULAR_INSTALLED = False

    def extend_schema(*_args: Any, **_kwargs: Any) -> Callable[[Callable], Callable]:
        def decorator(view: Callable) -> Callable:
            return view

        return decorator

    class OpenApiExample:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None: ...

    class OpenApiResponse:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None: ...


SIWE_TAG = "siwe"


__all__ = [
    "SIWE_TAG",
    "SPECTACULAR_INSTALLED",
    "OpenApiExample",
    "OpenApiResponse",
    "extend_schema",
]
