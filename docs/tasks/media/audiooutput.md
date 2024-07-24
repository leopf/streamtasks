---
module: streamtasks.system.tasks.media.audiooutput
title: Audio Output
grand_parent: Tasks
parent: Media Tasks
---
# Audio Output

## Inputs
* **input**: The audio data to be output, in raw format.

## Outputs
None

## Configuration
The task can be configured using the following fields:
* **Sample Format** Format of the output audio (e.g. s16, float32)
* **Channels** Number of channels in the output audio
* **Sample Rate** Sample rate of the output audio
* **Output ID/Device Index**: The index of the output device to use for playback 
* **Audio Buffer Size** size of the audio chunks sent to the output device.
(optional, defaults to automatic selection).

## Description
A task that takes audio data from an input and outputs it to a specified output device.
