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
        """Generate board with mines and remaining as gems"""
        # Start with all gems
        board = [[Tile("💎") for _ in range(5)] for _ in range(5)]
        
        # Place mines
        mine_positions = random.sample(range(25), self.mines_count)
        for pos in mine_positions:
            row = pos // 5
            col = pos % 5
            board[row][col].value = "💣"
            
        return board

    def reveal_tile(self, row: int, col: int) -> tuple[bool, str]:
    """Return (success, status) where status: 'gem', 'bomb', 'already_revealed'"""
    tile = self.board[row][col]
    
    # Check if already revealed
    if tile.revealed:
        return False, 'already_revealed'
    
    tile.revealed = True
    
    # Bomb handling
    if tile.value == "💣":
        self._reveal_all()
        return False, 'bomb'
    
    # Gem handling
    self.gems_revealed += 1
    self._update_multiplier()
    return True, 'gem'

def _reveal_all(self) -> None:
    """Reveal all tiles when bomb is hit"""
    for row in self.board:
        for tile in row:
            tile.revealed = True

    def _update_multiplier(self):
        """Update multiplier based on gems found"""
        base = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base)

    def calculate_winnings(self) -> int:
        """Return integer winnings"""
        return int(self.bet_amount * self.current_multiplier)
