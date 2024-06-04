from enum import Enum
import itertools
from typing import Any
import unittest
from streamtasks.net.message.data import RawData
from streamtasks.net.message.structures import NumberMessage
from streamtasks.net.message.types import TopicControlData
from streamtasks.system.tasks.gate import GateConfig, GateState, GateTask, GateFailMode
import asyncio
from tests.shared import full_test
from tests.sim import Simulator
from .shared import TaskTestBase, run_task


class GateSimEvent(Enum):
  SET_GATE_CLOSED = "set gate closed"
  SET_GATE_OPEN = "set gate open"
  SET_GATE_INVALID = "set gate invalid"
  SET_GATE_PAUSED = "set gate paused"
  SET_GATE_UNPAUSED = "set gate unpaused"
  SEND_DATA = "send data"


class GateSim(Simulator):
  def __init__(self, fail_mode: GateFailMode) -> None:
    super().__init__()
    self.state = GateState(True)
    self.fail_mode = fail_mode
    self.expect_receive_data = False

  def get_output(self) -> dict[str, Any]: return {
    "output_paused": self.state.get_output_paused(self.fail_mode),
    "recv_data": self.expect_receive_data
  }
  def get_state(self) -> dict[str, Any]: return self.state.as_dict()
  def eout_changed(self):
    new_out = self.get_output()
    new_out.pop("recv_data", None)
    changed = self.last_eout != new_out
    self.last_eout = new_out
    return changed

  def update_state(self, event: GateSimEvent):
    self.expect_receive_data = False
    if event == GateSimEvent.SEND_DATA:
      self.expect_receive_data = self.state.get_open(self.fail_mode)
    elif event == GateSimEvent.SET_GATE_CLOSED:
      self.state.control = False
      self.state.control_errored = False
    elif event == GateSimEvent.SET_GATE_OPEN:
      self.state.control = True
      self.state.control_errored = False
    elif event == GateSimEvent.SET_GATE_INVALID:
      self.state.control_errored = True
    elif event == GateSimEvent.SET_GATE_PAUSED:
      self.state.control_paused = True
    elif event == GateSimEvent.SET_GATE_UNPAUSED:
      self.state.control_paused = False


class TestGate(TaskTestBase):
  async def asyncSetUp(self):
    await super().asyncSetUp()
    # since we are outside the task the in/outs are flipped
    self.gate_topic = self.client.out_topic(101)
    self.in_topic = self.client.out_topic(100)
    self.out_topic = self.client.in_topic(102)

  def start_gate(self, fail_mode: GateFailMode):
    task = GateTask(self.worker_client, GateConfig(
      fail_mode=fail_mode,
      in_topic=self.in_topic.topic,
      control_topic=self.gate_topic.topic,
      out_topic=self.out_topic.topic,
      synchronized=False,
      initial_control=True
    ))
    self.tasks.append(asyncio.create_task(run_task(task)))
    return task

  async def send_input_data(self, value: float):
    self.timestamp += 1
    await self.in_topic.send(RawData(NumberMessage(timestamp=self.timestamp, value=value).model_dump()))

  async def send_gate_data(self, value: float):
    self.timestamp += 1
    await self.gate_topic.send(RawData(NumberMessage(timestamp=self.timestamp, value=value).model_dump()))

  async def send_gate_invalid(self):
    self.timestamp += 1
    await self.gate_topic.send(RawData({
      "timestamp": self.timestamp
    }))

  async def send_gate_pause(self, paused: bool):
    self.timestamp += 1
    await self.gate_topic.set_paused(paused)

  async def send_input_pause(self, paused: bool):
    self.timestamp += 1
    await self.in_topic.set_paused(paused)

  def generate_events(self): return itertools.islice(Simulator.generate_events(list(GateSimEvent)), 100)

  async def _test_fail_mode(self, fail_mode: GateFailMode):
    async with asyncio.timeout(100), self.in_topic, self.gate_topic, self.out_topic:
      self.client.start()
      self.start_gate(fail_mode)
      await self.out_topic.set_registered(True)
      await self.in_topic.set_registered(True)
      await self.gate_topic.set_registered(True)
      await self.in_topic.wait_requested()
      await self.gate_topic.wait_requested()

      sim = GateSim(fail_mode)
      sim.eout_changed() # init last eout

      for event in self.generate_events():
        assert event in GateSimEvent
        if event == GateSimEvent.SEND_DATA: await self.send_input_data(1337)
        if event == GateSimEvent.SET_GATE_CLOSED: await self.send_gate_data(0)
        if event == GateSimEvent.SET_GATE_OPEN: await self.send_gate_data(1)
        if event == GateSimEvent.SET_GATE_INVALID: await self.send_gate_invalid()
        if event == GateSimEvent.SET_GATE_PAUSED: await self.send_gate_pause(True)
        if event == GateSimEvent.SET_GATE_UNPAUSED: await self.send_gate_pause(False)
        sim.on_event(event)
        if sim.eout_changed() or sim.expect_receive_data:
          data = await sim.wait_or_fail(self.out_topic.recv_data_control())
          sim.on_output({
            "output_paused": self.out_topic.is_paused,
            "recv_data": not isinstance(data, TopicControlData)
          })
        else: sim.on_idle()

  async def test_gate_fail_open(self): await self._test_fail_mode(GateFailMode.OPEN)
  async def test_gate_fail_closed(self): await self._test_fail_mode(GateFailMode.CLOSED)

@full_test
class TestGateFull(TestGate):
  def generate_events(self): return Simulator.generate_events(list(GateSimEvent))

if __name__ == "__main__":
  unittest.main()
