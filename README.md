# Streamtasks
 Streamtasks is a system to run distributed tasks at scale that need to communicate in real time.

 ## The networking system
 To allow for real time communication accross different devices, there is a serperate networking system that has two modes of communication:
 - topic based, one client can publish a topic and one or more clients can subscribe to it.
 - addressed: this is similar to TCP/UDP based communication, where clients can have addresses and can send packets to different addresses and ports.

 The communication over this networking system is transport agnostic. 
 This means, that the communication does not differ, if it is between processes, inside a single process or accross a LAN or the Internet.

 ## Task System
 The task system consists of 3 parts.
 - the task itself
 - the task host, responsible for starting tasks and communicating with the management system
 - the task management system, which is responsible for managing running tasks and for communicating with the task hosts

Task host can live in seperate processes and connect to the system via IPC. 
This means, you can start the same host twice. 
If you do this, you must change the host name of the second task host, otherwise the task host will fail to register to the management system.

The task management system organizes running tasks in namespaces and is responsible for tracking errors of the tasks and propagating them to other systems. 
