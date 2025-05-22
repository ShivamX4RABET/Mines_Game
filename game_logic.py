from telegram import User, InlineKeyboardMarkup, InlineKeyboardButton
from dataclasses import dataclass
from typing import List, Tuple
import random

@dataclass
class Tile:
    def __init__(self, value: str):
        self.value = value
        self.revealed = False

class MinesGame:
    def __init__(self, bet_amount: int, mines: int, player_emoji: str = "💎"):
        self.bet_amount = bet_amount
        self.mines_count = mines
        self.player_emoji = player_emoji
        self.current_multiplier = 1.0
        self.message_id = None
        self.board = [[Tile(value=self.player_emoji) for _ in range(5)] for _ in range(5)]
        self.gems_revealed = 0
        self.game_over = False
        self.generate_board()

    def generate_board(self):
        import random
        positions = [(i,j) for i in range(5) for j in range(5)]
        random.shuffle(positions)
        
        # Set mines
        for i in range(self.mines_count):
            row, col = positions[i]
            self.board[row][col].value = "💣"
            
        # Remaining tiles stay as player_emoji

    def reveal_tile(self, row: int, col: int) -> Tuple[bool, str]:
        tile = self.board[row][col]
        if tile.revealed:
            return False, 'already_revealed'
        tile.revealed = True

        if tile.value == "💣":
            self.game_over = True
            self._reveal_all_tiles()
            return False, 'bomb'
        else:
            tile.value = self.player_emoji  # Use selected emoji
            self.gems_revealed += 1
            self._recalculate_multiplier()
            return True, 'gem'

    def _recalculate_multiplier(self) -> None:
        base_rate = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base_rate)

    def _reveal_all_tiles(self):
        for row in self.board:
            for tile in row:
                tile.revealed = True

class TicTacToeGame:
    def __init__(self, player1: User, player2: User, bet: int, is_bot=False):
        self.player1 = player1
        self.player2 = player2
        self.is_bot = is_bot
        self.bet = bet
        self.board = [[None]*3 for _ in range(3)]
        self.symbols = {
            player1.id: '❌',
            player2.id: '⭕'
        }
        self.current_player = random.choice([player1, player2])
        self.winner = None

    def make_move(self, i: int, j: int, player_id: int) -> bool:
        if self.board[i][j] or self.winner:
            return False
        self.board[i][j] = self.symbols[player_id]
        # Check win
        if self.check_win(self.symbols[player_id]):
            self.winner = player_id
        elif all(all(row) for row in self.board):
            self.winner = 'draw'
        else:
            self.current_player = self.player2 if self.current_player == self.player1 else self.player1
        return True

    def check_win(self, symbol: str) -> bool:
        # Check rows, columns, diagonals
        for row in self.board:
            if all(cell == symbol for cell in row):
                return True
        for col in range(3):
            if all(self.board[row][col] == symbol for row in range(3)):
                return True
        if all(self.board[i][i] == symbol for i in range(3)) or \
           all(self.board[i][2-i] == symbol for i in range(3)):
            return True
        return False

        # pick who goes first
        self.current_player = random.choice([self.player1, self.player2])
        self.winner = None

    def build_board_markup(self) -> InlineKeyboardMarkup:
        kb = []
        for i in range(3):
            row = []
            for j in range(3):
                text = self.board[i][j] or '▫️'
                row.append(InlineKeyboardButton(text, callback_data=f"ttt_move_{i}_{j}_{self.player1.id}"))
            kb.append(row)
        return InlineKeyboardMarkup(kb)

    def bot_move(self):
        """
        Simple AI: choose a random empty cell. Returns (i,j).
        """
        empties = [(i,j) for i in range(3) for j in range(3) if not self.board[i][j]]
        return random.choice(empties)
        
