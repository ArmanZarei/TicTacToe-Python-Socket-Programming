import socket


class SocketReader:
    def __init__(self, socket: socket.socket):
        self._socket = socket
    
    def read_json(self):
        res = self._socket.recv(1).decode()
        
        if res != "{":
            raise Exception(f"First char in buff is not open bracket (it's {res}). Incompatible with JSON convension.")
        
        cnt = 1

        while cnt != 0:
            ch = self._socket.recv(1).decode()
            res += ch

            if ch == "{":
                cnt += 1
            elif ch == "}":
                cnt -= 1
            
            if cnt == 0:
                break
        
        return res
