---
module: streamtasks.system.tasks.media.audioresampler
title: Audio Resampler
grand_parent: Tasks
parent: Media Tasks
---
# Audio Resampler

## Inputs
* **input**: raw audio

## Outputs
* **output**: raw resampled audio

## Configuration
The task can be configured using the following fields:
* **Input Sample Format**: The format of the input audio samples (e.g. s16, u8).
* **Input Sample Rate**: The rate of the input audio samples.
* **Input Channels**: The number of channels in the input audio data.
* **Output Sample Format**: The format of the output audio samples.
* **Output Sample Rate**: The rate of the output audio samples.
* **Output Channels**: The number of channels in the output audio data.

## Description
A task that resamples audio from one format to another.

### Example Use Case
Resample 32000 Hz mono audio to 44100 Hz stereo.