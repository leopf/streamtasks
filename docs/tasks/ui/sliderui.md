---
module: streamtasks.system.tasks.ui.sliderui
parent: UI Tasks
grand_parent: Tasks
title: Slider UI
---
# Slider UI

## Inputs
None

## Outputs
* **output**: The current value of the slider as a number message.

## Configuration
The task can be configured using the following fields:
* **Label** Label of the slider element
* **Default Value** initial and fallback value
* **Minimum Value** minimum value of the slider
* **Maximum Value** maximim value of the slider

## Description
A simple slider UI task that sends a value to an output topic when the user interacts with it.