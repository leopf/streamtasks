---
module: streamtasks.system.tasks.ui.textdisplay
title: Text Display
grand_parent: Tasks
parent: UI Tasks
---
# Text Display

## Inputs
* **value**: The text to be displayed.

## Outputs
None

## Description
Displays the incoming text messages. It can append new messages to the end of the current text, or replace it entirely. The maximum length of the displayed text is configurable, and if set to -1, there will be no limit.