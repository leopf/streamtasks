---
title: Environment Variables 
---

# Environment Variables
`NODE_NAME` (optional, default: hostname) - node name. It is used to set up a unix socket on the machine that other processes can connect to. It also is used for deterministic ID generation. 

Example: the generation of TaskHost IDs, which must always be the same in order to maintain data consistancy accross restarts, but must also differ between machines in order to be able to create multiple tasks of the same type, running on different machines.

`DATA_DIR` (optional, default to the user app data directory) - The directory to store data like user data and external dependencies.

## Debugging
`DEBUG_MEDIA` - Debugging media timing and synchronization.

`DEBUG_MIXER` - Debugging the audio mixer

`DEBUG_SER` - debug serialization by serializing and deserializing every message sent or received by a link.
