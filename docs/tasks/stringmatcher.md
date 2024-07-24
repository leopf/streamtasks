---
module: streamtasks.system.tasks.stringmatcher
title: String Matcher
parent: Tasks
---
# String Matcher

## Inputs
* **input**: A text message to be matched against a pattern.

## Outputs
* **output**: A number message indicating whether the input matches the pattern (1) or does not match (0).

## Configuration
The task can be configured using the following fields:
* **Pattern to Match**: The string to match against.
* **Regular Expression Flags**: Optional flags for the regular expression. (i.e. case insensitive, etc.)
* **Is Regular Expression**: Whether the pattern is a regular expression or not.

## Description
A simple text matcher task that sends a number message indicating whether an input text matches a specified pattern. If the pattern is a regular expression, it can be used with optional flags for case sensitivity and other options.