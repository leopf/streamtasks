---
module: streamtasks.system.tasks.media.outputcontainer
title: Output Container
parent: Media Tasks
grand_parent: Tasks
---
# output container

## Inputs
* destination: specifies the path or URL where the output container will be saved.
* max desynchronization: sets the maximum allowed desynchronization between video and audio tracks.

## Configuration
* **destination path or url**
* **maximum desynchronization**
* **container options**
* per video track:
	+ **pixel format**
	+ **video codec** (+encoder)
	+ **width**
	+ **height**
	+ **frame rate**
* per audio track:
	+ **audio codec** (+encoder)
	+ **sample format**
	+ **sample rate**
	+ **channel count**

### Description
The task is a media output container that takes in a set of video and audio tracks and combines them into a single output container. 

It is based on [ffmpeg](https://ffmpeg.org/ffmpeg.html) containers. The codec and container options correspond to those in [ffmpeg](https://ffmpeg.org/ffmpeg.html).
