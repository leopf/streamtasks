---
module: streamtasks.system.tasks.inference.asrspeechrecognition
title: ASR Speech Recognition
grand_parent: Tasks
parent: Inference Tasks
---
# ASR Speech Recognition

## Inputs
* **input**: Raw audio data containing the speech

## Outputs
* **output**: Transcribed text from the input audio.

## Configuration
* **source**: The path to a model or the name of a pre-trained model.
* **device**: The device to run the model on (e.g. "cpu" or "cuda").
* **chunk_size**: The size of each chunk of audio data to process.
* **left_context_size**: The number of chunks to consider as context for each chunk.

# Description
Receives audio data and transcribes it.

### Notes
This task uses a pre-trained ASR model from [SpeechBrain](https://github.com/speechbrain/speechbrain) and transcribes the input audio in real-time. It is recommended to use a high-performance device (e.g. GPU) to run this task efficiently.