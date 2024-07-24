---
module: streamtasks.system.tasks.namedinput
title: Named Input
parent: Tasks
---
# Named Input

## Inputs
None

## Outputs
* **output**: The data from the named topic including control messages (pause/unpause)

## Configuration
* **Name** Name of the named topic

## Description
A task that connects to a named topic and forwards its data to an output. If the named topic is paused, control messages (pause/unpause) are forwarded.