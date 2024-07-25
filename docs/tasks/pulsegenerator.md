---
module: streamtasks.system.tasks.pulsegenerator
title: Pulse Generator
parent: Tasks
---
# Pulse Generator

## Inputs
None

## Outputs
* **output**: A message with either an ID or timestamp, depending on the configuration.

## Configuration
* **Interval** The time between pulses in seconds.
* **Message Type** Either "id" to generate a unique ID or "ts" to generate a timestamp.

## Description
A task that generates a pulse at regular intervals. The pulse can be either an ID message (with a unique identifier) or a timestamp message (with the current time in milliseconds). The interval between pulses is configurable, and the type of pulse message is also customizable.