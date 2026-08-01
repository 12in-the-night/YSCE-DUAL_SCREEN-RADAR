import sys
import pygame
# ==========================================
# 1. INITIALIZE PYGAME AND THE DISPLAY
# ==========================================
pygame.init()                          # Initialize the Pygame subsystems
info = pygame.display.Info()           # Read the current desktop display size
w, h = info.current_w, info.current_h  # Store the full-screen window dimensions

# Create a borderless full-screen window on the primary display
screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN)
# Set the window title shown in the OS window manager
pygame.display.set_caption("why did i chose this project blink 2 for help while debuging it")
clock = pygame.time.Clock()            # Create a frame-timer for throttling the loop

# ==========================================
# 2. TELEMETRY DATA STRUCTURES
# ==========================================
# Player aircraft state
player = {"gear": False, "flaps": 0, "fuel": 1000, "weaponId": 1, "targetLockId": 101}

# Aircraft list: id, world position, team side, lock state, and missile warning state
# team=1 is treated as hostile; team=0 is treated as friendly
planes = [
    {"id": 101, "x": 2000, "z": 3000, "team": 1, "isLocked": True, "missileWarning": True},# Enemy ID 101
    {"id": 102, "x": 200, "z": 300, "team": 1, "isLocked": True, "missileWarning": True},
    {"id": 103, "x": -1500, "z": -2000, "team": 0, "isLocked": False, "missileWarning": False} # Friend ID 102
]

# Ground objects: SAM sites and runways
# isRunway=True means draw a runway marker instead of a SAM-site icon
grounds = [
    {"id": 201, "x": -3000, "z": 4000, "name": "SAM SITE", "hp": 100, "isRunway": False},
    {"id": 203, "x": -3000, "z": 4000, "name": "SAM SITE", "hp": 100, "isRunway": False},
    {"id": 202, "x": 0, "z": -4000, "name": "RUNWAY 09", "hp": 0, "isRunway": True}
]

max_range = 5000  # Maximum radar display radius in world units

# ==========================================
# 3. FONT SETUP
# ==========================================
font = pygame.font.SysFont("monospace", 28, bold=True)       # Font for the bottom status bar
small_font = pygame.font.SysFont("monospace", 20, bold=True) # Font for labels and small text

# ==========================================
# 4. MAIN GAME LOOP
# ==========================================
# Compute the radar scope center and radius from the current window size
bar_height = 69
radar_h = h - bar_height
center_x = w // 2
center_y = radar_h // 2
radius = int(min(center_x, center_y) * 0.85)

# Expand the radar range just enough to cover the farthest tracked object
# and provide a small safety margin around the visible edge.
for p in planes:
    # Calculate the straight-line distance from the origin to each aircraft.
    dist = (p["x"] ** 2 + p["z"] ** 2) ** 0.5
    if dist > max_range:
        max_range = dist

# Add a small safety buffer to the display scale so targets do not sit exactly on the edge.
max_range += 300

running = True
while running:
    # Read all pending events and react to quit or escape input.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    # Clear the drawing surface at the start of each frame.
    screen.fill((0, 1, 1))


    # ------------------------------------------
    # DRAW RADAR SCOPE RINGS AND PLAYER CENTER
    # ------------------------------------------
    # Draw the outer detection boundary and the inner guide ring.
    pygame.draw.circle(screen, (0, 255, 0), (center_x, center_y), radius, 3)     # Outer radar ring
    pygame.draw.circle(screen, (0, 68, 0), (center_x, center_y), int(radius * 0.5), 2) # Inner radar ring
    # Draw a small bright marker at the radar center to represent the player aircraft.
    pygame.draw.circle(screen, (255, 255, 0), (center_x, center_y), 6)           # Player marker at the center

    # ------------------------------------------
    # DRAW GROUND TARGETS AND RUNWAYS
    # ------------------------------------------
    for g in grounds:
        # Project world coordinates into a radar-relative screen position
        # using a simple scale based on max_range and the drawn radar radius.
        sx = int(center_x + (g["x"] / max_range) * radius)
        sy = int(center_y - (g["z"] / max_range) * radius)

        if g["isRunway"]:
            # Draw a cyan runway marker rectangle
            pygame.draw.rect(screen, (20, 200, 200), (sx - 14, sy - 4, 28, 8))
            # Render and place the runway label above the marker
            txt = small_font.render(f"ID:{g['id']} RUNWAY", True, (255, 255, 255))
            screen.blit(txt, (sx - 30, sy - 24))
        else:
            # Draw an orange SAM-site marker square
            pygame.draw.rect(screen, (255, 170, 0), (sx - 6, sy - 6, 12, 12))
            # Render and place the SAM label near the marker
            txt = small_font.render(f"ID:{g['id']} {g['name']}", True, (255, 170, 0))
            screen.blit(txt, (sx + 10, sy - 10))

    # ------------------------------------------
    # DRAW AIRCRAFT TARGETS AND LABELS
    # ------------------------------------------
    for p in planes:
        # Convert aircraft world coordinates into screen-space coordinates
        # so the radar blip stays centered on the scope and scales with the range.
        sx = int(center_x + (p["x"] / max_range) * radius)
        sy = int(center_y - (p["z"] / max_range) * radius)

        # Use red for hostile aircraft and green for friendly aircraft
        color = (255, 0, 0) if p["team"] == 1 else (0, 200, 55)
        
        # Draw the aircraft blip on the radar scope
        pygame.draw.circle(screen, color, (sx, sy), 8)

        # Render the aircraft ID label next to its blip
        id_txt = small_font.render(f"ID:{p['id']}", True, color)
        screen.blit(id_txt, (sx - 12, sy + 10))

        # Draw a white ring when the aircraft currently has a lock on the player
        if p["isLocked"]:
            pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 14, 2)

        # Draw the missile warning text above the blip when a missile warning is active
        if p["missileWarning"]:
            warn_txt = small_font.render("MISSILE!!-MISSILE!!", True, (255, 0, 0))
            screen.blit(warn_txt, (sx - 15, sy - 30))

    # ------------------------------------------
    # DRAW THE STATUS BAR
    # ------------------------------------------
    # Draw the dark panel across the bottom of the screen for the HUD readout
    pygame.draw.rect(screen, (19,25 ,30 ), (0, radar_h, w, bar_height))
    # Draw a bright green separator line above the status bar to visually split HUD sections
    pygame.draw.line(screen, (0, 255, 27), (0, radar_h), (w, radar_h), 3)

    # Build the player status text line shown in the HUD bar.
    gear_txt = "DOWN" if player["gear"] else "UP"
    bar_text = f"WEAPON: {player['weaponId']} | LOCK ID: {player['targetLockId']} | GEAR: {gear_txt} | FLAPS: {player['flaps']}% | FUEL: {player['fuel']} meters"
    
    # Render and place the status text in the bottom panel.
    text_surface = font.render(bar_text, True, (0, 255, 0))
    screen.blit(text_surface, (20, radar_h + 30))

    # ==========================================
    # 5. FLIP THE DISPLAY BUFFER
    # ==========================================
    pygame.display.flip()  # Present the completed frame to the screen
    clock.tick(30)         # Limit the loop to about 30 frames per second

# Shut down Pygame cleanly when the loop ends
pygame.quit()
sys.exit()