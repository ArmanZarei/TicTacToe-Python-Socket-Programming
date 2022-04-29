from typing import Dict, List
from dotenv import load_dotenv
import os
import socket
from game import TicTacToeGame
import numpy as np
from termcolor import colored
import re
from logger import Logger

from messages import (
    ClientToServerMessage,
    Message,
    MessageType,
    ServerEndGameMessage,
    ServerInitMessage,
    ServerStartDualPlayMessage,
    ServerStartSoloPlayMessage,
    ServerToClientMessage
)
from socket_reader import SocketReader


class GameServer:
    class ServerStatus:
        PLAYING_SOLO = 0
        PLAYING_DUAL = 1
        WAITING = 2


    PUT_COMMAND_REGEX = re.compile("^\/put \((\d+), (\d+)\)$")
    MSG_COMMAND_REGEX = re.compile("^\/msg (.+)$")


    def __init__(self, webserver_socket):
        self._socket = webserver_socket

        self._status = self.ServerStatus.WAITING
        self._clients: List[Dict[str, str]] = []
        self._game: TicTacToeGame = None
        self._logger: Logger = Logger()

        self._logger.green("Game Server initialized successfully")


    def _get_game_board_and_turn_as_string(self):
        result = self._game.get_board_as_string()
        result += f"{self._clients[0]['username']}: {self._game.get_sign(1)} | "
        result += f"{self._clients[1]['username'] if len(self._clients) == 2 else 'Computer'}: {self._game.get_sign(2)}\n"
        if self._status == self.ServerStatus.PLAYING_SOLO:
            if self._game.get_turn() == 1:
                result += f"Turn: {self._clients[0]['username']}"
            else:
                result += "Turn: Computer"
        else:
            result += f"Turn: {self._clients[self._game.get_turn()-1]['username']}"
        
        return result + "\n"


    def _get_turn_client(self):
        if self._status == self.ServerStatus.PLAYING_SOLO:
            return self._clients[0] if self._game.get_turn() == 1 else None
        elif self._status == self.ServerStatus.PLAYING_DUAL:
            return self._clients[self._game.get_turn()-1] 
        raise Exception("Invalid status")


    def _get_client_by_address(self, addr):
        for c in self._clients:
            if c['address'] == addr:
                return c
            
        return None


    def _get_help_string(self):
        result = self._game.get_help_board_as_string() 
        result += "Use the command \"/put (x, y)\" to put your sign on the board.\n"
        result += "Use the command \"/msg message\" to send your message\n"

        return result
    

    def _init_solo_game(self, message: ServerStartSoloPlayMessage):
        self._clients = [message.client]
        self._status = self.ServerStatus.PLAYING_SOLO
        self._game = TicTacToeGame(np.random.randint(1, 3))

        if self._game.get_turn() == 2:
            x_new, y_new = self._game.random_play()
            self._logger.cyan(f"Computer played random move /put ({x_new}, {y_new})")

        self._socket.sendall(ServerToClientMessage(
            self._clients[0]['address'],   
            colored("Game started. Enjoy!\n", "green") + colored(self._get_game_board_and_turn_as_string(), "blue")
        ).serialize().encode())

        self._logger.green(f"A solo game started [{self._clients[0]['username']} vs Computer]")
    

    def _init_dual_game(self, message: ServerStartDualPlayMessage):
        self._clients = message.clients
        self._status = self.ServerStatus.PLAYING_DUAL
        self._game = TicTacToeGame(np.random.randint(1, 3))

        message_to_clients = self._get_game_board_and_turn_as_string()
        for client in self._clients:
            self._socket.sendall(ServerToClientMessage(
                client['address'],
                colored("Game started. Enjoy!\n", "green") + colored(message_to_clients, "blue")
            ).serialize().encode())
        
        self._logger.green(f"A dual game started [{self._clients[0]['username']} vs {self._clients[1]['username']}]")


    def _handle_incoming_message_in_waiting_status(self, message: Message):
        if message.message_type == MessageType.SERVER_START_SOLO_PLAY:
            self._init_solo_game(message)
        elif message.message_type == MessageType.SERVER_START_DUAL_PLAY:
            self._init_dual_game(message)
        else:
            self._logger.red("Invalid message type. It should be either ServerStartSoloPlayMessage or ServerStartDualPlayMessage.")
    

    def _send_help_to_client(self, message: ClientToServerMessage):
            self._socket.sendall(
                ServerToClientMessage(message.client_address, colored(self._get_help_string(), "yellow")).serialize().encode()
            )

            self._logger.cyan(f"\"{self._get_client_by_address(message.client_address)['username']}\" requested for help menu")


    def _broadcast_message(self, message: ClientToServerMessage, message_content):
        username = self._get_client_by_address(message.client_address)['username']
        message_to_send = colored(f"{colored(username, attrs=['underline'])}: {message_content}", attrs=["bold"]) + "\n"
        for c in self._clients:
            self._socket.sendall(ServerToClientMessage(c['address'], message_to_send).serialize().encode())
        
        self._logger.cyan(f"Message from \"{username}\" sent to clients. Message content: {message_content}")
    

    def _check_end_of_game(self):
        if not self._game.is_finished():
            return False

        if self._game.is_draw():
            self._logger.green("Game ended. Result: Tie")

            for client in self._clients:
                self._socket.sendall(ServerToClientMessage(client['address'], colored("Game finished. Result: Tie\n", "cyan")).serialize().encode())

            self._socket.sendall(ServerEndGameMessage(is_tie=True, winner_address=None).serialize().encode())
        else:
            if self._status == self.ServerStatus.PLAYING_SOLO:
                winner_name = self._clients[0]['username'] if self._game.get_winner() == 1 else "Computer"
                self._logger.green(f"Game ended. Winner: {winner_name}")

                lost_or_won = "won" if self._game.get_winner() == 1 else "lost"

                self._socket.sendall(
                    ServerToClientMessage(self._clients[0]['address'], colored(f"Game finished. You {lost_or_won} the game!\n", "cyan")).serialize().encode()
                )

                self._socket.sendall(ServerEndGameMessage(
                    is_tie=False,
                    winner_address=self._clients[0]['address'] if self._game.get_winner() == 1 else None
                ).serialize().encode())
            else:
                winner_client = self._clients[self._game.get_winner()-1]
                
                self._logger.green(f"Game ended. Winner: {winner_client['username']}")

                for client in self._clients:
                    if client == winner_client:
                        self._socket.sendall(ServerToClientMessage(client['address'], colored("Game finished. You won the game!\n", "cyan")).serialize().encode())
                    else:
                        self._socket.sendall(ServerToClientMessage(client['address'], colored("Game finished. You lost the game!\n", "cyan")).serialize().encode())

                self._socket.sendall(ServerEndGameMessage(is_tie=False, winner_address=winner_client['address']).serialize().encode())

        self._logger.yellow("Server ended the connection with clients")
        
        return True
    

    def _reset_configuration(self):
        self._status = self.ServerStatus.WAITING
        self._clients = []
        self._game = None

        self._logger.magenta("Server configurations reseted to default values")


    def _send_clients_board_and_turn(self):
        message_to_clients = self._get_game_board_and_turn_as_string()
        for client in self._clients:
            webserver_socket.sendall(
                ServerToClientMessage(client['address'], colored(message_to_clients, "blue")).serialize().encode()
            )


    def _handle_game_message(self, message: ClientToServerMessage, x:int, y:int):
        username = self._get_client_by_address(message.client_address)['username']

        if message.client_address != self._get_turn_client()['address']:
            self._socket.sendall(
                ServerToClientMessage(message.client_address, colored("It's not your turn to play!\n", "red")).serialize().encode()
            )

            self._logger.yellow(f"\"{username}\" used /put command but it wasn't his turn")
        else:
            if not self._game.is_coord_valid(x, y):
                self._socket.sendall(ServerToClientMessage(message.client_address, colored("Invalid coord! See /help for more help.\n", "red")).serialize().encode())

                self._logger.yellow(f"\"{username}\" used /put command with invalid coord ({x}, {y})")
            elif not self._game.is_coord_cell_empty(x, y):
                self._socket.sendall(ServerToClientMessage(message.client_address, colored("The cell is already filled. Try another one\n", "red")).serialize().encode())

                self._logger.yellow(f"\"{username}\" used /put command with invalid coord ({x}, {y}) [cell was already filled]")
            else:
                self._game.put(x, y)

                self._logger.cyan(f"\"{username}\" used /put command with coord ({x}, {y})")
                
                is_finished = self._check_end_of_game()

                if not is_finished:
                    if self._status == self.ServerStatus.PLAYING_SOLO:
                        x_new, y_new = self._game.random_play()
                        
                        self._logger.blue(f"Computer played random move /put ({x_new}, {y_new})")

                        is_finished = self._check_end_of_game()

                        if not is_finished:
                            self._send_clients_board_and_turn()
                            self._logger.magenta("Board and turn sent to clients")
                    else:
                        self._send_clients_board_and_turn()
                        self._logger.magenta("Board and turn sent to clients")
                else:
                    self._reset_configuration()
    

    def _update_client(self, client):
        for idx, c in enumerate(self._clients):
            if c['username'] == client['username']:
                self._clients[idx] = client

                self._logger.magenta(f"Client \"{client['username']}\" updated")
                return
        
        self._logger.red(f"Invalid client update. No client with username \"{client['username']}\"")


    def serve(self):
        while True:
            message: Message = Message.deserialize(SocketReader(self._socket).read_json())

            if self._status == self.ServerStatus.WAITING:
                self._handle_incoming_message_in_waiting_status(message)
            elif message.message_type == MessageType.SERVER_FORCE_TERMINATE:
                self._logger.red("Server terminated from web server")
                self._reset_configuration()
            elif message.message_type == MessageType.SERVER_UPDATE_CLIENT:
                self._update_client(message.client)
                self._socket.sendall(ServerToClientMessage(
                    message.client['address'],   
                    colored("Reconnected to the server!\n", "green") + colored(self._get_game_board_and_turn_as_string(), "blue")
                ).serialize().encode())
            else:
                if message.message_type != MessageType.CLIENT_TO_SERVER_MESSAGE:
                    logger.red("Invalid message type. It should be of type ClientToServerMessage")
                    continue
                
                message: ClientToServerMessage = message

                m_msg = re.match(self.MSG_COMMAND_REGEX, message.message)
                m_put = re.match(self.PUT_COMMAND_REGEX, message.message)

                if message.message == "/help":
                    self._send_help_to_client(message)
                elif m_msg:
                    self._broadcast_message(message, m_msg.group(1))
                elif m_put:
                    self._handle_game_message(message, int(m_put.group(1)), int(m_put.group(2)))
                else:
                    webserver_socket.sendall(ServerToClientMessage(
                        message.client_address, colored("Invalid command. See /help for more help\n", "red")).serialize().encode()
                    )

                    self._logger.yellow(f"Invalid command from \"{self._get_client_by_address(message.client_address)['username']}\"")




if __name__ == '__main__':
    load_dotenv()
    
    host = os.getenv("HOST")
    port = int(os.getenv("PORT"))

    webserver_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    webserver_socket.connect((host, port))
    webserver_socket.sendall(ServerInitMessage().serialize().encode())
    print(webserver_socket.recv(1024).decode(), end='')

    GameServer(webserver_socket).serve()
