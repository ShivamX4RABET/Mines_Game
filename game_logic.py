# game_logic.py - UPDATED
from dataclasses import dataclass
from typing import List, Tuple
import random

@dataclass
class Tile:
    value: str = " "  # Initialize as empty
    revealed: bool = False

class MinesGame:
    def __init__(self, bet_amount: int, mines_count: int):
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.gems_revealed = 0
        self.current_multiplier = 1.0  # Renamed from 'multiplier'
        self.game_over = False
        self.board = self._generate_board()

    def _generate_board(self) -> List[List[Tile]]:
        """Initialize empty board, then add mines"""
        board = [[Tile() for _ in range(5)] for _ in range(5)]  # Empty tiles
        mine_positions = random.sample(range(25), self.mines_count)
        for pos in mine_positions:
            row, col = divmod(pos, 5)
            board[row][col].value = "💣"
        return board

    def reveal_tile(self, row: int, col: int) -> Tuple[bool, str]:
        tile = self.board[row][col]
        if tile.revealed: return False, 'already_revealed'
        tile.revealed = True

        if tile.value == "💣":
            self.game_over = True
            self._reveal_all_tiles()
            return False, 'bomb'
        else:
            # Calculate adjacent mines and update tile value
            adjacent_mines = self._calculate_adjacent_mines(row, col)
            if adjacent_mines > 0:
                tile.value = str(adjacent_mines)
            else:
                tile.value = "💎"  # Show gem for zero adjacent mines
            self.gems_revealed += 1
            self._recalculate_multiplier()
            return True, 'gem'

    def _calculate_adjacent_mines(self, row: int, col: int) -> int:
        """Count mines around a tile"""
        count = 0
        for i in range(max(0, row-1), min(4, row+1)+1):
            for j in range(max(0, col-1), min(4, col+1)+1):
                if self.board[i][j].value == "💣":
                    count += 1
        return count

    def _recalculate_multiplier(self) -> None:
        base_rate = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base_rate)

    def _reveal_all_tiles(self) -> None:
        for row in self.board:
            for tile in row:
                tile.revealed = True
