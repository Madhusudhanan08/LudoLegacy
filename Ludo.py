import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from game import GameManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
manager = GameManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *Welcome to THE SYSTEM*\n\n"
        "A dungeon awaits. Capture it before anyone else.\n\n"
        "/play — Create or join a game\n"
        "/profile — Your profile\n"
        "/leaderboard — Top dungeon owners",
        parse_mode="Markdown"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    room_id, created = manager.create_or_join(user.id, user.username or user.first_name)
    room = manager.get_room(room_id)
    count = len(room['players'])
    player_list = "\n".join([f"• {p['name']}" for p in room['players']])

    keyboard = []
    if count >= 2:
        keyboard.append([InlineKeyboardButton("⚔️ START", callback_data=f"start_{room_id}")])
    keyboard.append([InlineKeyboardButton("🚪 Leave", callback_data=f"leave_{room_id}")])

    await update.message.reply_text(
        f"🏰 *DUNGEON LOBBY* | Room: `{room_id}`\n\n"
        f"Players ({count}/6):\n{player_list}\n\n"
        f"{'✅ Ready!' if count >= 2 else '⏳ Waiting for players...'}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    if count == 6:
        await begin_game(update, context, room_id)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = manager.db.get_player(user.id, user.username or user.first_name)
    xp_thresholds = [100, 200, 300, 400, None]
    next_xp = xp_thresholds[p['level'] - 1]
    xp_str = f"{p['xp']}/{next_xp} XP" if next_xp else "MAX LEVEL"
    await update.message.reply_text(
        f"👤 *{p['name']}*\n🏰 Land: _{p['land_name']}_\n\n"
        f"⚔️ Level: {p['level']}/5\n💰 XP: {xp_str}\n"
        f"🏆 Dungeons: {len(p['dungeons'])}\n⭐ Stars: {p['stars']}",
        parse_mode="Markdown"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = manager.db.get_leaderboard()
    if not board:
        await update.message.reply_text("No dungeons captured yet. Be the first! ⚔️")
        return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    lines = [f"{medals[i]} *{p['name']}* — {len(p['dungeons'])} dungeons"
             for i, p in enumerate(board[:5])]
    await update.message.reply_text(
        "🏆 *THE SYSTEM LEADERBOARD*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        room_id = data.split("_",1)[1]
        room = manager.get_room(room_id)
        if not room: return
        if len(room['players']) < 2:
            await query.answer("Need at least 2 players!", show_alert=True)
            return
        await begin_game(query, context, room_id)

    elif data.startswith("leave_"):
        room_id = data.split("_",1)[1]
        manager.leave_room(update.effective_user.id, room_id)
        await query.edit_message_text("👋 You left the lobby.")

    elif data.startswith("roll_"):
        await handle_roll(query, context, data.split("_",1)[1])

    elif data.startswith("move_"):
        _, room_id, piece_id = data.split("_", 2)
        await handle_move(query, context, room_id, piece_id)

async def begin_game(upd, context, room_id):
    if not manager.start_game(room_id): return
    room = manager.get_room(room_id)
    current = room['players'][room['turn_index']]
    msg = (f"⚔️ *THE DUNGEON OPENS!*\n\n"
           f"Players: {', '.join(p['name'] for p in room['players'])}\n\n"
           f"🎲 {current['name']}'s turn! ({current['turn_time']}s)\n"
           f"⭐ {current['stars']} stars | 💰 {current['xp']} xp")
    kb = [[InlineKeyboardButton("🎲 ROLL DICE", callback_data=f"roll_{room_id}")]]
    fn = upd.message.reply_text if hasattr(upd, 'message') else upd.edit_message_text
    await fn(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def handle_roll(query, context, room_id):
    user = query.from_user
    room = manager.get_room(room_id)
    if not room or not room['started']: return
    current = room['players'][room['turn_index']]
    if current['id'] != user.id:
        await query.answer("Not your turn! ❌", show_alert=True)
        return

    result = manager.roll_dice(room_id)
    roll = result['roll']
    movable = result['movable_pieces']
    msg = f"🎲 *{current['name']} rolled {roll}!*\n⭐ {current['stars']} | 💰 {current['xp']}xp\n\n"

    if not movable:
        manager.next_turn(room_id)
        nxt = manager.get_current_player(room_id)
        msg += f"No moves! Passing to {nxt['name']}..."
        kb = [[InlineKeyboardButton("🎲 ROLL DICE", callback_data=f"roll_{room_id}")]]
    else:
        msg += "Choose piece to move:"
        kb = [[InlineKeyboardButton(
            f"{p['role'][0].upper()} — tile {p['position']}",
            callback_data=f"move_{room_id}_{p['id']}"
        )] for p in movable]

    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def handle_move(query, context, room_id, piece_id):
    user = query.from_user
    room = manager.get_room(room_id)
    current = room['players'][room['turn_index']]
    if current['id'] != user.id:
        await query.answer("Not your turn! ❌", show_alert=True)
        return

    result = manager.move_piece(room_id, piece_id)
    msg = f"♟️ *{current['name']}* moved {result['piece_role']} → tile {result['new_position']}\n\n"

    if result.get('domain'):
        msg += "🔴 *DOMAIN!*\n"
        if result['piece_role'] == 'Attacker' and current['stars'] > 0:
            msg += f"💥 Cleave ready! (Strength {result['roll']})\n"
        elif result['piece_role'] == 'Tanker':
            msg += f"🛡️ Tank power: {result['roll']}\n"

    if result.get('combat'):
        msg += f"⚔️ Opponent sent home! +{result['xp_gained']}xp\n"
        if result.get('star_gained'):
            msg += "⭐ Star refilled!\n"

    if result.get('winner'):
        await handle_win(query, context, room_id, current)
        return

    manager.next_turn(room_id)
    nxt = manager.get_current_player(room_id)
    msg += f"\n🎲 {nxt['name']}'s turn! ({nxt['turn_time']}s)"
    kb = [[InlineKeyboardButton("🎲 ROLL DICE", callback_data=f"roll_{room_id}")]]
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def handle_win(query, context, room_id, winner):
    standings = manager.get_standings(room_id)
    rewards = [(50,"50xp + dungeon 🏰"),(50,"50xp"),(30,"30xp"),(25,"25xp"),(10,"10xp"),(10,"10xp")]
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣"]
    lines = []
    for i, player in enumerate(standings):
        xp, label = rewards[i] if i < len(rewards) else (0,"")
        manager.db.add_xp(player['id'], xp)
        lines.append(f"{medals[i]} {player['name']} — {label}")

    context.bot_data[f"naming_{room_id}"] = winner['id']
    await query.edit_message_text(
        f"🏆 *{winner['name']} CAPTURED THE DUNGEON!*\n\n"
        + "\n".join(lines) +
        f"\n\n🏰 Name your dungeon:\n`/namedungeon <name>`",
        parse_mode="Markdown"
    )

async def name_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /namedungeon <name>")
        return
    name = " ".join(context.args)
    room_id = next((k.split("_",1)[1] for k, v in context.bot_data.items()
                    if k.startswith("naming_") and v == user.id), None)
    if not room_id:
        await update.message.reply_text("No dungeon waiting to be named!")
        return
    manager.db.add_dungeon(user.id, name)
    del context.bot_data[f"naming_{room_id}"]
    manager.close_room(room_id)
    await update.message.reply_text(
        f"🏰 *{name}* added to your land!\nYour empire grows... ⚔️",
        parse_mode="Markdown"
    )
    
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /join <room code>\nExample: /join ABC123")
        return
    room_id = context.args[0].upper()
    success, msg = manager.join_room(room_id, user.id, user.username or user.first_name)
    if not success:
        await update.message.reply_text(f"❌ {msg}")
        return
    room = manager.get_room(room_id)
    count = len(room['players'])
    player_list = "\n".join([f"• {p['name']}" for p in room['players']])
    keyboard = []
    if count >= 2:
        keyboard.append([InlineKeyboardButton("⚔️ START GAME", callback_data=f"start_{room_id}")])
    keyboard.append([InlineKeyboardButton("🚪 Leave", callback_data=f"leave_{room_id}")])
    # Notify host
    host = room['players'][0]
    try:
        await context.bot.send_message(
            chat_id=host['id'],
            text=f"👥 *{user.username or user.first_name} joined your lobby!*\n\n"
                 f"Players ({count}/6):\n{player_list}\n\n"
                 f"{'✅ Ready to start!' if count >= 2 else '⏳ Waiting for more players...'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        pass 
    await update.message.reply_text(
        f"✅ *Joined successfully!*\n\n"
        f"🏰 *DUNGEON LOBBY* | Room: `{room_id}`\n\n"
        f"Players ({count}/6):\n{player_list}\n\n"
        f"{'✅ Ready to start!' if count >= 2 else '⏳ Waiting for more players...'}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN not set!")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("namedungeon", name_dungeon))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("⚔️ The System is running...")
    app.run_polling()

if __name__ == "__main__":
    main()