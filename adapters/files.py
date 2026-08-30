class FileKeyProvider:
    def __init__(self):
        self.filepath = "keys.txt"
        self._keys = []
        self._load_keys()

    def _load_keys(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self._keys = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"ВНИМАНИЕ: Файл с ключами {self.filepath} не найден!")
            self._keys = []

    @property
    def keys(self):
        if not self._keys:
            raise ValueError("Нет доступных ключей!")
        return self._keys

