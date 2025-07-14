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
