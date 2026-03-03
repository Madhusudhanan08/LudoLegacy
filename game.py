import random
import uuid
from database import Database

COLORS = ["🔴", "🔵", "🟡", "🟢", "🟠", "🟣"]
BOARD_SIZE = 60
DOMAIN_TILES = [8, 16, 24, 32, 40, 48, 54, 58]
HOME_STRETCH_START = 55
XP_TABLE = {"Attacker": 30, "Tanker": 40, "Crewmate": 20}
LEVEL_TIMERS = {1: 15, 2: 20, 3: 25, 4: 30, 5: 35}

def make_pieces():
    return [
        {"id": str(uuid.uuid4())[:8], "role": "Attacker",  "position": -1, "tank_power": 0, "stored_cleaves": [], "tank_active": False},
        {"id": str(uuid.uuid4())[:8], "role": "Tanker",    "position": -1, "tank_power": 0, "stored_cleaves": [], "tank_active": False},
        {"id": str(uuid.uuid4())[:8], "role": "Crewmate",  "position": -1, "tank_power": 0, "stored_cleaves": [], "tank_active": False},
        {"id": str(uuid.uuid4())[:8], "role": "Crewmate",  "position": -1, "tank_power": 0, "stored_cleaves": [], "tank_active": False},
    ]

class GameManager:
    def __init__(self):
        self.rooms = {}
        self.db = Database()

    def create_or_join(self, user_id, name):
    room_id = str(uuid.uuid4())[:6].upper()
    profile = self.db.get_player(user_id, name)
    self.rooms[room_id] = {
        "started": False,
        "turn_index": 0,
        "last_roll": None,
        "finish_order": [],
        "players": [{
            "id": user_id,
            "name": name,
            "color": COLORS[0],
            "stars": 8,
            "xp": profile['xp'],
            "level": profile['level'],
            "turn_time": LEVEL_TIMERS[profile['level']],
            "pieces": make_pieces(),
            "finished": False,
            "finish_order": None
        }]
    }
    return room_id, True

def join_room(self, room_id, user_id, name):
    room = self.rooms.get(room_id)
    if not room:
        return False, "Room not found!"
    if room['started']:
        return False, "Game already started!"
    if len(room['players']) >= 6:
        return False, "Room is full!"
    if any(p['id'] == user_id for p in room['players']):
        return False, "You're already in this room!"
    profile = self.db.get_player(user_id, name)
    room['players'].append({
        "id": user_id,
        "name": name,
        "color": COLORS[len(room['players'])],
        "stars": 8,
        "xp": profile['xp'],
        "level": profile['level'],
        "turn_time": LEVEL_TIMERS[profile['level']],
        "pieces": make_pieces(),
        "finished": False,
        "finish_order": None
    })
    return True, "Joined!"

        # Create new room
        room_id = str(uuid.uuid4())[:6].upper()
        profile = self.db.get_player(user_id, name)
        self.rooms[room_id] = {
            "started": False,
            "turn_index": 0,
            "last_roll": None,
            "finish_order": [],
            "players": [{
                "id": user_id,
                "name": name,
                "color": COLORS[0],
                "stars": 8,
                "xp": profile['xp'],
                "level": profile['level'],
                "turn_time": LEVEL_TIMERS[profile['level']],
                "pieces": make_pieces(),
                "finished": False,
                "finish_order": None
            }]
        }
        return room_id, True

    def get_room(self, room_id):
        return self.rooms.get(room_id)

    def leave_room(self, user_id, room_id):
        room = self.rooms.get(room_id)
        if room:
            room['players'] = [p for p in room['players'] if p['id'] != user_id]
            if not room['players']:
                del self.rooms[room_id]

    def start_game(self, room_id):
        room = self.rooms.get(room_id)
        if not room or room['started']:
            return False
        random.shuffle(room['players'])
        for i, p in enumerate(room['players']):
            p['color'] = COLORS[i]
        room['started'] = True
        room['turn_index'] = 0
        return True

    def roll_dice(self, room_id):
        room = self.rooms[room_id]
        roll = random.randint(1, 6)
        room['last_roll'] = roll
        current = room['players'][room['turn_index']]

        movable = []
        for piece in current['pieces']:
            # Can bring out if roll is 1 or 6 and piece is at home
            if piece['position'] == -1 and roll in (1, 6):
                movable.append(piece)
            # Can move if piece is already on board
            elif piece['position'] >= 0 and piece['position'] < HOME_STRETCH_START:
                movable.append(piece)

        return {"roll": roll, "movable_pieces": movable}

    def move_piece(self, room_id, piece_id):
        room = self.rooms[room_id]
        current = room['players'][room['turn_index']]
        roll = room['last_roll']

        piece = next(p for p in current['pieces'] if p['id'] == piece_id)
        result = {
            "piece_role": piece['role'],
            "roll": roll,
            "new_position": 0,
            "domain": False,
            "combat": False,
            "xp_gained": 0,
            "star_gained": False,
            "winner": False
        }

        # Bring piece out
        if piece['position'] == -1:
            piece['position'] = 0
            result['new_position'] = 0
            return result

        # Move piece
        new_pos = piece['position'] + roll

        # Check home stretch / win
        if new_pos >= BOARD_SIZE:
            piece['position'] = BOARD_SIZE
            result['new_position'] = BOARD_SIZE
            # Check if all pieces finished
            if all(p['position'] == BOARD_SIZE for p in current['pieces']):
                result['winner'] = True
                current['finished'] = True
                room['finish_order'].append(current['id'])
            return result

        piece['position'] = new_pos
        result['new_position'] = new_pos

        # Domain check
        if new_pos in DOMAIN_TILES:
            result['domain'] = True
            if piece['role'] == 'Tanker':
                piece['tank_power'] = roll
                piece['tank_active'] = True
            elif piece['role'] == 'Attacker':
                piece['stored_cleaves'].append(roll)
                if len(piece['stored_cleaves']) > 2:
                    piece['stored_cleaves'].pop(0)

        # Combat check — did we land on an opponent?
        for opponent in room['players']:
            if opponent['id'] == current['id']:
                continue
            for opp_piece in opponent['pieces']:
                if opp_piece['position'] == new_pos:
                    # Basic combat — send home
                    opp_piece['position'] = -1
                    xp = XP_TABLE.get(opp_piece['role'], 20)
                    current['xp'] += xp
                    result['combat'] = True
                    result['xp_gained'] = xp

                    # Star refill check
                    stars_earned = current['xp'] // 50
                    if stars_earned > (current['xp'] - xp) // 50:
                        current['stars'] = min(current['stars'] + 1, 8)
                        result['star_gained'] = True

                    # Update db xp
                    self.db.add_xp(current['id'], xp)
                    break

        return result

    def next_turn(self, room_id):
        room = self.rooms[room_id]
        total = len(room['players'])
        room['turn_index'] = (room['turn_index'] + 1) % total

    def get_current_player(self, room_id):
        room = self.rooms[room_id]
        return room['players'][room['turn_index']]

    def get_standings(self, room_id):
        room = self.rooms[room_id]
        finished = [p for p in room['players'] if p['finished']]
        unfinished = [p for p in room['players'] if not p['finished']]
        return finished + unfinished

    def close_room(self, room_id):
        if room_id in self.rooms:
            del self.rooms[room_id]