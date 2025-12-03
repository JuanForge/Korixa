class db:
    def __init__(self):
        db = {}
        db["user"] = {}
        salon = []
        for i in range(8):
            salon.append({"id": str(i), "name": f"salon Francais#{i}", "type": "chat", "chat": []})
        for i in range(4):
            i += 8
            salon.append({"id": str(i), "name": f"salon Francais#{i}", "type": "audio"})
        db["salon"] = salon
        # db["salon"] = [{"id": "0", "name": "salon Francais", "type": "chat", "chat": []}]
        self.db = db
    def Register():
        pass