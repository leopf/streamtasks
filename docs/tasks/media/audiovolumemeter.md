---
module: streamtasks.system.tasks.media.audiovolumemeter
title: Audio Volume Meter
grand_parent: Tasks
parent: Media Tasks
---
# Audio Volume Meter

## Inputs
* **audio**: The input audio stream, which is expected to be a raw audio signal with one channel (mono).

## Outputs
* **volume**: The average volume of the input audio signal over the specified time window. It is represented as a number between 0 and 1.

## Configuration
* **Sample Rate** Sample rate of the input audio
* **Sample Format** Format of the input audio
* **Time Window**: The time window over which to calculate the average volume (in milliseconds).

## Description
The Audio Volume Meter task calculates the average volume of an audio signal over a specified time window. It takes in an audio stream, processes it in real-time, and outputs the calculated volume as a number.
