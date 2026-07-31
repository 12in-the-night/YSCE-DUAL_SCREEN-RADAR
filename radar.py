import sys
import pygame

# ==========================================
# 1. WAKE UP PYGAME & SETUP SCREEN MONITOR
# ==========================================
pygame.init()                          # Wake up graphics engine rock
info = pygame.display.Info()           # Look at computer monitor dimensions
w, h = info.current_w, info.current_h  # Grab monitor width (w) and height (h)

# Open giant full-screen borderless window on monitor
screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN)
pygame.display.set_caption("why did i chose this project blink 2 for help while debuging it")
clock = pygame.time.Clock()            # Create timer clock to lock speed at 60 FPS

# ==========================================
# 2. TELEMETRY DATA ROCKS (LEATHER POUCHES)
# ==========================================
# Player ship status pouch
player = {"gear": False, "flaps": 0, "fuel": 1000, "weaponId": 1, "targetLockId": 101}

# Enemy and friendly planes list (each has ID, position X/Z, team color, locks)
planes = [
    {"id": 101, "x": 2000, "z": 3000, "team": 1, "isLocked": True, "missileWarning": True},# Enemy ID 101
    {"id": 101, "x": 200, "z": 300, "team": 1, "isLocked": True, "missileWarning": True},
    {"id": 102, "x": -1500, "z": -2000, "team": 0, "isLocked": False, "missileWarning": False} # Friend ID 102
]

# Ground targets and runways list
grounds = [
    {"id": 201, "x": -3000, "z": 4000, "name": "SAM SITE", "hp": 100, "isRunway": False},
    {"id": 203, "x": -3000, "z": 4000, "name": "SAM SITE", "hp": 100, "isRunway": False},
    {"id": 202, "x": 0, "z": -4000, "name": "RUNWAY 09", "hp": 0, "isRunway": True}
]

max_range = 10000  # Max radar view distance in meters

# ==========================================
# 3. CHISEL FONT STAMPS (BIG TEXT)
# ==========================================
font = pygame.font.SysFont("monospace", 28, bold=True)       # Big font for bottom bar
small_font = pygame.font.SysFont("monospace", 20, bold=True) # Big font for IDs and text

# ==========================================
# 4. MAIN GAME LOOP (RUNS 60 TIMES PER SECOND)
# ==========================================
running = True
while running:
    
    # Check if pilot press keys on keyboard
    for event in pygame.event.get():
        # If window close clicked OR ESC key pressed -> break loop and exit cave!
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    # Paint entire screen pitch black (wipe old frame clean)
    screen.fill((0, 10, 10))

    # Calculate radar circle center and dimensions
    bar_height = 90
    radar_h = h - bar_height
    center_x = w // 2
    center_y = radar_h // 2
    radius = int(min(center_x, center_y) * 0.85)

    # ------------------------------------------
    # DRAW RADAR SCOPE CIRCLES & PLAYER CENTER
    # ------------------------------------------
    pygame.draw.circle(screen, (0, 255, 0), (center_x, center_y), radius, 3)     # Outer green radar ring
    pygame.draw.circle(screen, (0, 68, 0), (center_x, center_y), int(radius * 0.5), 2) # Inner radar ring
    pygame.draw.circle(screen, (255, 255, 0), (center_x, center_y), 6)           # Player yellow dot in middle

    # ------------------------------------------
    # DRAW GROUND TARGETS & RUNWAYS
    # ------------------------------------------
    for g in grounds:
        # Convert world coordinates (x, z) into screen pixel coordinates (sx, sy)
        sx = int(center_x + (g["x"] / max_range) * radius)
        sy = int(center_y - (g["z"] / max_range) * radius)

        if g["isRunway"]:
            # Draw grey runway rectangle box
            pygame.draw.rect(screen, (20, 136, 136), (sx - 14, sy - 4, 28, 8))
            # Chisel runway text stamp and place it above runway
            txt = small_font.render(f"ID:{g['id']} RUNWAY", True, (255, 255, 255))
            screen.blit(txt, (sx - 30, sy - 24))
        else:
            # Draw orange SAM site square box
            pygame.draw.rect(screen, (255, 170, 0), (sx - 6, sy - 6, 12, 12))
            # Chisel SAM text stamp with ID and HP, place it next to box
            txt = small_font.render(f"ID:{g['id']} {g['name']}", True, (255, 170, 0))
            screen.blit(txt, (sx + 10, sy - 10))

    # ------------------------------------------
    # DRAW PLANES & ENEMY ID NUMBERS
    # ------------------------------------------
    for p in planes:
        # Convert plane world coordinates into screen pixels
        sx = int(center_x + (p["x"] / max_range) * radius)
        sy = int(center_y - (p["z"] / max_range) * radius)

        # Pick color: Red if enemy (team 1), Green if friend (team 0)
        color = (255, 0, 0) if p["team"] == 1 else (0, 255, 0)
        
        # Draw dot blip for plane
        pygame.draw.circle(screen, color, (sx, sy), 8)

        # STAMP ENEMY ID NUMBER NEXT TO DOT:
        # 1. Grab ID from pouch -> format into string "ID:101"
        # 2. Chisel into image stamp using small_font
        id_txt = small_font.render(f"ID:{p['id']}", True, color)
        # 3. Stamp image onto screen 12 pixels right and 10 pixels up from dot
        screen.blit(id_txt, (sx + 12, sy - 10))

        # If enemy lock on player, draw yellow target ring around dot
        if p["isLocked"]:
            pygame.draw.circle(screen, (255, 255, 0), (sx, sy), 14, 2)

        # If missile incoming, stamp red "LOCK!" warning text above dot
        if p["missileWarning"]:
            warn_txt = small_font.render("LOCK!", True, (255, 0, 0))
            screen.blit(warn_txt, (sx - 15, sy - 30))

    # ------------------------------------------
    # DRAW BOTTOM STATUS BAR
    # ------------------------------------------
    # Draw dark grey bar rectangle across bottom of screen
    pygame.draw.rect(screen, (17, 17, 17), (0, radar_h, w, bar_height))
    # Draw bright green dividing line above bar
    pygame.draw.line(screen, (0, 255, 0), (0, radar_h), (w, radar_h), 3)

    # Format player stats text string
    gear_txt = "DOWN" if player["gear"] else "UP"
    bar_text = f"WEAPON: {player['weaponId']} | LOCK ID: {player['targetLockId']} | GEAR: {gear_txt} | FLAPS: {player['flaps']}% | FUEL: {player['fuel']} LBS"
    
    # Chisel status text into image stamp and paste onto bottom bar
    text_surface = font.render(bar_text, True, (0, 255, 0))
    screen.blit(text_surface, (20, radar_h + 30))

    # ==========================================
    # 5. FLIP SCREEN & WAIT FOR NEXT FRAME
    # ==========================================
    pygame.display.flip()  # Push completed drawing to monitor display rock
    clock.tick(30)         # Wait to maintain steady 60 frames per second

# Quit Pygame engine safely when loop break
pygame.quit()
sys.exit()