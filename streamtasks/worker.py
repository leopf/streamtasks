class Worker:
  node_id: int
  switch: TopicSwitch
  running: bool

  def __init__(self, node_id: int):
    self.node_id = node_id
    self.switch = TopicSwitch()
    self.running = False

  def signal_stop(self):
    self.running = False

  def create_connection(self) -> TopicConnection:
    connector = create_local_cross_connector()
    self.switch.add_connection(connector[0])
    return connector[1]

  def start(self):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.async_start())

  def process(self):
    self.switch.process()

  async def async_start(self):
    self.running = True

    while self.running:
      logging.info(f"Connecting to node {self.node_id}")
      try:
        conn = IPCTopicConnection(Client(get_node_socket_path(self.node_id)))
        logging.info(f"Connected to node {self.node_id}")

        self.switch.add_connection(conn)

        while self.running and not conn.connection.closed:
          self.process()
          await asyncio.sleep(0)
      except ConnectionRefusedError:
        logging.info(f"Connection to node {self.node_id} refused")
        await asyncio.sleep(1)