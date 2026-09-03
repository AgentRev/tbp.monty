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
import unittest

import hydra
import pytest

from tbp.monty import telemetry
from tbp.monty.frameworks.models import monty_base
from tbp.monty.hydra import instantiate_experiment
from tbp.monty.telemetry.publishers import TelemetryPublisher
from tbp.monty.telemetry.schemas import TelemetryEvent
from tests import HYDRA_ROOT

pytest.importorskip(
    "habitat_sim",
    reason="Habitat Sim optional dependency not installed.",
)


class TelemetryLogHandler(logging.Handler):
    """Logging handler that collects log records for telemetry assertions."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord):
        self.records.append(record)


class TelemetryEventTest(unittest.TestCase):
    """Unit tests for telemetry events."""

    def test_telemetry_event_defaults(self):
        """Verify TelemetryEvent kind fallback and values mapping."""
        event = TelemetryEvent(kind="")
        self.assertEqual(event.kind, event.__class__.__name__)

    def test_telemetry_event_custom_fields(self):
        """Verify TelemetryEvent kind when explicitly specified."""
        kind = "NewGraphAdded"
        graph_id = "new_object0"
        event = TelemetryEvent(kind=kind, graph_id=graph_id)
        self.assertEqual(event.kind, kind)
        self.assertEqual(event.graph_id, graph_id)


class TelemetryPublisherTest(unittest.TestCase):
    """Unit tests for TelemetryPublisher."""

    def setUp(self):
        self.handler = TelemetryLogHandler()
        self.telemeter = telemetry.getTelemeter(monty_base.__name__)
        self.telemeter.addHandler(self.handler)

        with hydra.initialize_config_dir(version_base=None, config_dir=str(HYDRA_ROOT)):
            self.base_cfg = hydra.compose(
                config_name="experiment",
                overrides=[
                    "experiment=test/profile/base",
                    "+telemetry=info",
                ],
            )

    def tearDown(self):
        self.telemeter.removeHandler(self.handler)

    def test_config(self):
        """Verify all telemeter configuration."""
        with instantiate_experiment(self.base_cfg.experiment):
            self.assertIsInstance(self.telemeter, TelemetryPublisher)
            self.assertEqual(self.telemeter.name, f"telemetry.{monty_base.__name__}")
            self.assertEqual(self.telemeter.getEffectiveLevel(), logging.INFO)
            self.assertFalse(self.telemeter.propagate)
            self.assertTrue(self.telemeter.hasHandlers())

    def test_emit_events(self):
        """Verify emitting events emits LogRecord with attached telemetry schema."""
        with instantiate_experiment(self.base_cfg.experiment):
            events = [
                (
                    self.telemeter.info,
                    logging.INFO,
                    TelemetryEvent(kind="InfoEvent"),
                ),
                (
                    self.telemeter.critical,
                    logging.CRITICAL,
                    TelemetryEvent(kind="CriticalEvent"),
                ),
            ]

            for log_func, _, event in events:
                log_func(event)

            self.assertEqual(len(self.handler.records), len(events))

            for record, (_, level, event) in zip(self.handler.records, events):
                self.assertEqual(record.levelno, level)
                self.assertEqual(record.msg, event.kind)
                self.assertIs(record.__dict__.get("telemetry_schema"), event)

    def test_ignored_level(self):
        """Verify debug event is ignored with telemetry level ``INFO``."""
        with instantiate_experiment(self.base_cfg.experiment):
            self.telemeter.debug(TelemetryEvent(kind="DebugEvent"))
            self.assertEqual(len(self.handler.records), 0)
