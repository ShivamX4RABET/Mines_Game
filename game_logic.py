from dataclasses import dataclass
from typing import List, Tuple
import random

@dataclass
class Tile:
    value: str = " "    # will become 💎 or 💣
    revealed: bool = False

# In game_logic.py
class MinesGame:
    def __init__(self, bet_amount: int, mines_count: int, user_emoji: str = '💎'):
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.user_emoji = user_emoji  # Store custom emoji
        self.board = [[Tile() for _ in range(5)] for _ in range(5)]
        self.gems_revealed = 0
        self.current_multiplier = 1.0
        self.game_over = False
        self.message_id = None
        self.generate_board()

    def generate_board(self):
        positions = [(i, j) for i in range(5) for j in range(5)]
        random.shuffle(positions)
        
        # Set mines
        for i in range(self.mines_count):
            x, y = positions[i]
            self.board[x][y].value = "💣"
        
        # Set custom emojis for gems
        for i in range(self.mines_count, 25):
            x, y = positions[i]
            self.board[x][y].value = self.user_emoji  # Use custom emoji here
    
    def reveal_tile(self, row: int, col: int) -> Tuple[bool, str]:
        tile = self.board[row][col]
        if tile.revealed:
            return False, 'already_revealed'
        tile.revealed = True

        if tile.value == "💣":
            # hit a mine!
            self.game_over = True
            self._reveal_all_tiles()
            return False, 'bomb'
        else:
            # safe tile → always a gem
            tile.value = "💎"
            self.gems_revealed += 1
            self._recalculate_multiplier()
            return True, 'gem'

    def _recalculate_multiplier(self) -> None:
        base_rate = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base_rate)

    def _reveal_all_tiles(self) -> None:
        for row in self.board:
            for tile in row:
                tile.revealed = True
