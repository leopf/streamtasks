---
module: streamtasks.system.tasks.media.audioinput
title: Audio Input
grand_parent: Tasks
parent: Media Tasks
---
# Audio Input

## Inputs
None

## Outputs
* **output**: The raw audio data from the input device

## Configuration
The task can be configured using the following fields:
* **Sample Format** Format of the output audio (e.g. s16, float32)
* **Channels** Number of channels in the output audio
* **Sample Rate** Sample rate of the output audio
* **Input ID** Index or ID of the input device to use (-1 to automatically select)
* **Audio Buffer Size** size of the audio chunks received from the input device

## Description
A task that reads audio from an input device like a microphone and sends it to an output topic. 