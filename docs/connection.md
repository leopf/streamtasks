# Connection

module: `streamtasks.connection`

Used to create connections external to the process.

It implements servers and clients for multiple connection methods.

## connecting to a server

The easiest way to connect to a server is to call `connect` with a url. The connect function returns a link connected to the server. It best can be managed with the `AutoReconnector`.

If no url is specified a connection will be made to the unix socket corresponding to the current node name. See [environment variables](env.md "environment variables") for more information about the node name.

The following url schemes are supported:
* `unix:///[some path]` - specify a path to a unix socket
* `tcp://[hostname]:[port]` - specify a tcp connection

When the url string is not a valid url, it will be interpreted as a node node. The node name will then be transformed into a unix socket path with `get_node_socket_path`. A connection will be attempted to this unix socket path.

If a username or password is specified in the url, it will be sent as handshake data. Any query parameter will also be included in the handshake data.

If a query parameter cost, with an integer value is specified, it will be used to set the cost of the connection.

The handshake data can be used to authenticate and configure a connection.

### AutoReconnector
The `AutoReconnector` can be used to reestablish connections when closed. it takes a link connecting to the rest of the system and a connect function returning a link.

It can be run by calling `run`.

## starting a server

Before starting a server a server of a specific type must be created. This can be done by calling `get_server` with a link connecting the server to the rest of the system and a url. The url works the same way it does for the connection. `get_server` returns a `ServerBase`. The server can be started by calling `run`.

In case of TCP servers the hostname and port is used for binding the socket.

In case of Unix socket servers the path is used to create the unix socket.
