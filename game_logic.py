from dataclasses import dataclass
from typing import List
import random

@dataclass
class Tile:
    value: str
    revealed: bool = False

class MinesGame:
    def __init__(self, bet_amount: int, mines_count: int):
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.gems_revealed = 0
        self.current_multiplier = 1.0
        self.message_id = None  # Store the message ID for editing
        self.board = self._generate_board()
    
    def _generate_board(self) -> List[List[Tile]]:
        """Generate a 5x5 board with gems and bombs."""
        # Create empty board
        board = [[Tile("🟦") for _ in range(5)] for _ in range(5)]
        
        # Place bombs
        bomb_positions = random.sample(range(25), self.mines_count)
        for pos in bomb_positions:
            i, j = divmod(pos, 5)
            board[i][j].value = "💣"
        
        # Place gems (3 gems)
        gem_positions = random.sample(
            [pos for pos in range(25) if pos not in bomb_positions],
            3
        )
        for pos in gem_positions:
            i, j = divmod(pos, 5)
            board[i][j].value = "💎"
        
        return board
    
    def reveal_tile(self, i: int, j: int) -> bool:
        """Reveal a tile. Returns True if it was a gem/safe, False if bomb."""
        tile = self.board[i][j]
        tile.revealed = True
        
        if tile.value == "💣":
            return False
        elif tile.value == "💎":
            self.gems_revealed += 1
            self._update_multiplier()
            return True
        else:
            # Empty tile
            self._update_multiplier()
            return True
    
    def _update_multiplier(self) -> None:
        """Update the multiplier based on revealed gems and mines count."""
        base_increase = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base_increase)
