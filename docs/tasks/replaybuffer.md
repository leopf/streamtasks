---
module: streamtasks.system.tasks.replaybuffer
title: Replay Buffer
parent: Tasks
---
# Replay Buffer

## Inputs
* **input**: The input stream, which will be stored in the buffer.
* **play**: A number input used to start and stop the playback.

## Outputs
* **output**: The output of the replay buffer.

## Configuration
* **Loop**: Whether the replay buffer should loop indefinitely or not.

## Description
A simple replay buffer task that stores incoming data and replays it when triggered by the play input. The loop field determines whether the playback should continue indefinitely or stop after a single iteration.