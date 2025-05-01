from dataclasses import dataclass
from typing import List, Tuple
import random

@dataclass
class Tile:
    value: str = " "    # will become 💎 or 💣
    revealed: bool = False

class MinesGame:
    def __init__(self, bet_amount: int, mines_count: int):
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.gems_revealed = 0
        self.current_multiplier = 1.0
        self.game_over = False
        self.board = self._generate_board()

    def _generate_board(self) -> List[List[Tile]]:
        board = [[Tile() for _ in range(5)] for _ in range(5)]
        mine_positions = random.sample(range(25), self.mines_count)
        for pos in mine_positions:
            row, col = divmod(pos, 5)
            board[row][col].value = "💣"
        return board

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
