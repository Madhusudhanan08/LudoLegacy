import json
import os

DB_FILE = "database.json"

class Database:
    def __init__(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"players": {}}
            self.save()

    def save(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_player(self, user_id, name):
        uid = str(user_id)
        if uid not in self.data["players"]:
            self.data["players"][uid] = {
                "id": user_id,
                "name": name,
                "land_name": name + "'s Land",
                "xp": 0,
                "level": 1,
                "stars": 8,
                "dungeons": []
            }
            self.save()
        return self.data["players"][uid]

    def add_xp(self, user_id, amount):
        p = self.get_player(user_id, "")
        uid = str(user_id)
        p["xp"] += amount
        xp_levels = [100, 200, 300, 400]
        if p["level"] < 5:
            needed = xp_levels[p["level"] - 1]
            if p["xp"] >= needed:
                p["level"] += 1
        self.data["players"][uid] = p
        self.save()

    def add_dungeon(self, user_id, dungeon_name):
        uid = str(user_id)
        p = self.get_player(user_id, "")
        p["dungeons"].append(dungeon_name)
        self.data["players"][uid] = p
        self.save()

    def get_leaderboard(self):
        players = list(self.data["players"].values())
        return sorted(players, key=lambda x: len(x["dungeons"]), reverse=True)