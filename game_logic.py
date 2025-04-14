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
        # Create all gems first
        board = [[Tile("💎") for _ in range(5)] for _ in range(5)]
        
        # Place mines randomly
        positions = [(i, j) for i in range(5) for j in range(5)]
        mine_positions = random.sample(positions, self.mines_count)
        
        for row, col in mine_positions:
            board[row][col].value = "💣"
        return board

    def reveal_tile(self, row: int, col: int) -> bool:
        """Return True if safe/gem, False if bomb"""
        tile = self.board[row][col]
        tile.revealed = True
        
        if tile.value == "💣":
            self._reveal_all()
            return False
            
        if tile.value == "💎":
            self.gems_revealed += 1
            self._update_multiplier()
        return True

    def _update_multiplier(self):
        """Calculate current multiplier with better progression"""
        base_multiplier = 0.5 + (self.mines_count / 24) * 1.5
        self.current_multiplier = round(1.0 + (self.gems_revealed * base_multiplier), 2)

    def _reveal_all(self):
        """Show all bombs/gems when game ends"""
        for row in self.board:
            for tile in row:
                tile.revealed = True
