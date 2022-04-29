from typing import Dict, List
from dotenv import load_dotenv
import os
import time
import socket
import threading
from termcolor import colored
from logger import Logger

from messages import (
    ClientInitMessage,
    ClientInitResponse,
    ClientMessage,
    ClientToServerMessage,
    Message, 
    MessageType,
    ServerEndGameMessage,
    ServerForceTerminateMessage,
    ServerInitMessage,
    ServerStartDualPlayMessage,
    ServerStartSoloPlayMessage,
    ServerUpdateClientMessage,
)
from socket_reader import SocketReader

from rich.console import Console
from rich.table import Table


class GameType:
    SOLO = 0
    DUAL = 1


class SocketContainer:
    def __init__(self, socket_obj, address):
        self.socket: socket.socket = socket_obj
        self.address = address
    
    def __repr__(self):
        return self.address


class Client(SocketContainer):
    class Status:
        IN_MENU = 0
        WAITING_FOR_SOLO = 1
        WAITING_FOR_DUAL = 2
        WAITING_FOR_OPPONENT = 3
        PLAYING_SOLO = 4
        PLAYING_DUAL = 5


    class OnlineStatus:
        ONLINE = 0
        TIMEOUT = 1


    def __init__(self, client_socket, address, username):
        super().__init__(client_socket, address)
        self.server: Server = None

        self.status: Client.Status = self.Status.IN_MENU

        self.username = username

        self.wins: int = 0
        self.ties: int = 0
        self.losses: int = 0

        self.online_status = self.OnlineStatus.ONLINE
    
    def __repr__(self):
        return self.username
    
    def get_dict_for_server(self):
        return {
            "username": self.username,
            "address": self.address,
        }
    

class Server(SocketContainer):
    ID = 1

    def __init__(self, server_socket, address):
        super().__init__(server_socket, address)
        self.clients: List[Client] = []
        self.ID = Server.ID
        Server.ID += 1

    def __repr__(self):
        return f"Server#{self.ID}" #super().__repr__() + " - Clients: " + str(self.clients)


class WebServer:
    TERMINATE_TIMEOUT_DURATION = 20

    def __init__(self, host, port):
        self._logger: Logger = Logger()

        self._logger.green("WebServer initialized successfully. See /help for list of command")

        self.clients: List[Client] = []
        self.address_to_clients_dict: Dict[str, Client] = {}
        self.username_to_clients_dict: Dict[str, Client] = {}

        self.waiting_clients_for_solo_play: List[Client] = []
        self.waiting_clients_for_dual_play: List[Client] = []

        self.servers: List[Server] = []
        self.waiting_server_for_dual_play: Server = None
        self.free_servers: List[Server] = []

        self._logger.green("Waiting Queues initialized successfully")
        
        self._host = host
        self._port = port
        self._init_socket()

        self.lock: threading.Lock = threading.Lock()
    

    def _init_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self._host, self._port))
        self.socket.listen()

        self._logger.green("Socket initialized successfully")
    

    def _init_solo_game(self, server: Server, client: Client):
        client.server = server
        server.clients = [client]

        client.status = client.Status.PLAYING_SOLO

        client.socket.send((colored("You have been assigned to a server. Enjoy!", "green") + "\n").encode())

        server.socket.send(ServerStartSoloPlayMessage(client=client.get_dict_for_server()).serialize().encode())

        self._logger.cyan(f"Client \"{client.username}\" was assigned to server {server.address}")
        self._logger.green(f"Solo game for client \"{client.username}\" initialized in server {server.address}")
    

    def _init_waiting_dual_game(self, server: Server, client: Client):
        self.waiting_server_for_dual_play = server

        client.server = server
        server.clients = [client]

        client.status = client.Status.WAITING_FOR_DUAL

        client.socket.send(colored("You have been assigned to a server. Waiting for opponent...\n", "cyan").encode())

        self._logger.cyan(f"Client \"{client.username}\" was assigned to server {server.address}")
        self._logger.green(f"Client \"{client.username}\" is waiting in the server {server.address} for a dual game")
    

    def _assign_server_to_two_players_for_dual_game(self, server: Server):
        client1, client2 = [self.waiting_clients_for_dual_play.pop() for _ in range(2)]

        server.clients = [client1, client2]

        for c in server.clients:
            c.status = Client.Status.PLAYING_DUAL
            c.server = server
            c.socket.send(colored("You have been assigned to a server. Waiting for opponent...\n", "cyan").encode())
            c.socket.send(colored("Opponent has been found. Your game starts now!\n").encode())
        
        server.socket.send(ServerStartDualPlayMessage(clients=[c.get_dict_for_server() for c in server.clients]).serialize().encode())

        self._logger.cyan(f"Clients \"{client1.username}\" and \"{client2.username}\" have been assigned to server {server.address}")
        self._logger.green(f"A dual game between \"{server.clients[0].username}\" and \"{server.clients[1].username}\" initialized in server {server.address}")


    def _assign_available_server(self, server: Server):
        self.lock.acquire()

        if len(self.waiting_clients_for_solo_play) != 0:
            self._init_solo_game(server=server, client=self.waiting_clients_for_solo_play.pop())
        elif len(self.waiting_clients_for_dual_play) != 0:
            if len(self.waiting_clients_for_dual_play) >= 2:
                self._assign_server_to_two_players_for_dual_game(server)
            else:
                self._init_waiting_dual_game(server=server, client=self.waiting_clients_for_dual_play.pop())
        else:
            server.clients = []
            self.free_servers.append(server)

        self.lock.release()


    def _init_new_server(self, server_socket, address):
        server_socket.send((colored("Successfully connected to the WebServer.", "green") + "\n").encode())

        server = Server(server_socket, address)

        self.servers.append(server)

        self._logger.green(f"{server} [{server.address}] initialized successfully")

        self._assign_available_server(server)

        return server
    

    def _handle_server_end_game(self, server: Server, message: ServerEndGameMessage):
        self._logger.green(f"Game in the server {server.address} ended")

        if message.is_tie:
            for c in server.clients:
                c.ties += 1
        elif message.winner_address is not None:
            if len(server.clients) == 1:
                server.clients[0].wins += 1
            else:
                client_winner = self.address_to_clients_dict[message.winner_address]
                client_loser = server.clients[0] if server.clients[0] != client_winner else server.clients[1]
                client_winner.wins += 1
                client_loser.losses += 1
        else:
            server.clients[0].losses += 1
        for c in server.clients:
            c.server = None
            c.status = Client.Status.IN_MENU
            c.socket.send(self._get_client_menu().encode())
        server.clients = []
        self._assign_available_server(server)


    def _handle_server(self, server: Server):
        while True:
            msg_obj: Message = Message.deserialize(SocketReader(server.socket).read_json())
            if msg_obj.message_type == MessageType.SERVER_END_GAME:
               self._handle_server_end_game(server, msg_obj)
            elif msg_obj.message_type == MessageType.SERVER_TO_CLIENT_MESSAGE:
                self.address_to_clients_dict[msg_obj.client_address].socket.send(msg_obj.message.encode())
            else:
                self._logger.red("Wrong message type. It should be of type ServerToClientMessage or ServerEndGameMessage")


    def _get_client_menu(self):
        return colored("\n".join([line.strip() for line in """
        ┏━ Menu ━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┣━━━  /solo : Play with computer   ┃
        ┣━━━  /dual : Play with opponent   ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
        """.split("\n") if line.strip() != ""]), "yellow") + "\n"


    def _init_new_client(self, client_socket, address, msg: ClientInitMessage):
        self._logger.blue(f"New client connected. [Address: {address} - Username: {msg.username}]")

        client_socket.send((colored("Successfully connected to the WebServer.", "green") + "\n").encode())

        client = Client(client_socket, address, msg.username)

        self.clients.append(client)
        self.address_to_clients_dict[address] = client
        self.username_to_clients_dict[msg.username] = client

        client.socket.send(self._get_client_menu().encode())

        self._logger.green(f"Client \"{client.username}\" initialized successfully")

        return client
    

    def _put_client_on_wait(self, client: Client, game_type: GameType):
        client.server = None

        if game_type == GameType.SOLO:
            client.status = client.Status.WAITING_FOR_SOLO
            self.waiting_clients_for_solo_play.append(client)
            
            self._logger.cyan(f"Client \"{client.username}\" added to the waiting queue for solo game")
        elif game_type == GameType.DUAL:
            client.status = client.Status.WAITING_FOR_DUAL
            self.waiting_clients_for_dual_play.append(client)

            self._logger.cyan(f"Client \"{client.username}\" added to the waiting queue for dual game")
        else:
            self._logger.red("Invalid game_type")
            raise Exception("Invalid game_type")

        client.socket.send(colored("You will be assigned to a server ASAP. Please wait... (/exchange to change the playing mode)\n", "cyan").encode())


    def _add_client_to_waiting_dual_game_server(self, client: Client):
        server = self.waiting_server_for_dual_play
        self.waiting_server_for_dual_play = None

        client.server = server
        server.clients.append(client)

        client.status = client.Status.PLAYING_DUAL
        server.clients[0].status = client.Status.PLAYING_DUAL

        for c in server.clients:
            c.socket.send(colored("Opponent has been found. Your game starts now!\n", "cyan").encode())

        server.socket.send(ServerStartDualPlayMessage(clients=[c.get_dict_for_server() for c in server.clients]).serialize().encode())

        self._logger.blue(f"Client \"{client.username}\" was assigned to server {server.address}")
        self._logger.cyan(f"Client \"{client.username}\" is waiting for an opponent in the server {server.address}")


    def _assign_available_client(self, client: Client, game_type: GameType):
        self.lock.acquire()

        if game_type == GameType.SOLO:
            if len(self.free_servers) != 0:
                self._init_solo_game(server=self.free_servers.pop(), client=client)
            else:
                self._put_client_on_wait(client, GameType.SOLO)
        elif game_type == GameType.DUAL:
            if self.waiting_server_for_dual_play is not None:
                self._add_client_to_waiting_dual_game_server(client)
            elif len(self.free_servers) != 0:
                self._init_waiting_dual_game(server=self.free_servers.pop(), client=client)
            else:
                self._put_client_on_wait(client, GameType.DUAL)
        else:
            self._logger.red("Invalid type for game_type")

        self.lock.release()
    

    def _remove_client(self, client: Client):
        self.clients.remove(client)
        del self.address_to_clients_dict[client.address]
        del self.username_to_clients_dict[client.username]
    

    def _terminate_timed_out_client(self, client: Client):
        self._logger.yellow(f"Client \"{client.username}\" timed out while playing. It will be removed after {self.TERMINATE_TIMEOUT_DURATION} seconds")
        
        cnt =  0
        while cnt < self.TERMINATE_TIMEOUT_DURATION:
            time.sleep(0.5)
            cnt += 1 
            if client.online_status == Client.OnlineStatus.ONLINE:
                self._logger.yellow(f"Timed out client \"{client.username}\" returned to the server and won't be removed.")
                return
            elif client.username not in self.username_to_clients_dict:
                self._logger.blue(f"Timed out client \"{client.username}\" has already removed from the server")
                return


        removed_opponent = None
        if client.status == client.Status.PLAYING_SOLO:
            client.server.clients = []
            self.waiting_server_for_dual_play = None
            client.server.socket.send(ServerForceTerminateMessage().serialize().encode())
            self._assign_available_server(client.server)
        elif client.status == client.Status.PLAYING_DUAL:
            client_opponent = client.server.clients[0] if client.server.clients[0] != client else client.server.clients[1]
            client.server.clients = []
            client.server.socket.send(ServerForceTerminateMessage().serialize().encode())
            if client_opponent.online_status == Client.OnlineStatus.ONLINE:
                client_opponent.socket.send(colored("Your opponent left the game.\n", "cyan").encode())
                self._assign_available_client(client_opponent, GameType.DUAL)
            else:
                self._remove_client(client_opponent)
                removed_opponent = client_opponent

            self._assign_available_server(client.server)
    
        self._remove_client(client)

        self._logger.red(f"Timed out client \"{client.username}\" removed")
        if removed_opponent is not None:
            self._logger.red(f"Timed out {client.username}'s opponent \"{client.username}\" also removed")


    def _handle_client_connection_lost(self, client: Client):
        client.socket.close()
        
        if client.status == Client.Status.IN_MENU:
            self._remove_client(client)
        if client.status == Client.Status.WAITING_FOR_DUAL:
            self.waiting_clients_for_dual_play.remove(client)
            self._remove_client(client)
        elif client.status == Client.Status.WAITING_FOR_SOLO:
            self.waiting_clients_for_solo_play.remove(client)
            self._remove_client(client)
        elif client.status == Client.Status.WAITING_FOR_OPPONENT:
            client.server.clients = []
            self.waiting_server_for_dual_play = None
            self._assign_available_server(client.server)
        elif client.status in {Client.Status.PLAYING_SOLO, Client.Status.PLAYING_DUAL}:
            client.online_status = client.OnlineStatus.TIMEOUT
            threading.Thread(target=self._terminate_timed_out_client, args=[client]).start()
        

        self._logger.red(f"Client [Address: {client.address} - Username: {client.username}] disconnected.")

    
    def _validate_username(self, username):
        if username not in self.username_to_clients_dict:
            return True
        if self.username_to_clients_dict[username].online_status == Client.OnlineStatus.TIMEOUT:
            return True
        return False
    

    def _get_valid_username_from_client(self, init_msg: ClientInitMessage, socket_obj: socket.socket):
        while not self._validate_username(init_msg.username):
            socket_obj.send(ClientInitResponse(
                is_valid=False,
                message=colored("Username already exists. Try another one", "red")+"\n"
            ).serialize().encode())

            init_msg = Message.deserialize(SocketReader(socket_obj).read_json())

            if type(init_msg) != ClientInitMessage:
                self._logger.red("Incoming client didn't follow the prototype for initialization. Socket terminated")
                socket_obj.close()
                return None
        
        return init_msg


    def _reconnect_client(self, init_msg: ClientInitMessage, socket_obj: socket.socket, address: str):
        self._logger.blue(f"Client [Address: {address} - Username: {init_msg.username}] reconnected to the server")

        socket_obj.send((colored("Successfully connected to the WebServer.", "green") + "\n").encode())

        client = self.username_to_clients_dict[init_msg.username]
        client.socket = socket_obj
        client.online_status = Client.OnlineStatus.ONLINE

        del self.address_to_clients_dict[client.address]
        client.address = address
        self.address_to_clients_dict[address] = client

        if client.status == Client.Status.PLAYING_SOLO or client.status == Client.Status.PLAYING_DUAL:
            client.server.socket.send(ServerUpdateClientMessage(client=client.get_dict_for_server()).serialize().encode())

        return client


    def _handle_client(self, init_msg: ClientInitMessage, socket_obj: socket.socket, address: str):
        init_msg = self._get_valid_username_from_client(init_msg, socket_obj)
        if init_msg is None:
            return

        socket_obj.send(ClientInitResponse(is_valid=True, message=colored("Username accepted by the webserver", "green")).serialize().encode())
        
        if init_msg.username in self.username_to_clients_dict:
            client = self._reconnect_client(init_msg, socket_obj, address)
        else:
            client = self._init_new_client(socket_obj, address, init_msg)


        while True:
            try:
                msg_obj = Message.deserialize(SocketReader(client.socket).read_json())

                if type(msg_obj) != ClientMessage:
                    self._logger.red("Wrong message type. It should be of type ClientMessage")
                    raise Exception("Wrong message type. It should be of type ClientMessage")
                
                msg = msg_obj.message

                if msg == "/users":
                    client.socket.send((colored("Users online: " + str(len(self.clients)), "magenta") + "\n").encode())
                elif client.status == client.Status.IN_MENU:
                    if msg == "/solo":
                        self._assign_available_client(client, GameType.SOLO)
                    elif msg == "/dual":
                        self._assign_available_client(client, GameType.DUAL)
                    else:
                        client.socket.send((colored("Invalid input\n", "red") + self._get_client_menu()).encode())
                elif client.status in {client.Status.PLAYING_SOLO, client.Status.PLAYING_DUAL}:
                    client.server.socket.send(ClientToServerMessage(client.address, msg).serialize().encode())
                else:
                    if msg == "/exchange":
                        self._logger.cyan(f"Client \"{client.username}\" used /exchange command")
                        if client.status == client.Status.WAITING_FOR_DUAL:
                            self.waiting_clients_for_dual_play.remove(client)
                            self._logger.cyan(f"Client \"{client.username}\" was removed from waiting queue of dual games")
                        elif client.status == client.Status.WAITING_FOR_SOLO:
                            self.waiting_clients_for_solo_play.remove(client)
                            self._logger.cyan(f"Client \"{client.username}\" was removed from waiting queue of solo games")
                        elif client.status == client.Status.WAITING_FOR_OPPONENT:
                            self._logger.cyan(f"Client \"{client.username}\" is no longer looking for opponent for dual game")
                            client.server.clients = []
                            self.waiting_server_for_dual_play = None
                            self._logger.cyan(f"Server {client.server.address} is no longer assigned to \"{client.username}\"")
                            self._assign_available_server(client.server)
                            client.server = None
                        else:
                            raise Exception("Why here?!")
                        client.status = client.Status.IN_MENU
                        client.socket.send(self._get_client_menu().encode())
                    else:
                        client.socket.send(colored("You will be assigned to a server ASAP. Please wait... (/exchange to change the playing mode)\n", "cyan").encode())
            except:
                self._handle_client_connection_lost(client)
                return


    def receive_connections(self):
        while True:
            new_socket, new_address = self.socket.accept()
            new_address = f"{new_address[0]}:{new_address[1]}"

            init_msg = Message.deserialize(SocketReader(new_socket).read_json())
            if type(init_msg) == ServerInitMessage:
                self._logger.blue(f"New server connected with address \"{new_address}\"")
                server = self._init_new_server(new_socket, new_address)
                threading.Thread(target=self._handle_server, args=[server]).start()
            elif type(init_msg) == ClientInitMessage:
                threading.Thread(target=self._handle_client, args=[init_msg, new_socket, new_address]).start()
            else:
                new_socket.send(colored(f"Invalid initialization message type. It should be either \"ServerInitMessage\" or \"ClientInitMessage\".\n", "red").encode())


    def _get_clients_by_status(self, status: Client.Status):
        res = []
        for c in self.clients:
            if c.status == status:
                res.append(c)
        return res


    def _get_clients_playing_solo_game(self):
        return self._get_clients_by_status(Client.Status.PLAYING_SOLO)

    
    def _get_clients_playing_dual_game(self):
        return self._get_clients_by_status(Client.Status.PLAYING_DUAL)
    

    def _get_client_waiting_for_opponent(self):
        res = self._get_clients_by_status(Client.Status.WAITING_FOR_DUAL)
        return res[0] if len(res) > 0 else None
    

    def _get_servers_hosting_solo_game(self):
        res = []
        for s in self.servers:
            if len(s.clients) != 0 and s.clients[0].status == Client.Status.PLAYING_SOLO:
                res.append(s)
        return res


    def _get_servers_hosting_dual_game(self):
        res = []
        for s in self.servers:
            if len(s.clients) != 0 and s.clients[0].status == Client.Status.PLAYING_DUAL:
                res.append(s)
        return res
        

    def _print_queues_stat(self):
        clients_stats = [
            "Clients : " + str(self.clients),
            "Clients waiting for solo play : " + str(self.waiting_clients_for_solo_play),
            "Clients waiting for dual play : " + str(self.waiting_clients_for_dual_play),
            "Clients waiting for opponent : " + str(self._get_client_waiting_for_opponent()),
            "Clients playing solo game : " + str(self._get_clients_playing_solo_game()),
            "Clients playing dual game : " + str(self._get_clients_playing_dual_game())
        ]
        servers_stats = [
            "Servers : " + str(self.servers),
            "Free servers : " + str(self.free_servers),
            "Server waiting for opponent : " + str(self.waiting_server_for_dual_play),
            "Servers hosting solo game : " + str(self._get_servers_hosting_solo_game()),
            "Servers hosting dual game : " + str(self._get_servers_hosting_dual_game())
        ]
        max_stat_len = max(list(map(len, clients_stats)) + list(map(len, servers_stats))) + 6

        title = " Queues Stat "
        half_line_len_for_title = (max_stat_len - len(title) + 1) // 2
        print(colored("┏" + "━"*half_line_len_for_title + title + "━"*(max_stat_len - len(title) - half_line_len_for_title + 1) + "┓", "magenta"))
        for stat in clients_stats:
            spaces_len = max_stat_len - len(stat)
            print(colored("┃ " + stat + " "*spaces_len + "┃", "magenta"))
        print(colored("┣" + "━"*(max_stat_len + 1) + "┫", "magenta"))
        for stat in servers_stats:
            spaces_len = max_stat_len - len(stat)
            print(colored("┃ " + stat + " "*spaces_len + "┃", "magenta"))
        print(colored("┗" + "━"*(max_stat_len + 1) + "┛", "magenta"))
    

    def _print_score_board(self):
        table = Table(show_header=True, header_style="bold magenta", border_style="magenta")
        table.add_column("Rank", style="magenta", justify='center')
        table.add_column("Username", justify='center', style="magenta")
        table.add_column("Wins", justify="center", style="magenta")
        table.add_column("Ties", justify="center", style="magenta")
        table.add_column("Losses", justify="center", style="magenta")

        sorted_clients = sorted(self.clients, key=lambda c: (-c.wins, -c.ties, c.losses, c.username))
        for rank, c in enumerate(sorted_clients):
            table.add_row(*map(str, [rank+1, c.username, c.wins, c.ties, c.losses]))

        console = Console()
        console.print(table)


    def handle_console_commands(self):
        while True:
            cmd = input()
            if cmd == "/users":
                print(colored("Users online: " + str(len(self.clients)), "magenta"))
            elif cmd == "/qstat":
                self._print_queues_stat()
            elif cmd == "/scoreboard":
                self._print_score_board()
            elif cmd == "/help":
                print(colored("┏━━━━━━━━━━━━━ Help Menu ━━━━━━━━━━━━━━┓", "yellow"))
                print(colored("┣━━ /users : Number of online users    ┃", "yellow"))
                print(colored("┣━━ /qstat : Stats about queues        ┃", "yellow"))
                print(colored("┣━━ /scoreboard : Scoreboard           ┃", "yellow"))
                print(colored("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛", "yellow"))
            else:
                print(colored("Invalid command. See /help for the list of commands.", "red"))


if __name__ == '__main__':
    load_dotenv()
    
    host = os.getenv("HOST")
    port = int(os.getenv("PORT"))

    web_server = WebServer(host, port)
    threading.Thread(target=web_server.handle_console_commands).start()
    web_server.receive_connections()
