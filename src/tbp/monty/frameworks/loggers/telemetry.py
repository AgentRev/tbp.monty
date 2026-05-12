# Copyright 2025-2026 Thousand Brains Project
#
# Copyright may exist in Contributors' modifications
# and/or contributions to the work.
#
# Use of this source code is governed by the MIT
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from __future__ import annotations

import abc
import logging
import multiprocessing as mp
import queue
import threading
import time
from dataclasses import dataclass, field
from queue import Queue
from typing import ClassVar, Sequence, final

from tbp.monty.frameworks.experiments.mode import ExperimentMode
from tbp.monty.frameworks.models.abstract_monty_classes import Observations
from tbp.monty.frameworks.models.motor_system_state import ProprioceptiveState


@dataclass
class TelemetryEvent:
    """Base class for all telemetry snapshot events.

    Subclasses declare a schema_id to identify their event type and add dataclass fields
    for their payload. All instances carry universal context baggage (emitter,
    timestamp, episode, step, mode).
    """

    schema_id: ClassVar[str] = ""
    """Event type identifier, e.g. `env_interface.step`.
    Used by TelemetryBroker for routing and as the log message in text sinks."""

    schema_version: ClassVar[int] = 1
    """Incremented on backwards-incompatible field changes."""

    emitter: str = ""
    """Name of the emitting module, e.g. `self.__class__.__name__`."""

    timestamp: float = field(default_factory=time.monotonic)
    episode: int = 0
    step: int = 0
    mode: ExperimentMode = ExperimentMode.EVAL


class TelemetryStopEvent(TelemetryEvent):
    """Sentinel object to shut down telemetry consumer threads."""

    pass


TELEMETRY_STOP = TelemetryStopEvent()


@dataclass
class EpisodeStepEvent(TelemetryEvent):
    """Telemetry event emitted at each step of an episode."""

    schema_id = "env_interface.step"
    observations: Observations = field(default_factory=Observations)
    proprioceptive_state: ProprioceptiveState = field(
        default_factory=ProprioceptiveState
    )
    is_saccade_on_image: bool = False


class Telemetry:
    """Structured telemetry emitter, analogous to logging.Logger.

    Wraps a logging.Logger and emits TelemetryEvents as structured LogRecords
    routed through the logging pipeline to a TelemetryBroker. Obtain via a
    factory (e.g. `monty.get_telemetry(__name__)`) rather than instantiating
    directly.

    Usage::

        telemetry = monty.get_telemetry(__name__)
        telemetry.snapshot(logging.INFO, EpisodeResultEvent(...))
    """

    def __init__(self, logger: logging.Logger):
        """Telemetry constructor. Obtain via monty.get_telemetry() rather than directly.

        Args:
            logger: The underlying `logging.Logger`.
        """
        self._logger = logger

    def snapshot(self, level: int, event: TelemetryEvent):
        """Emit a structured telemetry event at the specified level.

        Args:
            level: logging level (`logging.DEBUG`, `logging.INFO`, etc.)
            event: The `TelemetryEvent` dataclass instance.
        """
        self._logger.log(
            level,
            event.schema_id,  # msg is the schema id for text sinks
            extra={"monty_telemetry": event},
            stacklevel=2,  # reports the stack frame that called `snapshot()`
        )


class TelemetryBroker(logging.Handler):
    """Fanout handler that routes telemetry events to subscribed consumer queues.

    Registered as a handler on the logging pipeline (typically via a QueueListener).
    On each emit(), looks up the event's schema_id and puts it onto every matching
    subscriber queue.

    Events are dispatched with `put_nowait()`. Full queues trigger `handleError()`
    rather than blocking the emitting thread.
    """

    def __init__(self):
        """Initialize the broker with an empty subscription table."""
        super().__init__()
        self.subscriptions: dict[str, set[Queue[TelemetryEvent]]] = {}

    def subscribe(
        self,
        schema_ids: list[str],
        event_queue: Queue[TelemetryEvent] | None = None,
    ) -> Queue[TelemetryEvent]:
        """Registers a queue to receive events for the given schema IDs.

        The same queue may be subscribed to multiple schema IDs, in which case all
        matching events are multiplexed onto it. Thread-safe.

        Args:
            schema_ids: Schema ID strings to subscribe to.
            event_queue: Queue to receive matching events. If `None`, a new
                         `queue.Queue` is created and returned.

        Returns:
            The subscribed queue.
        """
        if event_queue is None:
            event_queue = queue.Queue()
        with self.lock:
            for schema_id in schema_ids:
                self.subscriptions.setdefault(schema_id, set()).add(event_queue)
        return event_queue

    def unsubscribe(
        self,
        schema_ids: list[str],
        event_queue: Queue[TelemetryEvent],
    ):
        """Deregisters a queue from the given schema IDs. Thread-safe.

        Args:
            schema_ids: Schema IDs to unsubscribe from.
            event_queue: The queue to remove. Silently ignores unknown schema IDs.
        """
        # Force it into a list if it's a string, otherwise keep as is
        with self.lock:
            for schema_id in schema_ids:
                if schema_id in self.subscriptions:
                    self.subscriptions[schema_id].remove(event_queue)

    def emit(self, record: logging.LogRecord):
        """Dispatch a log record's telemetry event to all subscribed queues.

        Extracts the `TelemetryEvent` from `record.monty_telemetry` and fans it out to
        each queue subscribed to its `schema_id`. Non-telemetry records are silently
        ignored.

        Args:
            record: The `LogRecord` emitted by `Telemetry.snapshot()`.
        """
        event: TelemetryEvent = record.__dict__.get("monty_telemetry")
        if not isinstance(event, TelemetryEvent):
            return  # TODO: log or raise error?
        with self.lock:
            event_queues = self.subscriptions.get(event.schema_id, [])
        for event_queue in event_queues:
            try:
                event_queue.put_nowait(event)
            except queue.Full:
                self.handleError(record)


class TelemetryConsumer(abc.ABC):
    """Base class for telemetry consumers driven by an external `pump()` call.

    Maintains a `queue.Queue` subscribed to the broker for the declared `schema_ids`.
    The caller drives consumption by calling pump() periodically, typically from the
    main thread interleaved with other work or a GUI loop.

    Subclasses declare `schema_ids` and implement `_consume()`. Override `_post_pump()`
    for logic to run after each drain, e.g. `plt.pause()`.

    Usage::
        consumer = MyConsumer(broker)
        consumer.subscribe()
        while not done:
            consumer.pump()
        consumer.pump()  # final drain
        consumer.unsubscribe()
    """

    schema_ids: ClassVar[list[str]]  # subclass declares which schemas it wants

    def __init__(self, broker: TelemetryBroker, **kwargs):
        """Base constructor for abstract `TelemetryConsumer`.

        Args:
            broker: The `TelemetryBroker` to subscribe to.
            **kwargs: Forwarded to superclass.
        """
        super().__init__(**kwargs)
        self._broker = broker
        self.event_queue: Queue[TelemetryEvent] = queue.Queue()

    def subscribe(self):
        """Registers `event_queue` with the broker for `schema_ids`.

        Clears any stale events from a previous run before re-registering.
        """
        with self.event_queue.mutex:
            self.event_queue.queue.clear()
        self._broker.subscribe(schema_ids=self.schema_ids, event_queue=self.event_queue)

    def unsubscribe(self):
        """Deregisters `event_queue` from the broker for `schema_ids`."""
        self._broker.unsubscribe(self.schema_ids, self.event_queue)

    def pump(self, continuous=False):
        """Consumes pending events from the queue, then calls `_post_pump()`.

        In non-continuous mode (default), drains all queued events and returns.
        In continuous mode, blocks on each get() until a `TelemetryStopEvent` is
        received; used internally by `ThreadedTelemetryConsumer._pump_loop()`.

        `_post_pump()` is called once after the queue drains. Not called if a
        TelemetryStopEvent causes an early return.
        """
        while True:
            if continuous:
                event = self.event_queue.get()
            else:
                try:
                    event = self.event_queue.get_nowait()
                except queue.Empty:
                    break
            if isinstance(event, TelemetryStopEvent):
                return
            self._consume(event)
        self._post_pump()

    @abc.abstractmethod
    def _consume(self, event: TelemetryEvent):
        """Processes a single telemetry event."""
        ...

    def _post_pump(self):
        """Called once after `pump()` drains the queue in non-continuous mode.

        Not called when `pump()` exits early due to a `TelemetryStopEvent`.
        Override to add post-drain behavior,

        Example::

            def _post_pump(self):
                plt.pause(0.00001)
        """
        return


class ThreadedTelemetryConsumer(TelemetryConsumer, abc.ABC):
    """A `TelemetryConsumer` that drives `pump()` on a dedicated background thread.

    Starts a daemon thread that calls `pump(continuous=True)`, blocking on each event
    until a `TelemetryStopEvent` is received. The calling thread is never blocked by
    event processing.

    Use this for consumers whose `_consume()` is thread-safe and does not require
    main-thread execution (e.g. file writers, forwarding bridges).

    For consumers that must run on the main thread (e.g. matplotlib GUIs), use
    `TelemetryConsumer` directly instead and call `pump()` from the main thread.

    Usage::

        consumer = MyThreadedConsumer(broker)
        consumer.start()
        # ... events processed in background ...
        consumer.stop()
    """

    def __init__(self, broker: TelemetryBroker, **kwargs):
        """Initializes the consumer.

        Args:
            broker: The TelemetryBroker to subscribe to.
            **kwargs: Forwarded to TelemetryConsumer.
        """
        super().__init__(broker=broker, **kwargs)
        self._thread = threading.Thread(target=self._pump_loop, daemon=True)

    def __del__(self):
        """Attempts a best-effort stop on garbage collection."""
        self.stop()

    def start(self):
        """Subscribes to the broker and start the background thread.

        No effect if already running.
        """
        if not self._thread.is_alive():
            self.subscribe()
            self._thread.start()

    def stop(self):
        """Signals the background thread to stop and join it.

        Sends a TelemetryStopEvent to unblock the thread if it is waiting on `get()`,
        then joins it. Unsubscribes from the broker unconditionally.
        """
        if self._thread.is_alive():
            self.event_queue.put(TELEMETRY_STOP)
            self._thread.join()
        self.unsubscribe()

    def _pump_loop(self):
        """Thread entry point. Runs pump(continuous=True) until stopped."""
        self.pump(continuous=True)


class MultiprocessTelemetryConsumer(ThreadedTelemetryConsumer, abc.ABC):
    """Telemetry consumer that consumes events in a dedicated child process.

    Extends `ThreadedTelemetryConsumer`, reusing its broker queue, bridge thread,
    subscribe/unsubscribe, and stop sentinel machinery. The inherited thread acts as the
    bridge between the broker queue and the child process: it drains the broker's
    `queue.Queue` and forwards events into a `multiprocessing.Queue` that the child
    process reads from.

    Subclasses implement `_process_consume()` rather than `_consume()`. The latter is
    reserved for the forwarding logic and must not be overridden.
    """

    def __init__(self, broker: TelemetryBroker, **kwargs):
        """Initializes the consumer, creating the `mp.Queue` and child process.

        The process is not started until `start()` is called.

        Args:
            broker: The `TelemetryBroker` to subscribe to.
            **kwargs: Forwarded to superclass.
        """
        super().__init__(broker=broker, **kwargs)
        self._mp_queue: mp.Queue = mp.Queue()
        self._process = mp.Process(
            target=self._process_main, args=(self._mp_queue,), daemon=True
        )

    def start(self):
        """Starts the child process, then the bridge thread.

        Process is started first so it is ready to receive events as soon as the bridge
        thread begins forwarding.
        """
        self._process.start()
        super().start()  # starts bridge thread + subscribe

    def stop(self):
        """Stops the bridge thread, then the child process.

        Joins the bridge thread first via `super()` to ensure all pending events have
        been forwarded to _mp_queue before the sentinel is sent to the child process.
        """
        super().stop()  # drains broker queue, joins bridge thread, unsubscribes
        if self._process.is_alive():
            self._mp_queue.put(TELEMETRY_STOP)
            self._process.join()

    @final
    def _consume(self, event: TelemetryEvent):
        """Forwards an event from the broker queue to the child process.

        This is the bridge step. Do not override in subclasses; implement
        `_process_consume()` instead.
        """
        self._mp_queue.put(event)

    def _process_main(self, mp_queue: mp.Queue):
        """Entry point for the child process.

        Drains `mp_queue` in a blocking loop, calling `_process_consume()` for each
        event until a TelemetryStopEvent is received.
        """
        while True:
            event = mp_queue.get()
            if isinstance(event, TelemetryStopEvent):
                break
            self._process_consume(event)

    @abc.abstractmethod
    def _process_consume(self, event: TelemetryEvent):
        """Event processing logic. Runs in the child process.

        Note: Cannot reference a live object from the parent process.
        """
        ...
