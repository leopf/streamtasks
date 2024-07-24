---
module: streamtasks.system.tasks.media.inputcontainer
title: Input Container
parent: Media Tasks
grand_parent: Tasks
---
# Input Container

## Configuration
* **source** (label: "Source path or url")
	* Description: The source file or URL from which the task will read input data.
* **real_time** (label: "Real-time")
	* Description: A boolean flag indicating whether the task should output data in real-time or as it is available. This is useful for file inputs, which are fully available immediately but should be processed in real time.
* **container_options** (label: "Container options")
	* Description: Options for the container format, such as encoding settings. These are [ffmpeg](https://ffmpeg.org/ffmpeg.html) options.

## Description
It reads media data from a source (e.g., file or URL) and streams it to one or more output topics. The task can handle multiple video and audio tracks, and it supports real-time streaming. It also allows for transcoding of the media data if necessary.

It is based on [ffmpeg](https://ffmpeg.org/ffmpeg.html) containers. The codec and container options correspond to those in [ffmpeg](https://ffmpeg.org/ffmpeg.html).
