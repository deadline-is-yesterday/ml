import copy
import math


class FireSystem:
    def __init__(self, width, height, speed_n=1):
        self.width = width
        self.height = height
        self.grid = [[0 for _ in range(width)] for _ in range(height)]
        self.ticks = 0
        self.speed_n = speed_n
        self.sources = []
        self.firetrucks = []
        self.active_water = {}

    def set_wall(self, x, y, wall_type=-100000):
        self.grid[y][x] = wall_type

    def set_source(self, x, y):
        self.sources.append((x, y))
        self.grid[y][x] = 1000

    def add_firetruck(self, x, y):
        self.firetrucks.append((x, y))

    def is_path_blocked(self, start_x, start_y, end_x, end_y):
        steps = max(abs(end_x - start_x), abs(end_y - start_y))
        if steps == 0: return False
        for i in range(1, steps):
            tx = int(start_x + (end_x - start_x) * i / steps)
            ty = int(start_y + (end_y - start_y) * i / steps)
            if 0 <= tx < self.width and 0 <= ty < self.height:
                if self.grid[ty][tx] < 0:
                    return True
        return False

    def spray_water(self, truck_x, truck_y, target_x, target_y, radius=8, amount=100):
        self.active_water.clear()
        main_angle = math.atan2(target_y - truck_y, target_x - truck_x)

        for y in range(self.height):
            for x in range(self.width):
                dx = x - truck_x
                dy = y - truck_y
                dist = math.hypot(dx, dy)

                if dist <= radius:
                    cell_angle = math.atan2(dy, dx)
                    diff = (cell_angle - main_angle + math.pi) % (2 * math.pi) - math.pi

                    if abs(diff) <= math.pi / 4:
                        if self.grid[y][x] >= 0:
                            if not self.is_path_blocked(truck_x, truck_y, x, y):
                                self.active_water[(x, y)] = True
                                if self.grid[y][x] > 0:
                                    self.grid[y][x] = round(max(0.0, self.grid[y][x] - amount), 2)

    def update(self):
        self.ticks += 1
        if self.ticks % self.speed_n != 0:
            return False

        new_grid = copy.deepcopy(self.grid)
        for y in range(self.height):
            for x in range(self.width):
                current = self.grid[y][x]
                if (x, y) in self.sources:
                    new_grid[y][x] = current + 1
                elif current >= 0:
                    surrounding_sum = 0
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0: continue
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                val = self.grid[ny][nx]
                                if val > 0: surrounding_sum += val
                    new_grid[y][x] = round(surrounding_sum / 8, 2)
                elif current < 0:
                    fire_neighbors = []
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0: continue
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                val = self.grid[ny][nx]
                                if val > 0: fire_neighbors.append(val)
                    if fire_neighbors:
                        if current == -1:
                            avg = sum(fire_neighbors) / len(fire_neighbors)
                            new_grid[y][x] = round(max(0.1, avg - 3), 2)
                        else:
                            new_grid[y][x] = current + 1
        self.grid = new_grid
        return True

    def draw(self):
        print(f"\n--- Тик: {self.ticks} ---")
        for y in range(self.height):
            line = ""
            for x in range(self.width):
                cell = self.grid[y][x]
                if (x, y) in self.firetrucks:
                    line += "🚒      "
                elif cell < 0:
                    line += f"{int(cell):<7} "
                elif (x, y) in self.active_water:
                    val_str = f"{cell:.1f}" if cell > 0 else "0"
                    line += f"💧{val_str:<5} "
                elif (x, y) in self.sources:
                    line += f"🔥{int(cell):<5} "
                elif cell == 0:
                    line += ".       "
                else:
                    line += f"{cell:<7.2f} "
            print(line)


sim = FireSystem(15, 12, speed_n=1)

for x in range(3, 12): sim.set_wall(x, 2)
for y in range(3, 7):
    sim.set_wall(3, y)
    sim.set_wall(11, y)

sim.set_source(7, 4)
sim.add_firetruck(7, 10)

for i in range(40):
    if i >= 10:
        sim.spray_water(truck_x=7, truck_y=10, target_x=7, target_y=4, radius=9, amount=100)
    else:
        sim.active_water.clear()
    sim.draw()
    sim.update()