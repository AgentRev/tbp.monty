# Copyright 2025 Thousand Brains Project
#
# Copyright may exist in Contributors' modifications
# and/or contributions to the work.
#
# Use of this source code is governed by the MIT
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
from __future__ import annotations

from typing import Dict, Protocol

from tbp.monty.frameworks.actions.actions import Action
from tbp.monty.frameworks.environments.embodied_environment import (
    ObjectID,
    QuaternionWXYZ,
    SemanticID,
    VectorXYZ,
)


class Simulator(Protocol):
    """A Protocol defining a simulator for use in simulated environments.

    A Simulator is responsible for a simulated environment that contains objects to
    interact with, agents to do the interacting, and for collecting observations and
    proprioceptive state to send to Monty.
    """

    # TODO - do we need a way to abstract the concept of "agent"?
    def initialize_agent(self, agent_id, agent_state) -> None:
        """Update agent runtime state."""
        ...

    def remove_all_objects(self) -> None:
        """Remove all objects from the simulated environment."""
        ...

    def add_object(
        self,
        name: str,
        position: VectorXYZ | None = None,
        rotation: QuaternionWXYZ | None = None,
        scale: VectorXYZ | None = None,
        semantic_id: SemanticID | None = None,
        enable_physics: bool = False,
        primary_target_object: ObjectID | None = None,
    ) -> tuple[ObjectID, SemanticID | None]:
        """Add new object to simulated environment.

        Adds a new object based on the named object. This assumes that the set of
        available objects are preloaded and keyed by name.

        Args:
            name: Registered object name.
            position: Initial absolute position of the object. Defaults to None.
            rotation: Initial orientation of the object. Defaults to None.
            scale: Initial object scale. Defaults to None.
            semantic_id: Optional override for the object's semantic ID. Defaults to
                None.
            enable_physics: Whether to enable physics on the object. Defaults to False.
            primary_target_object: ID of the primary target object. If not None, the
                added object will be positioned so that it does not obscure the initial
                view of the primary target object (which avoiding collision alone cannot
                guarantee). Used when adding multiple objects. Defaults to None.

        Returns:
            Tuple with the ID of the added object and optionally, the semantic ID of the
            object.
        """
        ...

    @property
    def num_objects(self) -> int:
        """Return the number of instantiated objects in the environment."""
        ...

    @property
    def observations(self):
        """Get sensor observations."""
        ...

    @property
    def states(self):
        """Get agent and sensor states."""
        ...

    def apply_action(self, action: Action) -> Dict[str, Dict]:
        """Execute the given action in the environment.

        Args:
            action: The action to execute.

        Returns:
            A dictionary with the observations grouped by agent_id.
        """
        ...

    def reset(self):
        """Reset the simulator.

        Returns:
            The initial observations from the simulator.
        """
        ...

    def close(self) -> None:
        """Close any resources used by the simulator."""
        ...
