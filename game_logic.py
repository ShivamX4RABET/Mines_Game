from dataclasses import dataclass
from typing import List, Tuple
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
        """Generate 5x5 board with mines and gems"""
        board = [[Tile("💎") for _ in range(5)] for _ in range(5)]
        mine_positions = random.sample(range(25), self.mines_count)
        for pos in mine_positions:
            row, col = divmod(pos, 5)
            board[row][col].value = "💣"
        return board

    def reveal_tile(self, row: int, col: int) -> Tuple[bool, str]:
        """Return (success, status) where status: 'gem', 'bomb', 'already_revealed'"""
        tile = self.board[row][col]
        
        if tile.revealed:
            return False, 'already_revealed'
        
        tile.revealed = True
        
        if tile.value == "💣":
            self._reveal_all()
            return False, 'bomb'
        
        self.gems_revealed += 1
        self._update_multiplier()
        return True, 'gem'

    def _reveal_all(self) -> None:
        """Reveal all tiles when game ends"""
        for row in self.board:
            for tile in row:
                tile.revealed = True

    def _update_multiplier(self) -> None:
        """Update current multiplier value"""
        base = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base)

    def calculate_winnings(self) -> int:
        """Return integer winnings"""
        return int(self.bet_amount * self.current_multiplier)
