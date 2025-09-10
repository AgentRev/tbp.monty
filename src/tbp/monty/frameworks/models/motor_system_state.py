# Copyright 2025 Thousand Brains Project
#
# Copyright may exist in Contributors' modifications
# and/or contributions to the work.
#
# Use of this source code is governed by the MIT
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from tbp.monty.frameworks.models.abstract_monty_classes import AgentID, SensorID


@dataclass
class SensorState:
    """The proprioceptive state of a sensor."""

    position: Any  # TODO: Stop using magnum.Vector3 and decide on Monty standard
    """The sensor's position relative to the agent."""
    rotation: Any  # TODO: Stop using quaternion.quaternion and decide on Monty standard
    """The sensor's rotation relative to the agent."""

@dataclass
class AgentState:
    """The proprioceptive state of an agent."""

    sensors: Dict[SensorID, SensorState]
    """The proprioceptive state of the agent's sensors."""
    position: Any  # TODO: Stop using magnum.Vector3 and decide on Monty standard
    """The agent's position relative to some global reference frame."""
    rotation: Any  # TODO: Stop using quaternion.quaternion and decide on Monty standard
    """The agent's rotation relative to some global reference frame."""
    motor_only_step: bool = False
    """Control flow parameter. Processing will bypass the learning module if True.

    TODO: Remove once we refactor Monty main processing loop to no longer need
    control flow parameters in motor system state.
    """


class ProprioceptiveState(Dict[AgentID, AgentState]):
    """The proprioceptive state of the motor system."""


class MotorSystemState(Dict[AgentID, AgentState]):
    """The state of the motor system.

    TODO: Currently, ProprioceptiveState can be cast to MotorSystemState since
          MotorSystemState is a generic dictionary. In the future, make
          ProprioceptiveState a param on MotorSystemState to more clearly distinguish
          between the two. These are separate from each other because
          ProprioceptiveState is the information returned from the environment, while
          MotorSystemState is that, as well as any state that the motor system
          needs for operation.
    """

    def convert_motor_state(self) -> Dict[AgentID, Any]:
        """Convert the motor state into something that can be pickled/saved to JSON.

        i.e. substitute vector and quaternion objects; note e.g. copy.deepcopy does not
        work.

        Returns:
            Copy of the motor state.
        """
        state_copy: Dict[AgentID, Any] = {}
        for agent_id in self.keys():
            agent_state = self[agent_id]
            sensors = {}
            for sensor_id in agent_state.sensors.keys():
                sensor_state = agent_state.sensors[sensor_id]
                sensors[sensor_id] = {
                    "position": np.array(list(sensor_state.position)),
                    "rotation": [sensor_state.rotation.real]
                    + list(sensor_state.rotation.imag),
                }
            state_copy[agent_id] = {
                "position": np.array(list(agent_state.position)),
                "rotation": [agent_state.rotation.real]
                + list(agent_state.rotation.imag),
                "sensors": sensors,
            }

        return state_copy
