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
        self.message_id = None
        self.board = self._generate_board()
    
    def _generate_board(self) -> List[List[Tile]]:
        """Generate a 5x5 board with gems and bombs."""
        board = [[Tile("⬜️") for _ in range(5)] for _ in range(5)]
        
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
        """Reveal a tile and return True if safe/gem, False if bomb."""
        tile = self.board[i][j]
        tile.revealed = True
        
        if tile.value == "💣":
            self._reveal_all_mines_and_gems()
            return False
        elif tile.value == "💎":
            self.gems_revealed += 1
            self._update_multiplier()
            return True
        return True
    
    def _reveal_all_mines_and_gems(self):
        """Reveal all bombs and gems when game ends."""
        for row in self.board:
            for tile in row:
                if tile.value in ("💣", "💎"):
                    tile.revealed = True
    
    def _update_multiplier(self):
        """Update multiplier based on gems found."""
        base_increase = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base_increase)
