from dataclasses import dataclass
from typing import List
import random

@dataclass
class Tile:
    value: str  # "💣" or "💎"
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
        """Create board with gems and mines"""
        board = [[Tile("💎") for _ in range(5)] for _ in range(5)]
        positions = random.sample(range(25), self.mines_count)
        
        for pos in positions:
            row = pos // 5
            col = pos % 5
            board[row][col].value = "💣"
        return board

    def reveal_tile(self, row: int, col: int) -> bool:
        """Return True if safe/gem, False if bomb"""
        tile = self.board[row][col]
        tile.revealed = True
        
        if tile.value == "💣":
            self._reveal_all()
            return False
            
        self.gems_revealed += 1
        self._update_multiplier()
        return True

    def _update_multiplier(self):
        """Calculate current multiplier"""
        base = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base)

    def _reveal_all(self):
        """Show all bombs/gems when game ends"""
        for row in self.board:
            for tile in row:
                if tile.value in ("💣", "💎"):
                    tile.revealed = True
