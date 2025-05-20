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
    def __init__(self, player1: User, player2: User, bet: int, is_bot: bool=False):
        self.player1 = player1
        self.player2 = player2             # ALWAYS a User object
        self.is_bot  = is_bot              # True when player2 is the Bot
        self.bet     = bet
        self.board   = [[None]*3 for _ in range(3)]
        
        # map actual user IDs → symbols
        self.symbols = {
            self.player1.id: '❌',
            self.player2.id: '⭕',
        }

        # pick who goes first
        self.current_player = random.choice([self.player1, self.player2])
        self.winner = None

    def build_board_markup(self) -> InlineKeyboardMarkup:
        kb = []
        for i in range(3):
            row = []
            for j in range(3):
                text = self.board[i][j] or ' '  # empty
                row.append(InlineKeyboardButton(text, callback_data=f"ttt_move_{i}_{j}_{self.player1.id}"))
            kb.append(row)
        return InlineKeyboardMarkup(kb)

    def bot_move(self):
        """
        Simple AI: choose a random empty cell. Returns (i,j).
        """
        empties = [(i,j) for i in range(3) for j in range(3) if not self.board[i][j]]
        return random.choice(empties)

    def make_move(self, i: int, j: int, user_id: int) -> str:
        if self.board[i][j] or self.winner:
            return 'invalid'
        sym = self.symbols.get(user_id if isinstance(user_id,int) else 'bot')
        self.board[i][j] = sym
        if self.check_win(sym): self.winner = user_id
        elif all(all(cell for cell in row) for row in self.board): self.winner = 'draw'
        else:
            # switch
            self.current_player = self.player1 if self.current_player!=self.player1 else ('bot' if self.player2_name=='Bot' else 'invitee')
        return 'ok'

    def check_win(self, sym: str) -> bool:
        # rows, cols, diags
        lines = self.board + list(zip(*self.board)) + [ [self.board[i][i] for i in range(3)], [self.board[i][2-i] for i in range(3)] ]
        return any(all(cell==sym for cell in line) for line in lines)
