import asyncio
import sys
import logging
import pathlib
import os
from client_mode import Client
from datetime import datetime
import re


class Server:
    def __init__(self, ip: str, port: int, loop: asyncio.AbstractEventLoop):
        self.__ip: str = ip
        self.__port: int = port
        self.__loop: asyncio.AbstractEventLoop = loop
        self.__logger: logging.Logger = self.initialize_logger()
        self.__clients: dict[asyncio.Task, Client] = {}

        self.logger.info(f"Server Initialized with {self.ip}:{self.port}")

    @property
    def ip(self):
        return self.__ip

    @property
    def port(self):
        return self.__port

    @property
    def loop(self):
        return self.__loop

    @property
    def logger(self):
        return self.__logger

    @property
    def clients(self):
        return self.__clients

    def initialize_logger(self):
        path = pathlib.Path(os.path.join(os.getcwd(), "logs"))
        path.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger('Server')
        logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        fh = logging.FileHandler(
            filename=f'logs/{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}_server.log'
        )
        ch.setLevel(logging.INFO)
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '[%(asctime)s] - %(levelname)s - %(message)s'
        )

        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)

        return logger

    def start_server(self):
        try:
            self.server = asyncio.start_server(
                self.accept_client, self.ip, self.port
            )
            self.loop.run_until_complete(self.server)
            self.loop.run_forever()
        except Exception as e:
            self.logger.error(e)
        except KeyboardInterrupt:
            self.logger.warning("Keyboard Interrupt Detected. Shutting down!")

        self.shutdown_server()

    def accept_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        client = Client(client_reader, client_writer)
        task = asyncio.Task(self.incoming_client_message_cb(client))
        self.clients[task] = client

        client_ip = client_writer.get_extra_info('peername')[0]
        client_port = client_writer.get_extra_info('peername')[1]
        self.logger.info(f"New Connection: {client_ip}:{client_port}")

        task.add_done_callback(self.disconnect_client)

    async def incoming_client_message_cb(self, client: Client):
        while True:
            client_message = await client.get_message()

            if client_message.startswith("quit"):
                break
            elif client_message.startswith("/"):
                self.handle_client_command(client, client_message)
            else:
                self.broadcast_message(
                    f"{client.nickname}: {client_message}".encode('utf8'), [client])

            self.logger.info(f"{client_message}")

            await client.writer.drain()

        self.logger.info("Client Disconnected!")

    def handle_client_command(self, client: Client, client_message: str):
        client_message = client_message.replace("\n", "").replace("\r", "")

        if client_message.startswith("/nick"):
            split_client_message = client_message.split(" ")
            if len(split_client_message) >= 2:
                client.nickname = split_client_message[1]
                client.writer.write(
                    f"Nickname changed to {client.nickname}\n".encode('utf8'))
                return

        client.writer.write("Invalid Command\n".encode('utf8'))

    def broadcast_message(self, message: bytes, exclusion_list):

        for client in self.clients.values():
            if client not in exclusion_list:
                client.writer.write(message)

    def disconnect_client(self, task: asyncio.Task):
        client = self.clients[task]

        self.broadcast_message(
            f"{client.nickname} has left!".encode('utf8'), [client])

        del self.clients[task]
        client.writer.write('quit'.encode('utf8'))
        client.writer.close()
        self.logger.info("End Connection")

    def shutdown_server(self):
        self.logger.info("Shutting down server!")
        for client in self.clients.values():
            client.writer.write('quit'.encode('utf8'))
        self.loop.stop()


def check_call(call_cli):
    pattern = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    return len(call_cli) == 3 \
        and pattern.match(call_cli[1]) \
        and call_cli[2].isdecimal() and 1024 <= int(call_cli[2]) <= 65535


if __name__ == "__main__":
    if not check_call(sys.argv):
        sys.exit(f"Usage: {sys.argv[0]} HOST_IP PORT")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = Server(sys.argv[1], int(sys.argv[2]), loop)
    asyncio.run(server.start_server())