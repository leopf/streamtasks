# Client

Among the basics the client implements some higher level protocols for convenience.
1. the basics of the discovery protocol (name resolution). This is because of caching and needing a place to store the cached names resolutions.
2. the fetch protocol. This is because the discovery protocol depends on this.