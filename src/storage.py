import json
import os

class RegulationStorage:
    def __init__(self, file_path="regulations.json"):
        self.file_path = file_path
        self.regulations = self._load_data()

    def _load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []

    def save_data(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.regulations, f, ensure_ascii=False, indent=4)

    def add_regulation(self, regulation):
        for reg in self.regulations:
            if reg["title"] == regulation["title"]:
                return False
        self.regulations.append(regulation)
        self.save_data()
        return True

    def get_all_regulations(self):
        return self.regulations

    def search_regulations(self, query):
        query = query.lower()
        results = []
        for reg in self.regulations:
            if query in reg["title"].lower() or query in reg["content"].lower():
                results.append(reg)
        return results

