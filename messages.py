import json


class MessageType:
    CLIENT_INIT = 0
    CLIENT_INIT_RESPONSE = 1
    CLIENT_MESSAGE = 2
    SERVER_INIT = 3
    SERVER_START_SOLO_PLAY = 4
    SERVER_START_DUAL_PLAY = 5
    CLIENT_TO_SERVER_MESSAGE = 6
    SERVER_TO_CLIENT_MESSAGE = 7
    SERVER_END_GAME = 8
    SERVER_FORCE_TERMINATE = 9
    SERVER_UPDATE_CLIENT = 10

    @staticmethod
    def resolve_class(m_type):
        return {
            MessageType.CLIENT_INIT: ClientInitMessage,
            MessageType.CLIENT_INIT_RESPONSE: ClientInitResponse,
            MessageType.CLIENT_MESSAGE: ClientMessage,
            MessageType.SERVER_INIT: ServerInitMessage,
            MessageType.SERVER_START_SOLO_PLAY: ServerStartSoloPlayMessage,
            MessageType.SERVER_START_DUAL_PLAY: ServerStartDualPlayMessage,
            MessageType.CLIENT_TO_SERVER_MESSAGE: ClientToServerMessage,
            MessageType.SERVER_TO_CLIENT_MESSAGE: ServerToClientMessage,
            MessageType.SERVER_END_GAME: ServerEndGameMessage,
            MessageType.SERVER_FORCE_TERMINATE: ServerForceTerminateMessage,
            MessageType.SERVER_UPDATE_CLIENT: ServerUpdateClientMessage,
        }[m_type]


class Message:
    def __init__(self, message_type: MessageType):
        self.message_type = message_type
    
    def serialize(message):
        return json.dumps(message, default=lambda msg: msg.__dict__)
    
    @staticmethod
    def deserialize(message_json):
        message_dict = json.loads(message_json)
        cls = MessageType.resolve_class(message_dict["message_type"])
        message_dict.pop("message_type")
        return cls(**message_dict)


class ClientInitMessage(Message):
    def __init__(self, username):
        super().__init__(MessageType.CLIENT_INIT)
        self.username = username


class ClientInitResponse(Message):
    def __init__(self, is_valid, message):
        super().__init__(MessageType.CLIENT_INIT_RESPONSE)
        self.is_valid = is_valid
        self.message = message


class ClientMessage(Message):
    def __init__(self, message):
        super().__init__(MessageType.CLIENT_MESSAGE)
        self.message = message


class ServerInitMessage(Message):
    def __init__(self):
        super().__init__(MessageType.SERVER_INIT)


class ServerStartSoloPlayMessage(Message):
    def __init__(self, client):
        super().__init__(MessageType.SERVER_START_SOLO_PLAY)
        self.client = client


class ServerStartDualPlayMessage(Message):
    def __init__(self, clients):
        super().__init__(MessageType.SERVER_START_DUAL_PLAY)
        self.clients = clients


class ClientToServerMessage(Message):
    def __init__(self, client_address, message):
        super().__init__(MessageType.CLIENT_TO_SERVER_MESSAGE)
        self.client_address = client_address
        self. message = message


class ServerToClientMessage(Message):
    def __init__(self, client_address, message):
        super().__init__(MessageType.SERVER_TO_CLIENT_MESSAGE)
        self.client_address = client_address
        self.message = message


class ServerEndGameMessage(Message):
    def __init__(self, is_tie, winner_address):
        super().__init__(MessageType.SERVER_END_GAME)
        self.is_tie = is_tie
        self.winner_address = winner_address


class ServerForceTerminateMessage(Message):
    def __init__(self):
        super().__init__(MessageType.SERVER_FORCE_TERMINATE)


class ServerUpdateClientMessage(Message):
    def __init__(self, client):
        super().__init__(MessageType.SERVER_UPDATE_CLIENT)
        self.client = client
