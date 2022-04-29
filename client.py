from dotenv import load_dotenv
import os
import socket
import threading
from messages import ClientInitMessage, ClientInitResponse, ClientMessage, Message
from socket_reader import SocketReader


def receive_thread(socket_obj: socket.socket):
    while True:
        try:
            print(socket_obj.recv(1024).decode(), end='')
        except:
            socket_obj.close()
            return

def send_thread(socket_obj: socket.socket):
    while True:
        inp = input()
        if inp == '/exit':
            socket_obj.shutdown(0)
            socket_obj.close()
            return
        socket_obj.send(ClientMessage(inp).serialize().encode())


def non_empty_username_from_input():
    username = input("Username: ")
    while username.strip() == "":
        username = input("Username: ")

    return username


if __name__ == '__main__':
    load_dotenv()

    username = non_empty_username_from_input()
    
    host = os.getenv("HOST")
    port = int(os.getenv("PORT"))

    socket_obj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_obj.connect((host, port))

    while True:
        socket_obj.send(ClientInitMessage(username).serialize().encode())

        message: ClientInitResponse = Message.deserialize(SocketReader(socket_obj).read_json())
        
        if message.is_valid:
            break
        else:
            print(message.message, end='')
            username = non_empty_username_from_input()


    tr = threading.Thread(target=receive_thread, args=[socket_obj])
    tc = threading.Thread(target=send_thread, args=[socket_obj])
    
    tr.start()
    tc.start()

    tc.join()
    tr.join()

    print("Good bye!")
