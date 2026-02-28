import copy


class FireSystem:
    def __init__(self, width, height, speed_n=3):
        self.width = width
        self.height = height
        self.grid = [[0 for _ in range(width)] for _ in range(height)]
        self.ticks = 0
        self.speed_n = speed_n  # Пожар распространяется каждые N тиков

    def set_wall(self, x, y):
        self.grid[y][x] = -1

    def set_source(self, x, y):
        self.grid[y][x] = 999  # Уникальный индекс для очага

    def get_neighbors(self, x, y):
        """Возвращает координаты соседей (без диагоналей)"""
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                neighbors.append((nx, ny))
        return neighbors

    def update(self):
        self.ticks += 1
        # Проверяем, наступил ли нужный тик для распространения
        if self.ticks % self.speed_n != 0:
            return False

        new_grid = copy.deepcopy(self.grid)

        for y in range(self.height):
            for x in range(self.width):
                current = self.grid[y][x]

                # 1. Если это очаг — он остается очагом (999)
                if current == 999:
                    # Очаг заражает соседей индексом 1
                    for nx, ny in self.get_neighbors(x, y):
                        if self.grid[ny][nx] == 0:
                            new_grid[ny][nx] = 1

                # 2. Если это клетка пожара (индекс >= 1)
                elif current >= 1 and current < 999:
                    # Сама клетка увеличивает индекс (стареет)
                    new_grid[y][x] = current + 1
                    # Заражает соседей индексом 1
                    for nx, ny in self.get_neighbors(x, y):
                        if self.grid[ny][nx] == 0:
                            new_grid[ny][nx] = 1

                # Стены (-1) и пустые клетки (0) без соседей-огня не меняются

        self.grid = new_grid
        return True

    def draw(self):
        print(f"--- Тик: {self.ticks} ---")
        for row in self.grid:
            line = ""
            for cell in row:
                if cell == -1:
                    line += "██ "  # Стена
                elif cell == 0:
                    line += ".  "  # Пусто
                elif cell == 999:
                    line += "🔥 "  # Очаг
                else:
                    line += f"{cell:<2} "  # Индекс пожара
            print(line)

sim = FireSystem(10, 6, speed_n=1) # Распространение каждый тик
sim.set_source(1, 1)
sim.set_wall(3, 0); sim.set_wall(3, 1); sim.set_wall(3, 2) # Стена-перегородка

for _ in range(10):
    sim.draw()
    sim.update()