# Copyright 2026 Thousand Brains Project
#
# Copyright may exist in Contributors' modifications
# and/or contributions to the work.
#
# Use of this source code is governed by the MIT
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from __future__ import annotations

import logging

from tbp.monty.telemetry.schemas import TelemetryEvent


class TelemetryPublisher(logging.Logger):
    """Structured telemetry publisher.

    Subclasses `logging.Logger` and emits `TelemetrySchema` as structured `LogRecord`
    instances routed through the logging pipeline to telemetry handlers.

    Do not instantiate this class directly; obtain it via `telemetry.getTelemeter`.

    Example::

        telemeter = telemetry.getTelemeter(__name__)
        telemeter.info(TelemetryEvent(...))
    """

    def __init__(self, *args, **kwargs):
        """Creates the publisher; do not instantiate outside this module."""
        super().__init__(*args, **kwargs)
        self.propagate = False  # do not propagate to root logger

        # Prevent logging.lastResort from printing to stderr
        if not self.hasHandlers():
            self.addHandler(logging.NullHandler())

    def emit(self, level: int, event: TelemetryEvent):
        """Emits a structured telemetry event at the specified log level.

        Args:
            level: The log level.
            event: The event instance.

        Raises:
            TypeError: If the event is not a `TelemetryEvent`.
        """
        if not isinstance(event, TelemetryEvent):
            raise TypeError("This logger is only for telemetry events")

        self.log(
            level=level,
            msg=event.kind,
            extra={"telemetry_schema": event},
            stacklevel=2,  # reports the stack frame that called this method
        )

    def debug(
        self,
        event: TelemetryEvent,
        *args,  # noqa: ARG002
    ):
        """Emits a structured telemetry event at ``DEBUG`` log level."""
        self.emit(level=logging.DEBUG, event=event)

    def info(
        self,
        event: TelemetryEvent,
        *args,  # noqa: ARG002
    ):
        """Emits a structured telemetry event at ``INFO`` log level."""
        self.emit(level=logging.INFO, event=event)

    def critical(
        self,
        event: TelemetryEvent,
        *args,  # noqa: ARG002
    ):
        """Emits a structured telemetry event at ``CRITICAL`` log level."""
        self.emit(level=logging.CRITICAL, event=event)
