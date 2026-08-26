# Copyright 2026 Thousand Brains Project
#
# Copyright may exist in Contributors' modifications
# and/or contributions to the work.
#
# Use of this source code is governed by the MIT
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""Structured telemetry framework based on Python's logging pub/sub.

Provides a structured telemetry module that emits inline telemetry events routed through
standard Python `logging` mechanics. Telemetry schemas and events are passed via the
``extra`` parameter of `logging.Logger.log` and stored within the internal ``__dict__``
of `logging.LogRecord` objects.

Modules:
    -   schemas: Defines `TelemetrySchema` and `TelemetryEvent` Pydantic models for
        structured telemetry.
    -   publishers: Defines `TelemetryPublisher`, backed by isolated loggers under the
        ``telemetry.*`` namespace.

Example::

    from tbp.monty.frameworks import telemetry
    from tbp.monty.frameworks.telemetry.schemas import TelemetryEvent

    telemeter = telemetry.getTelemeter(__name__)
    telemeter.info(TelemetryEvent(kind="CustomEvent", values={"key": "value"}))
"""

from __future__ import annotations

import logging

# Telemetry log levels, mirrors logging
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET


def getTelemeter(*args, **kwargs):  # noqa: N802 - lowercase
    """Alias function for the `TelemetryPublisher` constructor.

    Example::

        telemeter = telemetry.getTelemeter(__name__)
        telemeter.info(TelemetryEvent(...))

    Returns:
        The publisher instance.
    """
    # Lazy import to avoid circular dependency
    from tbp.monty.frameworks.telemetry.publishers import (  # noqa: PLC0415
        TelemetryPublisher,
    )

    return TelemetryPublisher(*args, **kwargs)
