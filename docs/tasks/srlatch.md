---
module: streamtasks.system.tasks.srlatch
title: SR Latch
parent: Tasks
---
# SR Latch

## Inputs
* **set**: Set the latch value high.
* **reset**: Reset the latch value low.

## Outputs
* **output**: The current state of the latch (high or low).

## Configuration
The task can be configured using the following fields:
* **Default Value** initial value
* **Synchronized** if true, receive messages from set and reset topics in a synchronized manner.

## Description
A SR-Latch. It can be set and reset by sending a value greater than 0.5 to either the set or reset inputs.

The output value (current state) is sent when any value is received on either the set or reset input.