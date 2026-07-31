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
pygame.display.set_caption("why did i chose this project blink 2 for help while debuging it")
clock = pygame.time.Clock()            # Create a frame-timer for throttling the loop

# ==========================================
# 2. TELEMETRY DATA STRUCTURES
# ==========================================
# Player aircraft state
player = {"gear": False, "flaps": 0, "fuel": 1000, "weaponId": 1, "targetLockId": 101}

# Aircraft list: id, world position, team side, lock state, and missile warning state
planes = [
    {"id": 101, "x": 2000, "z": 3000, "team": 1, "isLocked": True, "missileWarning": True},# Enemy ID 101
    {"id": 101, "x": 200, "z": 300, "team": 1, "isLocked": True, "missileWarning": True},
    {"id": 102, "x": -1500, "z": -2000, "team": 0, "isLocked": False, "missileWarning": False} # Friend ID 102
]

# Ground objects: SAM sites and runways
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

running = True
while running:
    for event in pygame.event.get():
        # If pilot click the red 'X' button to close window
        if event.type == pygame.QUIT:
            running = False
            
        # Catch window focus changes (when clicking away or clicking back)
        elif event.type == pygame.ACTIVEEVENT:
            # event.gain tells if window gained (1) or lost (0) focus
            # Game keep running safe either way!
            pass
            
        # Catch key presses (if pilot press Escape to quit)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
    # --- EVENT GUARD END ---

    # Game drawing and radar math goes here after guard!
    screen.fill((0, 0, 0)) # Clear screen black rock
    pygame.display.flip()
    
    # Process input events from the OS and keyboard
    for event in pygame.event.get():
        # Close the loop on window close or ESC key press
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    # Clear the screen for the next frame
    screen.fill((0, 1, 1))


    # ------------------------------------------
    # DRAW RADAR SCOPE RINGS AND PLAYER CENTER
    # ------------------------------------------
    pygame.draw.circle(screen, (0, 255, 0), (center_x, center_y), radius, 3)     # Outer radar ring
    pygame.draw.circle(screen, (0, 68, 0), (center_x, center_y), int(radius * 0.5), 2) # Inner radar ring
    pygame.draw.circle(screen, (255, 255, 0), (center_x, center_y), 6)           # Player marker at the center

    # ------------------------------------------
    # DRAW GROUND TARGETS AND RUNWAYS
    # ------------------------------------------
    for g in grounds:
        # Convert world-space coordinates (x, z) into screen-space coordinates (sx, sy)
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
    # Draw the dark panel across the bottom of the screen
    pygame.draw.rect(screen, (19,25 ,30 ), (0, radar_h, w, bar_height))
    # Draw a bright green separator line above the status bar
    pygame.draw.line(screen, (0, 255, 27), (0, radar_h), (w, radar_h), 3)

    # Build the player status text line
    gear_txt = "DOWN" if player["gear"] else "UP"
    bar_text = f"WEAPON: {player['weaponId']} | LOCK ID: {player['targetLockId']} | GEAR: {gear_txt} | FLAPS: {player['flaps']}% | FUEL: {player['fuel']} mtrics"
    
    # Render and place the status text in the bottom panel
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