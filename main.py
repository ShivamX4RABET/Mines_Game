import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from game_logic import MinesGame
from database import UserDatabase
db = UserDatabase("users.json")
import config
import datetime
from typing import Dict

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Changed from: user_games: Dict[int, MinesGame] = {}
# New structure: {chat_id: {user_id: MinesGame}}
user_games: Dict[int, Dict[int, MinesGame]] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    if not db.user_exists(user.id):
        db.add_user(
            user.id,
            user.username,     # may be None if they have no @username
            user.first_name,   # always present
            100
                )
        await update.message.reply_text(
            f"Welcome to Mines Game, {user.first_name}!\n"
            "You've been given 100 Hiwa to start playing.\n"
            "Use /help to learn how to play."
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {user.first_name}!\n"
            f"Your current balance: {db.get_balance(user.id)} Hiwa\n"
            "Use /help to see available commands."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
🎮 *Mines Game Bot Help* 🎮

*Basic Commands:*
/start - Initialize your account
/help - Show this help message
/balance - Check your Hiwa balance
/mine <amount> <mines> - Start a new game (e.g., /mine 10 5)
/cashout - Cash out your current winnings
/daily - Claim daily bonus (24h cooldown)
/weekly - Claim weekly bonus (7d cooldown)
/leaderboard - Show top players
/gift @username <amount> - Send Hiwa to another player

*Game Rules:*
1. 5x5 grid with hidden gems (💎) and bombs (💣)
2. Choose how many bombs (3-24) when starting
3. Reveal tiles to find gems
4. Cash out after finding at least 2 gems
5. Hit a bomb and you lose your bet

*Admin Commands:*
/broadcast <message> - Send message to all users
/resetdata - Reset all user data (admin only)
/setbalance @user <amount> - Set user balance (admin only)
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user balance."""
    user_id = update.effective_user.id
    balance = db.get_balance(user_id)
    await update.message.reply_text(f"Your current balance: {balance} Hiwa")

async def send_game_board(update: Update, game: MinesGame, user_id: int, exploded_row: int = -1, exploded_col: int = -1):
    """Send updated game board with proper user ID in callbacks"""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            text = "🟦"
            if game.game_over or tile.revealed:
                text = tile.value
                if i == exploded_row and j == exploded_col and tile.value == "💣":
                    text = "💥"
            
            # Add user ID to callback data
            row.append(InlineKeyboardButton(
                text, 
                callback_data=f"reveal_{i}_{j}_{user_id}"
            ))
        keyboard.append(row)
    
    if game.gems_revealed >= 2 and not game.game_over:
        keyboard.append([
            InlineKeyboardButton(
                f"💰 Cash Out ({game.current_multiplier:.2f}x)", 
                callback_data=f"cashout_{user_id}"
            )
        ])
    
    text = (
        f"💎 Mines Game 💣\n\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}/{25 - game.mines_count}\n"
        f"Multiplier: {game.current_multiplier:.2f}x"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Board update error: {e}")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mine command and initialize game"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = user.id

    # Check existing game in this chat
    if chat_id in user_games and user_id in user_games[chat_id]:
        await update.message.reply_text(
            "❌ You have an ongoing game in this chat! Finish it first."
        )
        return

    try:
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /mine <amount> <mines>\nExample: /mine 100 5")
            return

        amount = int(context.args[0])
        mines  = int(context.args[1])

        if amount < 1 or mines < 3 or mines > 24:
            await update.message.reply_text("Invalid input!\nAmount ≥1 | Mines 3–24")
            return

        if not db.has_sufficient_balance(user_id, amount):
            await update.message.reply_text("Insufficient balance!")
            return

        db.deduct_balance(user_id, amount)
        game = MinesGame(amount, mines)

        # Store game under chat_id and user_id
        if chat_id not in user_games:
            user_games[chat_id] = {}
        user_games[chat_id][user_id] = game

        await send_initial_board(update, context, chat_id, user_id, game)

    except Exception as e:
        logger.error(f"/mine error: {e}")
        await update.message.reply_text("Error starting game. Try again.")

async def send_initial_board(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    user_id: int, 
    game: MinesGame
) -> None:
    """Send the first game board with tiles to GROUP CHAT"""
    keyboard = [
        [
            InlineKeyboardButton(
                "🟦", 
                callback_data=f"reveal_{i}_{j}_{user_id}"  # Added user_id
            ) for j in range(5)
        ] for i in range(5)
    ]
    
    keyboard.append([
        InlineKeyboardButton(
            "💰 Initialize Cashout", 
            callback_data=f"cashout_{user_id}"  # Added user_id
        )
    ])
    
    text = (
        f"💎 {update.effective_user.first_name}'s Mines Game Started! 💣\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Tap tiles to begin!"
    )
    
    message = await context.bot.send_message(
        chat_id=chat_id,  # Send to group chat
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    game.message_id = message.message_id

async def update_board(update: Update, game: MinesGame):
    """Refresh game board with revealed tiles"""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            text = tile.value if tile.revealed else "🟦"
            row.append(InlineKeyboardButton(text, callback_data=f"reveal_{i}_{j}"))
        keyboard.append(row)
    
    if game.gems_revealed >= 2 and not game.game_over:
        keyboard.append([InlineKeyboardButton(
            f"💰 Cash Out ({game.multiplier:.2f}x)", 
            callback_data="cashout"
        )])
    
    text = (
        f"💎 Mines Game 💣\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}\n"
        f"Multiplier: {game.multiplier:.2f}x"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Board update error: {e}")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    caller_id = query.from_user.id
    data = query.data

    try:
        if data.startswith("reveal_"):
            parts = data.split("_")
            i, j, target_user_id = int(parts[1]), int(parts[2]), int(parts[3])
        elif data.startswith("cashout_"):
            target_user_id = int(data.split("_")[1])
        else:
            return

        # Validate user
        if caller_id != target_user_id:
            await query.answer("❌ This isn't your game!", show_alert=True)
            return

        # Retrieve game
        try:
            game = user_games[chat_id][target_user_id]
        except KeyError:
            await query.edit_message_text("❌ Game session expired!")
            return

        if data.startswith("reveal_"):
            success, status = game.reveal_tile(i, j)
            
            if not success:
                if status == "already_revealed":
                    await query.answer("Already revealed!", show_alert=True)
                elif status == "bomb":
                    await handle_game_over(
                        update, chat_id, target_user_id, game,
                        won=False, exploded_row=i, exploded_col=j, context=context
                    )
                return
                
            # Pass user_id to send_game_board
            await send_game_board(update, game, target_user_id, i, j)

        elif data.startswith("cashout"):
            if game.gems_revealed >= 2:
                game.game_over = True
                win_amount = int(game.bet_amount * game.current_multiplier)
                db.add_balance(target_user_id, win_amount)
                await handle_game_over(
                    update, chat_id, target_user_id, game,
                    won=True, context=context
                )
            else:
                await query.answer("Need 2+ gems to cash out!", show_alert=True)

    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await query.answer("Error processing request")

async def handle_game_over(
    update: Update,
    chat_id: int,  # NEW: Group chat ID where game exists
    user_id: int,   # NEW: User ID of game owner
    game: MinesGame,
    won: bool,
    exploded_row: int = -1,
    exploded_col: int = -1,
    context: ContextTypes.DEFAULT_TYPE = None
) -> None:
    """Handle game conclusion with group chat support"""
    # 1. Mark exploded bomb if applicable
    if not won and 0 <= exploded_row < 5 and 0 <= exploded_col < 5:
        game.board[exploded_row][exploded_col].value = "💥"

    # 2. Reveal all tiles
    for row in game.board:
        for tile in row:
            tile.revealed = True
            if tile.value not in ["💣", "💥"]:
                tile.value = "💎"

    # 3. Build final keyboard
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            row.append(InlineKeyboardButton(tile.value, callback_data="ignore"))
        keyboard.append(row)
    
    # 4. Add play again button
    keyboard.append([InlineKeyboardButton("🎮 Play Again", callback_data=f"newgame_{user_id}")])

    # 5. Prepare result message
    balance = db.get_balance(user_id)
    if won:
        win_amount = int(game.bet_amount * game.current_multiplier)
        message = (
            f"🎉 {update.effective_user.first_name} Cashed Out!\n"
            f"Won: {win_amount} Hiwa\n"
            f"New Balance: {balance} Hiwa"
        )
    else:
        message = (
            f"💥 {update.effective_user.first_name} Hit a Mine!\n"
            f"Lost: {game.bet_amount} Hiwa\n"
            f"New Balance: {balance} Hiwa"
        )

    # 6. Edit original message in group chat
    try:
        await update.callback_query.edit_message_text(
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Game over message error: {e}")

    # 7. Cleanup game state - CRITICAL NEW PART
    try:
        # Remove from nested storage
        del user_games[chat_id][user_id]
        # Cleanup empty chat entry
        if not user_games[chat_id]:
            del user_games[chat_id]
    except KeyError:
        pass

async def cashout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cashout command with group-chat support."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check nested dict: chat → user
    if chat_id not in user_games or user_id not in user_games[chat_id]:
        await update.message.reply_text("❌ You don't have an active game to cash out.")
        return

    game = user_games[chat_id][user_id]
    if game.gems_revealed < 2:
        await update.message.reply_text("❌ You need at least 2 gems to cash out.")
        return

    # Perform cashout
    game.game_over = True
    win_amount = int(game.bet_amount * game.current_multiplier)
    db.add_balance(user_id, win_amount)
    # Reuse your existing handle_game_over
    await handle_game_over(update, chat_id, user_id, game, won=True, context=context)

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /end — cancel an ongoing game and refund the bet."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # No active game?
    if chat_id not in user_games or user_id not in user_games[chat_id]:
        await update.message.reply_text("❌ You don’t have an active game to end.")
        return

    game = user_games[chat_id][user_id]

    # If the game already finished, disallow
    if game.game_over:
        await update.message.reply_text("❌ This game has already ended.")
        return

    # Refund original bet
    db.add_balance(user_id, game.bet_amount)
    new_balance = db.get_balance(user_id)

    # Clean up state exactly as in handle_game_over
    del user_games[chat_id][user_id]
    if not user_games[chat_id]:
        del user_games[chat_id]

    # Let the user know
    await update.message.reply_text(
        f"🛑 Game cancelled. Your bet of {game.bet_amount} Hiwa has been refunded.\n"
        f"Current balance: {new_balance} Hiwa"
    )

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /daily command."""
    user_id = update.effective_user.id
    last_daily = db.get_last_daily(user_id)
    
    if last_daily and (datetime.datetime.now() - last_daily).total_seconds() < 24 * 3600:
        next_claim = last_daily + datetime.timedelta(hours=24)
        await update.message.reply_text(
            f"You've already claimed your daily bonus today.\n"
            f"Next claim available at {next_claim.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return
    
    amount = 50  # Daily bonus amount
    db.add_balance(user_id, amount)
    db.set_last_daily(user_id, datetime.datetime.now())
    await update.message.reply_text(
        f"🎁 You claimed your daily bonus of {amount} Hiwa!\n"
        f"New balance: {db.get_balance(user_id)} Hiwa"
    )

async def weekly_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weekly command."""
    user_id = update.effective_user.id
    last_weekly = db.get_last_weekly(user_id)
    
    if last_weekly and (datetime.datetime.now() - last_weekly).total_seconds() < 7 * 24 * 3600:
        next_claim = last_weekly + datetime.timedelta(days=7)
        await update.message.reply_text(
            f"You've already claimed your weekly bonus this week.\n"
            f"Next claim available at {next_claim.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return
    
    amount = 200  # Weekly bonus amount
    db.add_balance(user_id, amount)
    db.set_last_weekly(user_id, datetime.datetime.now())
    await update.message.reply_text(
        f"🎁 You claimed your weekly bonus of {amount} Hiwa!\n"
        f"New balance: {db.get_balance(user_id)} Hiwa"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    top = db.get_top_users(10)  # now returns (id, username, first_name, balance)
    if not top:
        return await update.message.reply_text("🏆 Leaderboard is empty!")

    lines = ["🏆 **TOP PLAYERS** 🏆\n"]
    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, username, first_name, balance) in enumerate(top, start=1):
        # pick medal emoji or numeric rank
        prefix = medals[i-1] if i <= 3 else f"{i}."
        # if they have a Telegram @username, use it verbatim;
        # otherwise mention them by name & ID so Telegram links it
        # Always use first name with user ID link
        mention = f"[{first_name}](tg://user?id={uid})"

        lines.append(f"{prefix} {mention} — **{balance:,}** Hiwa")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode='Markdown'
    )

async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gift command."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /gift @username <amount>")
        return
    
    try:
        recipient_username = context.args[0].lstrip('@')
        amount = int(context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /gift @username <amount>")
        return
    
    if amount < 1:
        await update.message.reply_text("Amount must be at least 1 Hiwa.")
        return
    
    sender_id = update.effective_user.id
    recipient_id = db.get_user_id_by_username(recipient_username)
    
    if not recipient_id:
        await update.message.reply_text(f"User @{recipient_username} not found.")
        return
    
    if sender_id == recipient_id:
        await update.message.reply_text("You can't gift yourself!")
        return
    
    if not db.has_sufficient_balance(sender_id, amount):
        await update.message.reply_text("Insufficient balance for this gift.")
        return
    
    db.deduct_balance(sender_id, amount)
    db.add_balance(recipient_id, amount)
    
    sender_balance = db.get_balance(sender_id)
    recipient_balance = db.get_balance(recipient_id)
    
    await update.message.reply_text(
        f"🎁 You gifted {amount} Hiwa to @{recipient_username}!\n"
        f"Your new balance: {sender_balance} Hiwa"
    )
    
    # Notify recipient
    await context.bot.send_message(
        chat_id=recipient_id,
        text=f"🎁 You received {amount} Hiwa from @{update.effective_user.username}!\n"
             f"New balance: {recipient_balance} Hiwa"
    )

from telegram.constants import ParseMode
from telegram import MessageEntity, User

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = ' '.join(context.args)

    # Send to all users privately
    user_ids = db.get_all_user_ids()
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except:
            pass  # Ignore failures (e.g., user blocked the bot)

    # Create silent mentions for the group
    text = message + "\n\n"
    entities = []
    offset = len(text)
    for user_id in user_ids:
        # Mention will not be visible, but will notify the user
        mention_text = "."
        text += mention_text
        entities.append(MessageEntity(type="text_mention", offset=offset, length=1, user=User(id=user_id, first_name="User")))
        offset += 1

    try:
        await context.bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            text=text,
            entities=entities,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to send to group chat: {e}")
    else:
        await update.message.reply_text("Broadcast sent to all users and group chat.")

async def admin_reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to reset all user data."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return
    
    db.reset_all_data()
    await update.message.reply_text("All user data has been reset.")

async def admin_set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to set a user's balance."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbalance @username <amount>")
        return
    
    try:
        username = context.args[0].lstrip('@')
        amount = int(context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /setbalance @username <amount>")
        return
    
    target_id = db.get_user_id_by_username(username)
    if not target_id:
        await update.message.reply_text(f"User @{username} not found.")
        return
    
    db.set_balance(target_id, amount)
    await update.message.reply_text(f"Set @{username}'s balance to {amount} Hiwa.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(config.TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("mine", start_game))
    application.add_handler(CommandHandler("cashout", cashout_command))
    application.add_handler(CommandHandler("end", end_game))
    application.add_handler(CommandHandler("daily", daily_bonus))
    application.add_handler(CommandHandler("weekly", weekly_bonus))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("gift", gift))
    
    # Admin commands
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("resetdata", admin_reset_data))
    application.add_handler(CommandHandler("setbalance", admin_set_balance))
    
    # Button click handler
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
    
