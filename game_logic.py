from dataclasses import dataclass
from typing import List, Tuple
import random

@dataclass
class Tile:
    value: str   # "💣" for a mine or "💎" for a gem
    revealed: bool = False

class MinesGame:
    def __init__(self, bet_amount: int, mines_count: int):
        """
        Initialize a 5×5 minesweeper-style game.
        
        :param bet_amount: amount staked by the player
        :param mines_count: number of bombs (must be 0–24)
        """
        if not (0 <= mines_count < 25):
            raise ValueError("mines_count must be between 0 and 24")
        
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.gems_revealed = 0
        self.multiplier = 1.0
        self.game_over = False
        self.board = self._generate_board()

    def _generate_board(self) -> List[List[Tile]]:
        """Create a 5×5 grid, randomly placing the specified number of mines."""
        board = [[Tile("💎") for _ in range(5)] for _ in range(5)]
        mine_positions = random.sample(range(25), self.mines_count)
        for pos in mine_positions:
            row, col = divmod(pos, 5)
            board[row][col].value = "💣"
        return board

    def reveal_tile(self, row: int, col: int) -> Tuple[bool, str]:
        """
        Reveal a tile at (row, col).

        :returns: (success, status)  
                  success=False with status 'already_revealed' or 'out_of_bounds' or 'bomb'  
                  success=True with status 'gem'
        """
        # Bounds check
        if not (0 <= row < 5 and 0 <= col < 5):
            return False, 'out_of_bounds'

        tile = self.board[row][col]
        if tile.revealed:
            return False, 'already_revealed'

        tile.revealed = True
        if tile.value == "💣":
            # Hit a bomb → end game
            self.game_over = True
            self._reveal_all_tiles()
            return False, 'bomb'

        # Found a gem → update state
        self.gems_revealed += 1
        self._recalculate_multiplier()
        return True, 'gem'

    def _reveal_all_tiles(self) -> None:
        """Mark every tile on the board as revealed (used when the game ends)."""
        for row in self.board:
            for tile in row:
                tile.revealed = True

    def _recalculate_multiplier(self) -> None:
        """
        Recompute the payout multiplier based on gems found:
        base rate = 0.25 + (mines_count / 24) * 0.5,
        total multiplier = 1 + gems_revealed * base rate.
        """
        base_rate = 0.25 + (self.mines_count / 24) * 0.5
        self.multiplier = 1.0 + (self.gems_revealed * base_rate)

    def calculate_winnings(self) -> int:
        """
        Compute final winnings.  
        Returns 0 if the player has hit a bomb.
        """
        if self.game_over:
            return 0
        return int(self.bet_amount * self.multiplier)

    def has_won(self) -> bool:
        """
        Check if all non-mine tiles have been revealed.
        """
        total_gems = 25 - self.mines_count
        return self.gems_revealed >= total_gems
