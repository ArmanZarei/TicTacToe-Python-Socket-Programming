import numpy as np


class TicTacToeGame:
    def __init__(self, first_turn_number):
        assert first_turn_number == 1 or first_turn_number == 2
        self.__board = [[0 for _ in range(3)] for _ in range(3)]
        self.__turn = first_turn_number
    
    def get_sign(self, x):
        return {0: " ", 1: "X", 2: "O"}[x]
    
    def get_winner(self):
        for i in range(3):
            if self.__board[i][0] == self.__board[i][1] and self.__board[i][1] == self.__board[i][2] and self.__board[i][0] != 0:
                return self.__board[i][0]
            if self.__board[0][i] == self.__board[1][i] and self.__board[1][i] == self.__board[2][i] and self.__board[0][i] != 0:
                return self.__board[0][i]
        if self.__board[0][0] == self.__board[1][1] and self.__board[1][1] == self.__board[2][2] and self.__board[0][0] != 0:
            return self.__board[0][0]
        if self.__board[0][2] == self.__board[1][1] and self.__board[1][1] == self.__board[2][0] and self.__board[0][2] != 0:
            return self.__board[0][2]
        return None
    
    def is_draw(self):
        if self.get_winner() != None:
            return False
        for i in range(3):
            for j in range(3):
                if self.__board[i][j] == 0:
                    return False
        return True
             
    def is_finished(self):
        return self.get_winner() != None or self.is_draw() 
    
    def __change_turn(self):
        self.__turn = 2 if self.__turn == 1 else 1
    
    def is_coord_valid(self, x, y):
        return x >= 0  and x <= 2 and y >= 0 and y <= 2
    
    def is_coord_cell_empty(self, x, y):
        return self.__board[x][y] == 0
    
    def put(self, x, y):
        if self.is_finished():
            raise Exception("Game is finished!")
        if not self.is_coord_cell_empty(x, y):
            raise ValueError(f"Cell ({x}, {y}) is not empty!")
        self.__board[x][y] = self.__turn
        self.__change_turn()
    
    def get_board_as_string(self):
        board = "┏━━━┳━━━┳━━━┓\n"
        board += f"┃ {self.get_sign(self.__board[0][0])} ┃ {self.get_sign(self.__board[0][1])} ┃ {self.get_sign(self.__board[0][2])} ┃\n"
        board += "┣━━━╋━━━╋━━━┫\n"
        board += f"┃ {self.get_sign(self.__board[1][0])} ┃ {self.get_sign(self.__board[1][1])} ┃ {self.get_sign(self.__board[1][2])} ┃\n"
        board += "┣━━━╋━━━╋━━━┫\n"
        board += f"┃ {self.get_sign(self.__board[2][0])} ┃ {self.get_sign(self.__board[2][1])} ┃ {self.get_sign(self.__board[2][2])} ┃\n"
        board += "┗━━━┻━━━┻━━━┛\n"
        return board
    
    def get_help_board_as_string(self):
        board = ""
        board += "┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓\n"
        board += "┃        ┃        ┃        ┃\n"
        board += "┃ (0, 0) ┃ (0, 1) ┃ (0, 2) ┃\n"
        board += "┃        ┃        ┃        ┃\n"
        board += "┣━━━━━━━━╋━━━━━━━━╋━━━━━━━━┫\n"
        board += "┃        ┃        ┃        ┃\n"
        board += "┃ (1, 0) ┃ (1, 1) ┃ (1, 2) ┃\n"
        board += "┃        ┃        ┃        ┃\n"
        board += "┣━━━━━━━━╋━━━━━━━━╋━━━━━━━━┫\n"
        board += "┃        ┃        ┃        ┃\n"
        board += "┃ (2, 0) ┃ (2, 1) ┃ (2, 2) ┃\n"
        board += "┃        ┃        ┃        ┃\n"
        board += "┗━━━━━━━━┻━━━━━━━━┻━━━━━━━━┛\n"
        return board

    def get_turn(self):
        return self.__turn
    
    def random_play(self):
        if self.is_finished():
            raise Exception("Game is finished!")
        choices = []
        for i in range(3):
            for j in range(3):
                if self.__board[i][j] == 0:
                    choices.append((i, j))
        
        x, y = choices[np.random.randint(len(choices))]

        self.put(x, y)

        return x, y


if __name__ == '__main__':
    game = TicTacToeGame(2)
    print("Help board:")
    print(game.get_help_board_as_string())
    while True:
        print(f"\nTurn: {game.get_turn()}")
        print(f"Is finished: {game.is_finished()} | Winner: {game.get_winner()} | Is Draw: {game.is_draw()}")
        print("Game Board:")
        print(game.get_board_as_string())

        if game.is_finished():
            break

        if game.get_turn() == 1:
            x, y = map(int, input("Enter cell: ").split())
            game.put(x, y)
        else: 
            c_x, c_y = game.random_play()
            print("Computer played it's turn randomly")
