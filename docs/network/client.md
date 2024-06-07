# Client
module: `streamtasks.client`

The client provides a simplified interface for the networking. It provides all basic functions needed to implement services on the network.

A client can be started and stopped. In order to receive data, it must be started.

To receive data receivers are registered in the client that process the messages.

Among the basics the client implements some higher level protocols for convenience.
1. the basics of the discovery protocol (name resolution). This is because of caching and needing a place to store the cached names resolutions.
2. the fetch protocol. This is because the discovery protocol depends on this.

The client must be created by providing a link `Client(link)`.

## Topic
module: `streamtasks.client.topic`

An abstraction layer for individual topics and topic synchronization.

A topic has a state:
* **registered** - if the topic is provided in the network 
* **paused** - if the topic has been paused 

### In Topic
Can be created with `client.in_topic` or `client.sync_in_topic`.

Helps with receiving data and monitoring its state.

The SynchronizedInTopic also allows synchronizing multiple topics with a InTopicSynchronizer.

#### Synchronizers
* **SequentialInTopicSynchronizer** - synchronizes messages sequentially by their timestamp
* **PrioritizedSequentialInTopicSynchronizer** - like **SequentialInTopicSynchronizer**, but allows for setting a topic priority in case two messages have the same timestamp

### Out Topic
Can be created with `client.out_topic`.

Helps with sending data and changing its state.

## protocols
Besides the protocols directly implemented in the client the streamtasks.client module also provides other basic protocols and abstractions.

### Fetch
module: `streamtasks.client.fetch`

A fetching (RPC) protocol. Servers can handle requests sent to them with a descriptor (name of the procedure) and return a result.

### Broadcast
module: `streamtasks.client.broadcast`

A broadcasting protocol, like websockets, but in the streamtasks network.

### Discovery
module: `streamtasks.client.discovery`

Functions:
* register/discover address names (like DNS)
* register/discover topics spaces (namespaces for topics)
* generate addresses, to avoid address collisions
* generate broadcasting topics, to avoid topic collisions

### Signal
module: `streamtasks.client.signal`

Like fetch but without any returning results, allowing for shutdown messages.