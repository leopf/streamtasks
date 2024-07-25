---
module: streamtasks.system.tasks.textformatter
title: Text Formatter
parent: Tasks
---
# Text Formatter

## Inputs
* **variables***: The inputs used as variables in the formatted text.

## Outputs
* **output**: The formatted text, with placeholders replaced by actual values from the input variables.

## Description
A task that formats a template string using values from multiple inputs. The template string is defined in the task configuration and can include placeholders for each variable. When new data arrives on any of the input topics, the corresponding placeholder in the output topic will be updated with the new value, any the resulting text will be reemitted to the output.