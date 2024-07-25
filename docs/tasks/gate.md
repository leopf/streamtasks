---
module: streamtasks.system.tasks.gate
title: Gate
parent: Tasks
---
# Gate

## Inputs
* **Input**: The input data to be passed through the gate, if it is open.
* **Control**: A number input that controls the gate's state (open if >0.5, otherwise closed).

## Outputs
* **Output**: The output data from the gate.

## Configuration
* **Fail Mode**: Determines how the gate behaves when it fails to open or close. Can be either "closed" (default) or "open".
* **Synchronized**: If true, the input topics are synchronized by time and the control topic will have priority over the input topic. This means that if there are two messages with the same timestamp, it will first process the control message.
* **Initial Control**: The initial state of the gate.

## Description
A gate which allows blocking messages or letting them pass through. 
The gate will pass through any valid input data if it is open and not paused.