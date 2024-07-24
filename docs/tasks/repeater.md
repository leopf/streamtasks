---
module: streamtasks.system.tasks.repeater
title: Repeater
parent: Tasks
---
# Repeater

## Inputs
* **input**: The input data to be repeated.

## Outputs
* **output**: The repeated data.

## Configuration
The task can be configured using the following fields:
* **Rate** The rate at which to repeat the input (in Hz).
* **Fail Closed** Determines if the previous message should be repeated if the new message is invalid (no=fail closed, yes=fail open).

## Description
A repeater that repeats the input data at a specified rate. If the input is invalid and Fail Closed is enabled, it will not repeat any data until valid input is received again.