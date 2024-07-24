---
module: streamtasks.system.tasks.ui.statusdisplay
title: Status Display
grand_parent: Tasks
parent: UI Tasks
---
# Status Display

## Inputs
* **value**: A number input used to display the status

## Outputs
None

## Configuration
The task can be configured using the following fields:
* **Text Above** Text to display when the value is above the threshold.
* **Color Above** Color of the text when the value is above the threshold.
* **Text Below** Text to display when the value is below the threshold.
* **Color Below** Color of the text when the value is below the threshold.
* **Threshold** The value at which the status changes.

## Description
A simple status display task that updates its display based on a number input. It will show different text and colors depending on whether the value is above or below the configured threshold.