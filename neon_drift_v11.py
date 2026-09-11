# ================================================================
# NEON DRIFT — 3D Obstacle-Dodging Racing Game v2 (ENRICHED)
# PyOpenGL (GLUT / GL / GLU only)
# ================================================================

from OpenGL.GL   import *
from OpenGL.GLUT import *
from OpenGL.GLU  import *
import math, random, sys

# ──────────────────────────────────────────────────────────────
# WINDOW & WORLD CONSTANTS
# ──────────────────────────────────────────────────────────────
WIN_W, WIN_H  = 1100, 800

NUM_LANES     = 5
LANE_W        = 60
ROAD_HALF     = NUM_LANES * LANE_W // 2   # 150
LANE_CENTERS  = [-120, -60, 0, 60, 120]

WORLD_HALF    = 1800
GRID_STEP     = 80
SPAWN_AHEAD   = 1600
CULL_BEHIND   = 350
SEGMENT_GAP   = 325       # was 130 — ~2.5x larger gap = ~60% fewer spawns
COIN_COLLISION_RANGE = 70 # Distance for collecting coins/powerups

CAM_DY        = 110
CAM_DZ        = -260
LOOK_DZ       = 380

AUTO_CYCLE    = 60.0   # seconds per full day+night cycle
TRANS_DUR     = 3.0
POWERUP_MULTIPLIER_DURATION = 10 # seconds
INVINCIBILITY_DURATION = 15  # seconds

MINIMAP_X, MINIMAP_Y = 12, WIN_H - 260    # top-left, just below HUD bar
MINIMAP_W, MINIMAP_H = 140, 155

WHEEL_R = 14
WHEEL_W = 10

# ──────────────────────────────────────────────────────────────
# GAME STATE
# ──────────────────────────────────────────────────────────────
player_lane   = 2
player_z      = 0.0
player_x      = 0.0
wheel_angle   = 0.0
steer_lean    = 0.0

speed         = 30.0
score         = 0.0
health        = 5          # NEW: Player Health (5 hearts)
coins         = 0           # NEW: Coin Counter
game_state    = "play"
confirm_from_state = "play"   # state to restore if user clicks NO on restart dialog
fpv_mode      = False          # toggle with [C] — first-person camera attached to car front
powerup_multiplier = 1.0  # NEW: Current score multiplier (1.0 to 2.0)
invincible    = False      # NEW: Invincibility flag

day_factor    = 1.0
night_target  = 1.0
auto_day_time = 0.0
manual_override = False
multiplier_timer = 0.0 # NEW: Multiplier timer in seconds
invincible_timer = 0.0 # NEW: Invincibility timer in seconds

obstacles     = []
decorations   = []
particles     = []
spawn_z_next  = 600.0
last_time     = 0.0
bob_time      = 0.0   # global time for coin/powerup bobbing animation

# Fallen tree animation state: each entry is {ox, oz, side, angle, fallen}
fallen_trees  = []
# Coin spawn: track z intervals for regular coin rows
coin_row_next = 800.0
COIN_ROW_GAP  = 300.0   # every 300 units, a coin row appears

# ──────────────────────────────────────────────────────────────
# COLOR HELPERS
# ──────────────────────────────────────────────────────────────
def blend(ca, cb, t):
    t = max(0.0, min(1.0, t))
    return tuple(ca[i]*(1-t) + cb[i]*t for i in range(len(ca)))

def sky_col():
    return blend((0.01,0.01,0.09),(0.42,0.68,1.00), day_factor)
def road_col():
    return blend((0.04,0.04,0.07),(0.21,0.21,0.24), day_factor)
def grass_col():
    return blend((0.02,0.10,0.04),(0.14,0.48,0.18), day_factor)
def build_col():
    return blend((0.07,0.07,0.13),(0.50,0.50,0.56), day_factor)

def neon(r, g, b):
    boost = 1.0 + (1.0 - day_factor) * 2.8
    return (min(r*boost,1.0), min(g*boost,1.0), min(b*boost,1.0))

# ──────────────────────────────────────────────────────────────
# TEXT
# ──────────────────────────────────────────────────────────────
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text_lg(x, y, text):
    draw_text(x, y, text, GLUT_BITMAP_TIMES_ROMAN_24)

# ──────────────────────────────────────────────────────────────
# GEOMETRY PRIMITIVES
# ──────────────────────────────────────────────────────────────
def box(w, h, d):
    hw, hh, hd = w*0.5, h*0.5, d*0.5
    faces = [
        [(-hw,-hh, hd),( hw,-hh, hd),( hw, hh, hd),(-hw, hh, hd)],
        [( hw,-hh,-hd),(-hw,-hh,-hd),(-hw, hh,-hd),( hw, hh,-hd)],
        [(-hw,-hh,-hd),(-hw,-hh, hd),(-hw, hh, hd),(-hw, hh,-hd)],
        [( hw,-hh, hd),( hw,-hh,-hd),( hw, hh,-hd),( hw, hh, hd)],
        [(-hw, hh, hd),( hw, hh, hd),( hw, hh,-hd),(-hw, hh,-hd)],
        [(-hw,-hh,-hd),( hw,-hh,-hd),( hw,-hh, hd),(-hw,-hh, hd)],
    ]
    glBegin(GL_QUADS)
    for face in faces:
        for v in face:
            glVertex3f(*v)
    glEnd()

def vcyl(radius, height, segs=14):
    """Vertical cylinder base at y=0."""
    step = 2.0*math.pi/segs
    glBegin(GL_QUADS)
    for i in range(segs):
        a0,a1 = i*step,(i+1)*step
        x0,z0 = math.cos(a0)*radius, math.sin(a0)*radius
        x1,z1 = math.cos(a1)*radius, math.sin(a1)*radius
        glVertex3f(x0,0,z0); glVertex3f(x1,0,z1)
        glVertex3f(x1,height,z1); glVertex3f(x0,height,z0)
    glEnd()
    glBegin(GL_TRIANGLES)
    for i in range(segs):
        a0,a1 = i*step,(i+1)*step
        glVertex3f(0,height,0)
        glVertex3f(math.cos(a0)*radius,height,math.sin(a0)*radius)
        glVertex3f(math.cos(a1)*radius,height,math.sin(a1)*radius)
    glEnd()

def cone(base_r, tip_r, height, segs=12):
    step = 2.0*math.pi/segs
    glBegin(GL_QUADS)
    for i in range(segs):
        a0,a1 = i*step,(i+1)*step
        x0,z0 = math.cos(a0)*base_r, math.sin(a0)*base_r
        x1,z1 = math.cos(a1)*base_r, math.sin(a1)*base_r
        tx0,tz0 = math.cos(a0)*tip_r, math.sin(a0)*tip_r
        tx1,tz1 = math.cos(a1)*tip_r, math.sin(a1)*tip_r
        glVertex3f(x0,0,z0); glVertex3f(x1,0,z1)
        glVertex3f(tx1,height,tz1); glVertex3f(tx0,height,tz0)
    glEnd()

def draw_wheel(radius, width, spin_deg, segs=16):
    """Upright wheel: spins around X-axis."""
    step = 2.0*math.pi/segs
    hw = width*0.5
    # Sidewalls
    glBegin(GL_TRIANGLES)
    for i in range(segs):
        a0 = i*step + math.radians(spin_deg)
        a1 = (i+1)*step + math.radians(spin_deg)
        y0,z0 = math.cos(a0)*radius, math.sin(a0)*radius
        y1,z1 = math.cos(a1)*radius, math.sin(a1)*radius
        for xp in [-hw, hw]:
            glVertex3f(xp, 0, 0)
            glVertex3f(xp, y0, z0)
            glVertex3f(xp, y1, z1)
    glEnd()
    # Tread band
    glBegin(GL_QUADS)
    for i in range(segs):
        a0 = i*step + math.radians(spin_deg)
        a1 = (i+1)*step + math.radians(spin_deg)
        y0,z0 = math.cos(a0)*radius, math.sin(a0)*radius
        y1,z1 = math.cos(a1)*radius, math.sin(a1)*radius
        glVertex3f(-hw, y0, z0); glVertex3f(hw, y0, z0)
        glVertex3f( hw, y1, z1); glVertex3f(-hw, y1, z1)
    glEnd()

# ──────────────────────────────────────────────────────────────
# GROUND, ROAD, MARKINGS
# ──────────────────────────────────────────────────────────────
def draw_ground():
    # Ground is centred on player_z so it scrolls with the car — no more void
    pz   = player_z
    far  = WORLD_HALF
    z0   = pz - far
    z1   = pz + far
    # Grass (left and right of road)
    glColor3f(*grass_col())
    glBegin(GL_QUADS)
    glVertex3f(-far,0,z0); glVertex3f(-ROAD_HALF,0,z0)
    glVertex3f(-ROAD_HALF,0,z1); glVertex3f(-far,0,z1)
    glVertex3f( ROAD_HALF,0,z0); glVertex3f(far,0,z0)
    glVertex3f(far,0,z1); glVertex3f(ROAD_HALF,0,z1)
    glEnd()
    # Road surface
    glColor3f(*road_col())
    glBegin(GL_QUADS)
    glVertex3f(-ROAD_HALF,0,z0); glVertex3f(ROAD_HALF,0,z0)
    glVertex3f( ROAD_HALF,0,z1); glVertex3f(-ROAD_HALF,0,z1)
    glEnd()
    # Kerb strips
    glColor3f(0.85,0.85,0.85)
    for side in [-1,1]:
        xk = side*ROAD_HALF
        glBegin(GL_QUADS)
        glVertex3f(xk-side*5,0,z0); glVertex3f(xk+side*5,0,z0)
        glVertex3f(xk+side*5,0,z1); glVertex3f(xk-side*5,0,z1)
        glEnd()


def draw_road_markings(cam_z):
    """White lane lines that scroll toward us = forward motion feel."""
    DASH = 50; GAP = 35; PERIOD = DASH+GAP

    # Solid outer edges
    glLineWidth(4); glColor3f(0.95,0.95,0.95)
    glBegin(GL_LINES)
    for side in [-1,1]:
        xe = side*ROAD_HALF
        glVertex3f(xe,1.2,cam_z-600); glVertex3f(xe,1.2,cam_z+1800)
    glEnd()

    # Dashed lane dividers — phase locked to cam_z so they scroll
    phase = cam_z % PERIOD
    glLineWidth(3); glColor3f(0.88,0.88,0.88)
    glBegin(GL_LINES)
    for i in range(1, NUM_LANES):
        lx = -ROAD_HALF + i*LANE_W
        z = cam_z - phase - PERIOD*5
        while z < cam_z+1800:
            glVertex3f(lx,1.5,z); glVertex3f(lx,1.5,z+DASH)
            z += PERIOD
    glEnd()

    # Yellow centre double-line
    glLineWidth(3); glColor3f(*neon(1.0,0.85,0.0))
    glBegin(GL_LINES)
    for dx in [-2.5, 2.5]:
        glVertex3f(dx,1.8,cam_z-600); glVertex3f(dx,1.8,cam_z+1800)
    glEnd()


def draw_grid_overlay(cam_z):
    alpha = 0.12 + (1.0-day_factor)*0.72
    r,g,b = 0.0, 0.55*alpha, 1.0*alpha
    phase = cam_z % GRID_STEP
    glLineWidth(1)
    glBegin(GL_LINES)
    glColor3f(r,g,b)
    for i in range(NUM_LANES+1):
        lx = -ROAD_HALF + i*LANE_W
        glVertex3f(lx,0.5,cam_z-400); glVertex3f(lx,0.5,cam_z+1800)
    z = cam_z - phase - GRID_STEP*5
    while z < cam_z+1800:
        fade = max(0, 1.0 - abs(z-cam_z)/1200.0)
        glColor3f(r*fade, g*fade, b*fade)
        glVertex3f(-ROAD_HALF,0.5,z); glVertex3f(ROAD_HALF,0.5,z)
        z += GRID_STEP
    glEnd()


def draw_guardrails(cam_z):
    for side in [-1,1]:
        xg = side*(ROAD_HALF+8)
        c  = neon(0.0,0.85,1.0) if side==-1 else neon(1.0,0.28,0.0)
        glColor3f(*c); glLineWidth(3)
        glBegin(GL_LINES)
        for y in [0,22]:
            glVertex3f(xg,y,cam_z-400); glVertex3f(xg,y,cam_z+1800)
        glEnd()
        z = cam_z - (cam_z % 80)
        glLineWidth(2)
        glBegin(GL_LINES)
        while z < cam_z+1800:
            glVertex3f(xg,0,z); glVertex3f(xg,24,z)
            z += 80
        glEnd()

# ──────────────────────────────────────────────────────────────
# DECORATIONS & OBSTACLES
# ──────────────────────────────────────────────────────────────

def draw_tree(ox, oz):
    glPushMatrix(); glTranslatef(ox,0,oz)
    tc = blend((0.28,0.18,0.04),(0.45,0.28,0.08), day_factor)
    glColor3f(*tc); vcyl(5,52,8)
    for (y,br,h) in [(42,30,58),(62,23,46),(82,15,34)]:
        fc = blend((0.0,0.28,0.02),(0.10,0.60,0.12), day_factor)
        glColor3f(*neon(*fc))
        glPushMatrix(); glTranslatef(0,y,0); cone(br,2,h,10); glPopMatrix()
    glPopMatrix()


def draw_bush(ox, oz):
    glPushMatrix(); glTranslatef(ox,0,oz)
    bc = blend((0.04,0.38,0.04),(0.10,0.65,0.10), day_factor)
    glColor3f(*neon(*bc))
    for (dx,dz,r) in [(-12,0,13),(0,4,16),(12,0,13),(0,-8,11)]:
        glPushMatrix(); glTranslatef(dx,r*0.6,dz)
        gluSphere(gluNewQuadric(),r,8,8); glPopMatrix()
    glPopMatrix()


def draw_grass_tuft(ox, oz):
    glPushMatrix(); glTranslatef(ox,0,oz)
    gc = blend((0.05,0.38,0.05),(0.14,0.58,0.14), day_factor)
    glColor3f(*neon(*gc))
    for i in range(7):
        a = i*math.pi*2/7
        glPushMatrix(); glTranslatef(math.cos(a)*7,0,math.sin(a)*7)
        glRotatef(i*20,0,1,0)
        box(3,16+i*2,2)
        glPopMatrix()
    glPopMatrix()

def draw_lamp_post(ox, oz, side):
    """Tall stick lamp post with horizontal arm."""
    glPushMatrix(); glTranslatef(ox,0,oz)
    pc = blend((0.28,0.28,0.36),(0.52,0.52,0.60), day_factor)
    # Pole
    glColor3f(*pc); vcyl(3,115,7)
    # Arm
    arm_x = side*30
    glColor3f(*pc)
    glBegin(GL_QUADS)
    glVertex3f(0,115,-2); glVertex3f(arm_x,115,-2)
    glVertex3f(arm_x,120,-2); glVertex3f(0,120,-2)
    glVertex3f(0,115, 2); glVertex3f(arm_x,115, 2)
    glVertex3f(arm_x,120, 2); glVertex3f(0,120, 2)
    glEnd()
    # Lamp head
    lc = neon(1.0,0.95,0.50) if day_factor < 0.65 else (0.72,0.72,0.52)
    glColor3f(*lc)
    glPushMatrix(); glTranslatef(arm_x,112,0); box(20,9,14); glPopMatrix()
    # Light cone — points DOWN to ground at night (translated down, no rotation needed)
    if day_factor < 0.5:
        alpha = (1-day_factor)*0.6
        glColor3f(alpha*0.9, alpha*0.85, alpha*0.3)
        glPushMatrix()
        # Place base of cone at lamp head (y=112), tip reaches toward y=0 (ground)
        # cone() draws from y=0 (base) upward, so translate so y=0 is at ground level
        glTranslatef(arm_x, 0, 0)
        cone(28, 2, 112, 12)   # base at ground (y=0), tip at lamp height (y=112)
        glPopMatrix()
    glPopMatrix()

def draw_building(ox, oz, w, h, d, seed):
    glPushMatrix(); glTranslatef(ox,0,oz)
    bc = build_col()
    glColor3f(*bc)
    glPushMatrix(); glTranslatef(0,h*0.5,0); box(w,h,d); glPopMatrix()
    # Windows
    random.seed(seed)
    floors = max(2, h//22)
    cols   = max(2, w//18)
    for fl in range(floors):
        for col in range(cols):
            if random.random() < 0.72:
                wc = neon(0.90,0.85,0.45) if day_factor < 0.55 else (0.72,0.84,0.96)
                glColor3f(*wc)
                wx2 = -w*0.38 + col*(w*0.76/(max(cols-1,1)))
                wy  = 12 + fl*22
                for wz2 in [d*0.502, -d*0.502]:
                    glPushMatrix(); glTranslatef(wx2,wy,wz2); box(9,11,1); glPopMatrix()
    random.seed()
    glPopMatrix()

def draw_pothole(ox, oz):
    glPushMatrix(); glTranslatef(ox,0.5,oz)
    segs=14; step=2*math.pi/segs
    glBegin(GL_QUADS)
    for i in range(segs):
        a0,a1 = i*step,(i+1)*step
        glColor3f(*neon(1.0,0.80,0.0))
        glVertex3f(math.cos(a0)*20,0,math.sin(a0)*20)
        glVertex3f(math.cos(a1)*20,0,math.sin(a1)*20)
        glColor3f(0.08,0.08,0.08)
        glVertex3f(math.cos(a1)*12,0,math.sin(a1)*12)
        glVertex3f(math.cos(a0)*12,0,math.sin(a0)*12)
    glEnd()
    glPopMatrix()

def draw_traffic_cone(ox, oz):
    glPushMatrix(); glTranslatef(ox,0,oz)
    glColor3f(*neon(1.0,0.30,0.0)); cone(12,1,42,10)
    glColor3f(0.95,0.95,0.95)
    glPushMatrix(); glTranslatef(0,16,0); cone(8,6,7,10); glPopMatrix()
    glPopMatrix()

def draw_coin(ox, oz, bob_offset=0.0):
    """A glowing upright spinning coin floating above the road."""
    glPushMatrix()
    # Float up and down
    glTranslatef(ox, 22 + math.sin(bob_offset) * 6, oz)
    # Spin around Y axis — uses bob_offset as a phase so each coin has different rotation
    glRotatef(bob_time * 180.0 + bob_offset * 57.3, 0, 1, 0)
    glColor3f(*neon(1.0, 0.90, 0.1))
    segs = 14
    step = 2.0 * math.pi / segs
    # Front face (XY plane disc — coin stands up along Y)
    glBegin(GL_TRIANGLES)
    for i in range(segs):
        a0, a1 = i * step, (i + 1) * step
        glVertex3f(0, 0, 0)
        glVertex3f(math.cos(a0) * 10, math.sin(a0) * 10, 0)
        glVertex3f(math.cos(a1) * 10, math.sin(a1) * 10, 0)
    glEnd()
    # Back face
    glBegin(GL_TRIANGLES)
    for i in range(segs):
        a0, a1 = i * step, (i + 1) * step
        glVertex3f(0, 0, -3)
        glVertex3f(math.cos(a1) * 10, math.sin(a1) * 10, -3)
        glVertex3f(math.cos(a0) * 10, math.sin(a0) * 10, -3)
    glEnd()
    # Edge band
    glBegin(GL_QUADS)
    for i in range(segs):
        a0, a1 = i * step, (i + 1) * step
        glVertex3f(math.cos(a0) * 10, math.sin(a0) * 10, 0)
        glVertex3f(math.cos(a1) * 10, math.sin(a1) * 10, 0)
        glVertex3f(math.cos(a1) * 10, math.sin(a1) * 10, -3)
        glVertex3f(math.cos(a0) * 10, math.sin(a0) * 10, -3)
    glEnd()
    glPopMatrix()

def draw_powerup(ox, oz, ptype, bob_offset=0.0):
    """Draw a floating, bobbing power-up item on the road."""
    glPushMatrix()
    glTranslatef(ox, 28 + math.sin(bob_offset + 1.0) * 7, oz)
    if ptype == 'multiplier':
        # Orange glowing sphere with an X2 feel — two stacked boxes
        glColor3f(*neon(1.0, 0.55, 0.0))
        gluSphere(gluNewQuadric(), 13, 10, 10)
        glColor3f(*neon(1.0, 0.9, 0.1))
        glPushMatrix(); glTranslatef(0, 0, 0); box(6, 18, 6); glPopMatrix()
        glPushMatrix(); glTranslatef(0, 0, 0); box(18, 6, 6); glPopMatrix()
    elif ptype == 'coinbag':
        # Blue glowing cube (coin bag)
        glColor3f(*neon(0.1, 0.5, 1.0))
        box(18, 18, 18)
        glColor3f(*neon(0.6, 0.9, 1.0))
        glPushMatrix(); glTranslatef(0, 12, 0); vcyl(5, 8, 8); glPopMatrix()
    elif ptype == 'invincibility':
        # Green pulsing star shape
        glColor3f(*neon(0.0, 1.0, 0.4))
        gluSphere(gluNewQuadric(), 10, 10, 10)
        for angle in range(0, 360, 60):
            glPushMatrix()
            glRotatef(angle, 0, 1, 0)
            glTranslatef(14, 0, 0)
            box(6, 6, 6)
            glPopMatrix()
    glPopMatrix()


def draw_fallen_tree(ox, oz, side, angle=90.0):
    """Draw a fallen tree log. angle=0 means upright, 90 means fully fallen."""
    glPushMatrix()
    glTranslatef(ox, 0, oz)
    # Rotate around Z to simulate falling from the side
    glRotatef(-side * angle, 0, 0, 1)
    # Trunk: long cylinder lying along Y when fallen
    tc = blend((0.28, 0.18, 0.04), (0.45, 0.28, 0.08), day_factor)
    glColor3f(*tc)
    vcyl(7, 80, 10)
    # Canopy clusters at top of trunk
    fc = blend((0.0, 0.28, 0.02), (0.10, 0.60, 0.12), day_factor)
    glColor3f(*neon(*fc))
    for (dy, r) in [(70, 22), (88, 16), (100, 10)]:
        glPushMatrix()
        glTranslatef(0, dy, 0)
        gluSphere(gluNewQuadric(), r, 8, 8)
        glPopMatrix()
    glPopMatrix()


# ──────────────────────────────────────────────────────────────
# PLAYER CAR
# ──────────────────────────────────────────────────────────────
BODY_Y = WHEEL_R   # body base sits at wheel-axle height

WHEEL_POSITIONS = [(-22, -32), (-22, 32), (22, -32), (22, 32)]

def draw_player_car(px, lean):
    glPushMatrix()
    glTranslatef(px, 0, player_z)
    glRotatef(lean*12, 0,0,1)

    # Body
    glColor3f(*neon(0.05,0.82,1.00))
    glPushMatrix(); glTranslatef(0,BODY_Y+18,0); box(44,22,84); glPopMatrix()
    # Cabin
    glColor3f(*neon(0.08,0.36,0.92))
    glPushMatrix(); glTranslatef(0,BODY_Y+37,-4); box(34,18,48); glPopMatrix()
    # Windshield
    glColor3f(*neon(0.55,0.90,1.00))
    glPushMatrix(); glTranslatef(0,BODY_Y+36,20); box(30,14,3); glPopMatrix()
    glPushMatrix(); glTranslatef(0,BODY_Y+36,-28); box(30,14,3); glPopMatrix()
    # Neon undercarriage
    glColor3f(*neon(0.00,1.00,0.60))
    glPushMatrix(); glTranslatef(0,BODY_Y+2,0); box(46,2,88); glPopMatrix()
    # Headlights
    glColor3f(*neon(1.00,1.00,0.50))
    for lx in [-14,14]:
        glPushMatrix(); glTranslatef(lx,BODY_Y+16,43); box(9,6,4); glPopMatrix()
    # Tail lights
    glColor3f(*neon(1.00,0.10,0.10))
    for lx in [-14,14]:
        glPushMatrix(); glTranslatef(lx,BODY_Y+16,-43); box(9,6,4); glPopMatrix()

    # Wheels — upright, sitting on ground, spinning
    for (wx,wz) in WHEEL_POSITIONS:
        glPushMatrix()
        glTranslatef(wx, WHEEL_R, wz)
        glColor3f(0.10,0.10,0.10)
        draw_wheel(WHEEL_R, WHEEL_W, wheel_angle) # Main tire spin
        glColor3f(*neon(0.00,1.00,0.55))
        draw_wheel(int(WHEEL_R*0.46), WHEEL_W+2, wheel_angle, 10) # Inner glow
        glPopMatrix()

    glPopMatrix()

# ──────────────────────────────────────────────────────────────
# OBSTACLE VEHICLES
# ──────────────────────────────────────────────────────────────
def draw_obstacle_car(otype, ox, oz):
    glPushMatrix(); glTranslatef(ox,0,oz)

    if otype == "car":
        glColor3f(*neon(1.0,0.18,0.18))
        glPushMatrix(); glTranslatef(0,BODY_Y+18,0); box(40,22,80); glPopMatrix()
        glColor3f(*neon(0.8,0.10,0.10))
        glPushMatrix(); glTranslatef(0,BODY_Y+36,0); box(32,16,44); glPopMatrix()
        glColor3f(*neon(0.50,0.85,1.00))
        glPushMatrix(); glTranslatef(0,BODY_Y+36,20); box(28,12,3); glPopMatrix()
        glColor3f(*neon(1.0,0.0,0.45))
        glPushMatrix(); glTranslatef(0,BODY_Y+4,0); box(44,2,84); glPopMatrix()
        wps = [(-20,-27),(20,-27),(-20,27),(20,27)]

    elif otype == "truck":
        glColor3f(*neon(0.90,0.55,0.05))
        glPushMatrix(); glTranslatef(0,BODY_Y+32,-22); box(50,54,104); glPopMatrix()
        glColor3f(*neon(0.70,0.40,0.05))
        glPushMatrix(); glTranslatef(0,BODY_Y+22,56); box(46,38,30); glPopMatrix()
        glColor3f(*neon(0.00,1.00,0.50))
        glPushMatrix(); glTranslatef(0,BODY_Y+4,0); box(54,3,136); glPopMatrix()
        wps = [(-27,-55),(27,-55),(-27,-18),(27,-18),(-27,52),(27,52)]

    elif otype == "sports":
        glColor3f(*neon(0.60,0.00,1.00))
        glPushMatrix(); glTranslatef(0,BODY_Y+11,0); box(38,16,76); glPopMatrix()
        glColor3f(*neon(0.40,0.00,0.80))
        glPushMatrix(); glTranslatef(0,BODY_Y+23,-6); box(30,12,40); glPopMatrix()
        glColor3f(*neon(0.75,0.92,1.00))
        glPushMatrix(); glTranslatef(0,BODY_Y+23,16); box(26,10,3); glPopMatrix()
        glColor3f(*neon(0.80,0.20,1.00))
        glPushMatrix(); glTranslatef(0,BODY_Y+3,0); box(42,2,80); glPopMatrix()
        wps = [(-20,-22),(20,-22),(-20,22),(20,22)]
    else:
        wps = []

    for (wx,wz) in wps:
        glPushMatrix(); glTranslatef(wx,WHEEL_R,wz)
        glColor3f(0.10,0.10,0.10); draw_wheel(WHEEL_R,WHEEL_W,0)
        glColor3f(*neon(0.80,0.20,0.20)); draw_wheel(int(WHEEL_R*0.42),WHEEL_W+2,0,10)
        glPopMatrix()

    glPopMatrix()

# ──────────────────────────────────────────────────────────────
# PARTICLES (Unchanged)
# ──────────────────────────────────────────────────────────────
def spawn_particles(px, pz):
    for _ in range(35):
        particles.append({'x':px,'y':25,'z':pz,
            'vx':random.uniform(-6,6),'vy':random.uniform(3,12),'vz':random.uniform(-6,6),
            'life':1.0,'color':random.choice([(1,.3,0),(1,.8,0),(1,0,.5),(0,1,1)])})

def update_particles(dt):
    for p in particles[:]:
        p['x']+=p['vx']; p['y']+=p['vy']; p['z']+=p['vz']
        p['vy']-=0.5; p['life']-=dt*2.0
        if p['life']<=0: particles.remove(p)

def draw_particles():
    glPointSize(10)
    glBegin(GL_POINTS)
    for p in particles:
        r,g,b=p['color']
        glColor3f(r*p['life'],g*p['life'],b*p['life'])
        glVertex3f(p['x'],p['y'],p['z'])
    glEnd()

# ──────────────────────────────────────────────────────────────
# SKY (Unchanged)
# ──────────────────────────────────────────────────────────────
def draw_sky():
    sc  = sky_col()
    top = blend(sc,(0,0,0),0.45)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    # Sky gradient (bottom bright → top dark)
    glBegin(GL_QUADS)
    glColor3f(*sc);  glVertex3f(0,0,0);        glVertex3f(WIN_W,0,0)
    glColor3f(*top); glVertex3f(WIN_W,WIN_H,0); glVertex3f(0,WIN_H,0)
    glEnd()

    # Stars at night
    if day_factor < 0.85:
        sa = 1.0-day_factor; glColor3f(sa,sa,sa); glPointSize(2)
        random.seed(99)
        glBegin(GL_POINTS)
        for _ in range(220):
            glVertex3f(random.randint(0,WIN_W),random.randint(WIN_H//2,WIN_H),0)
        glEnd()
        random.seed()

    segs=16
    # Sun
    if day_factor > 0.05:
        cx,cy=WIN_W-140,WIN_H-95; r=38*day_factor
        glColor3f(*neon(1.0,0.92,0.30))
        glBegin(GL_TRIANGLES)
        for i in range(segs):
            a0=i*2*math.pi/segs; a1=(i+1)*2*math.pi/segs
            glVertex3f(cx,cy,0)
            glVertex3f(cx+math.cos(a0)*r,cy+math.sin(a0)*r,0)
            glVertex3f(cx+math.cos(a1)*r,cy+math.sin(a1)*r,0)
        glEnd()
    # Moon
    if day_factor < 0.5:
        cx,cy=145,WIN_H-85; r=26*(1-day_factor)
        glColor3f(0.92,0.92,0.80)
        glBegin(GL_TRIANGLES)
        for i in range(segs):
            a0=i*2*math.pi/segs; a1=(i+1)*2*math.pi/segs
            glVertex3f(cx,cy,0)
            glVertex3f(cx+math.cos(a0)*r,cy+math.sin(a0)*r,0)
            glVertex3f(cx+math.cos(a1)*r,cy+math.sin(a1)*r,0)
        glEnd()

    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

# ──────────────────────────────────────────────────────────────
# CAMERA (Unchanged)
# ──────────────────────────────────────────────────────────────
def setup_camera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity()

    if fpv_mode:
        # Wider FOV for immersive first-person feel
        gluPerspective(90, WIN_W/WIN_H, 1.0, 4000.0)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        # Camera sits at driver eye level, hard-attached to front of car
        # Car body front is at z + 43 (headlight z), cabin top ~BODY_Y+46
        eye_y  = BODY_Y + 46          # eye height — top of cabin
        eye_z  = player_z + 43        # front of car (headlight plane)
        look_z = player_z + 800       # look far ahead along the road
        gluLookAt(player_x, eye_y, eye_z,
                  player_x, eye_y - 5, look_z,
                  0, 1, 0)
    else:
        gluPerspective(62, WIN_W/WIN_H, 1.0, 4000.0)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        cam_x = player_x * 0.25
        gluLookAt(cam_x, CAM_DY, player_z + CAM_DZ,
                  player_x * 0.05, 30, player_z + LOOK_DZ,
                  0, 1, 0)

# ──────────────────────────────────────────────────────────────
# SPAWN / CULL
# ──────────────────────────────────────────────────────────────
OBS_TYPES = ["car","car","car","truck","sports","pothole","cone"]

def spawn_row(z):
    # Only 1 obstacle per row (was 1-3) to further reduce density
    n = 1
    lanes = random.sample(range(NUM_LANES), n)
    for lane in lanes:
        # Fallen tree only allowed in leftmost (0) or rightmost (4) lanes
        if random.random() < 0.12 and lane in (0, NUM_LANES - 1):
            obs_type = 'fallen_tree'
            # Spawn a new animated fallen tree entry
            side = -1 if lane == 0 else 1
            fallen_trees.append({'ox': LANE_CENTERS[lane], 'oz': z,
                                  'side': side, 'angle': 0.0, 'fallen': False})
        else:
            if lane in (0, NUM_LANES - 1):
                obs_type = random.choice(OBS_TYPES)
            else:
                obs_type = random.choice(OBS_TYPES)
        obstacles.append({'type': obs_type, 'lane': lane, 'z': z, 'hit': False})

def spawn_coin_row(z):
    """Spawn a row of 1-3 coins across road lanes."""
    num_coins = random.randint(1, 3)
    lanes = random.sample(range(NUM_LANES), num_coins)
    for lane in lanes:
        cx = LANE_CENTERS[lane] + random.uniform(-15, 15)
        decorations.append({'type': 'coin', 'x': cx, 'z': z, 'side': 0,
                            'bob': random.uniform(0, math.pi * 2)})

def spawn_deco(z):
    for side in [-1, 1]:
        bx = side * (ROAD_HALF + random.randint(20, 400))
        choice = random.random()
        if choice < 0.95:   # powerups now spawn only ~5 % of the time (was 20 %)
            dt = random.choices(
                ["tree", "tree", "bush", "grass", "lamp", "building"],
                weights=[3, 3, 3, 2, 2, 2])[0]
            decorations.append({'type': dt, 'x': bx, 'z': z, 'side': side,
                                'w': random.randint(38, 85),
                                'h': random.randint(75, 220),
                                'd': random.randint(38, 85),
                                'seed': random.randint(0, 9999)})
        else:
            # Power-ups spawn on the road, not on the sides
            road_x = LANE_CENTERS[random.randint(0, NUM_LANES - 1)]
            p_types = ['multiplier', 'coinbag', 'invincibility']
            ptype = random.choice(p_types)
            decorations.append({'type': ptype, 'x': road_x, 'z': z, 'side': side,
                                'bob': random.uniform(0, math.pi * 2)})

def cull_all():
    global obstacles, decorations, fallen_trees
    obstacles    = [o for o in obstacles    if o['z'] > player_z - CULL_BEHIND]
    decorations  = [d for d in decorations  if d['z'] > player_z - CULL_BEHIND]
    fallen_trees = [f for f in fallen_trees if f['oz'] > player_z - CULL_BEHIND]

# ──────────────────────────────────────────────────────────────
# COLLISION (HEART & COIN LOGIC)
# ──────────────────────────────────────────────────────────────
def check_collisions():
    global score, speed, health, coins, invincible, multiplier_timer, invincible_timer
    global powerup_multiplier

    # --- 1. Obstacle Collision and Damage ---
    for o in obstacles:
        if o['hit']: continue
        dz = abs(player_z - o['z'])
        dx = abs(player_x - LANE_CENTERS[o['lane']])

        hit_dz = 95 if o['type'] == 'truck' else (68 if o['type'] != 'fallen_tree' else 70)

        if dz < hit_dz and dx < 36:
            o['hit'] = True
            spawn_particles(player_x, player_z)

            if not invincible:
                health -= 1
                score = max(0, score - 50)
                speed = max(10, speed - 8)
                if health <= 0:
                    global game_state
                    game_state = 'gameover'

    # --- 2. Collectible Collision (Coins & Power-Ups) ---
    to_remove = []
    for d in decorations:
        if d['type'] not in ('coin', 'multiplier', 'coinbag', 'invincibility'):
            continue
        if d.get('collected'):
            continue

        dist_z = abs(player_z - d['z'])
        dist_x = abs(player_x - d['x'])
        if dist_z < COIN_COLLISION_RANGE and dist_x < 35:

            if d['type'] == 'coin':
                coins += 1
                d['collected'] = True

            elif d['type'] == 'multiplier':
                multiplier_timer = POWERUP_MULTIPLIER_DURATION
                powerup_multiplier = 2.0
                d['collected'] = True

            elif d['type'] == 'invincibility':
                invincible_timer = INVINCIBILITY_DURATION
                invincible = True
                d['collected'] = True

            elif d['type'] == 'coinbag':
                coins += 10
                d['collected'] = True

    # Remove collected decorations
    decorations[:] = [d for d in decorations if not d.get('collected')]

# ──────────────────────────────────────────────────────────────
# HUD & DISPLAY HELPERS
# ──────────────────────────────────────────────────────────────
def draw_hud():
    glDisable(GL_DEPTH_TEST)

    # ── Top HUD bar ──────────────────────────────────────────────
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(0.03, 0.03, 0.10)
    glBegin(GL_QUADS)
    glVertex3f(0, WIN_H-52, 0); glVertex3f(WIN_W, WIN_H-52, 0)
    glVertex3f(WIN_W, WIN_H, 0); glVertex3f(0, WIN_H, 0)
    glEnd()
    glColor3f(*neon(0.0, 0.8, 1.0)); glLineWidth(2)
    glBegin(GL_LINES)
    glVertex3f(0, WIN_H-52, 0); glVertex3f(WIN_W, WIN_H-52, 0)
    glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # Row inside top bar — SCORE (centre), COINS (right), controls (left)
    glColor3f(*neon(0.0, 1.0, 0.6))
    draw_text_lg(WIN_W//2-75, WIN_H-34, f"SCORE: {int(score)}")
    glColor3f(*neon(1.0, 0.85, 0.0))
    draw_text(WIN_W-230, WIN_H-20, f"COINS: {coins}")
    draw_text(WIN_W-230, WIN_H-40, f"SPEED: {int(speed)} km/h")
    glColor3f(0.55, 0.55, 0.75)
    draw_text(12, WIN_H-30, "[A/D/ARROWS] Steer  [W/S] Speed  [P] Pause  [R] Restart  [C] Camera",
              GLUT_BITMAP_HELVETICA_12)
    # FPV badge
    if fpv_mode:
        glColor3f(*neon(1.0, 0.55, 0.0))
        draw_text(WIN_W//2 - 28, WIN_H - 72, "FPV", GLUT_BITMAP_HELVETICA_12)

    # ── Health bar strip — just below the HUD bar ─────────────────
    HP_BAR_TOP = WIN_H - 52   # bottom edge of HUD bar
    HP_BAR_H   = 22           # strip height
    HP_BAR_BOT = HP_BAR_TOP - HP_BAR_H

    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    # Dark strip background
    glColor3f(0.06, 0.06, 0.14)
    glBegin(GL_QUADS)
    glVertex3f(0, HP_BAR_BOT, 0); glVertex3f(WIN_W, HP_BAR_BOT, 0)
    glVertex3f(WIN_W, HP_BAR_TOP, 0); glVertex3f(0, HP_BAR_TOP, 0)
    glEnd()

    # 5 health segments, centred
    seg_w   = 46
    seg_gap = 6
    total_w = 5 * seg_w + 4 * seg_gap
    bar_x0  = WIN_W // 2 - total_w // 2
    seg_y0  = HP_BAR_BOT + 3
    seg_y1  = HP_BAR_TOP - 3

    for i in range(5):
        sx = bar_x0 + i * (seg_w + seg_gap)
        # Empty slot
        glColor3f(0.25, 0.04, 0.04)
        glBegin(GL_QUADS)
        glVertex3f(sx, seg_y0, 0);     glVertex3f(sx+seg_w, seg_y0, 0)
        glVertex3f(sx+seg_w, seg_y1, 0); glVertex3f(sx, seg_y1, 0)
        glEnd()
        # Filled slot
        if i < health:
            if health <= 2:
                glColor3f(*neon(1.0, 0.1, 0.1))
            elif health <= 3:
                glColor3f(*neon(1.0, 0.55, 0.0))
            else:
                glColor3f(*neon(0.1, 0.9, 0.3))
            glBegin(GL_QUADS)
            glVertex3f(sx+2, seg_y0+2, 0);       glVertex3f(sx+seg_w-2, seg_y0+2, 0)
            glVertex3f(sx+seg_w-2, seg_y1-2, 0); glVertex3f(sx+2, seg_y1-2, 0)
            glEnd()

    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # HP label left of segments
    glColor3f(0.85, 0.85, 0.85)
    draw_text(bar_x0 - 58, HP_BAR_BOT + 5, f"HP {health}/5", GLUT_BITMAP_HELVETICA_12)

    # ── Active powerup timers — below health strip ────────────────
    timer_y = HP_BAR_BOT - 18
    if invincible and invincible_timer > 0:
        glColor3f(*neon(0.0, 1.0, 0.4))
        draw_text(12, timer_y, f"SHIELD {invincible_timer:.1f}s")
    if powerup_multiplier > 1.0 and multiplier_timer > 0:
        glColor3f(*neon(1.0, 0.55, 0.0))
        tx = 180 if (invincible and invincible_timer > 0) else 12
        draw_text(tx, timer_y, f"x2 SCORE {multiplier_timer:.1f}s")

    if game_state == "pause":
        _overlay("PAUSED", "Press P to resume | R to restart")
    elif game_state == "gameover":
        _overlay("GAME OVER", "")
    elif game_state == "confirm_restart":
        _overlay("RESTART?", "Are you sure you want to restart?")
    glEnable(GL_DEPTH_TEST)


def _draw_button(x1, y1, x2, y2, label, col_border, col_fill):
    """Helper: draw a filled rectangle button with centred text label."""
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(*col_fill)
    glBegin(GL_QUADS)
    glVertex3f(x1,y1,0); glVertex3f(x2,y1,0)
    glVertex3f(x2,y2,0); glVertex3f(x1,y2,0)
    glEnd()
    glColor3f(*col_border); glLineWidth(2)
    glBegin(GL_LINES)
    glVertex3f(x1,y1,0); glVertex3f(x2,y1,0)
    glVertex3f(x2,y1,0); glVertex3f(x2,y2,0)
    glVertex3f(x2,y2,0); glVertex3f(x1,y2,0)
    glVertex3f(x1,y2,0); glVertex3f(x1,y1,0)
    glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    # Centre label: GLUT_BITMAP_HELVETICA_18 averages ~10px/char
    char_w = 10
    lw = len(label) * char_w
    cx = (x1+x2)//2 - lw//2
    cy = (y1+y2)//2 - 7
    glColor3f(1.0,1.0,1.0)
    draw_text(cx, cy, label)

def _overlay(title, sub):
    CX = WIN_W // 2   # 550
    CY = WIN_H // 2   # 400

    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    if title == "GAME OVER":
        px0, px1, py0, py1 = 200, 900, 230, 570
    elif title == "RESTART?":
        px0, px1, py0, py1 = 270, 830, 250, 540   # taller: was 300-500
    else:   # PAUSED
        px0, px1, py0, py1 = 290, 810, 270, 530   # taller: was 320-490

    glColor3f(0,0,0.04)
    glBegin(GL_QUADS)
    glVertex3f(px0,py0,0); glVertex3f(px1,py0,0)
    glVertex3f(px1,py1,0); glVertex3f(px0,py1,0)
    glEnd()
    glColor3f(*neon(0.0,0.85,1.0)); glLineWidth(2)
    glBegin(GL_LINES)
    glVertex3f(px0,py0,0); glVertex3f(px1,py0,0)
    glVertex3f(px1,py0,0); glVertex3f(px1,py1,0)
    glVertex3f(px1,py1,0); glVertex3f(px0,py1,0)
    glVertex3f(px0,py1,0); glVertex3f(px0,py0,0)
    glEnd()

    # Thin separator — sits further below title for Restart/Pause to create space
    sep_gap = 80 if title == "GAME OVER" else 100
    sep_y = py1 - sep_gap
    glColor3f(*neon(0.0,0.5,0.8)); glLineWidth(1)
    glBegin(GL_LINES)
    glVertex3f(px0+20, sep_y, 0); glVertex3f(px1-20, sep_y, 0)
    glEnd()

    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # Title — centred using char-width estimate (TIMES_ROMAN_24 ~14px/char)
    title_x = CX - len(title) * 7
    glColor3f(*neon(1.0,1.0,0.3))
    draw_text_lg(title_x, py1 - 48, title)

    # ── GAME OVER ────────────────────────────────────────────────
    if title == "GAME OVER":
        coin_bonus  = coins * 5
        final_score = int(score) + coin_bonus

        # Flavour text centred (~9px/char for HELVETICA_18)
        flavour = "Try again later or never or now... nevermind"
        glColor3f(0.85,0.85,0.85)
        draw_text(CX - len(flavour)*4, py1 - 100, flavour, GLUT_BITMAP_HELVETICA_12)

        # Two-column score table: labels right-aligned at CX-10, values left at CX+15
        LX = CX - 160   # label left edge
        VX = CX + 20    # value left edge

        glColor3f(*neon(0.0,1.0,0.6))
        draw_text(LX, 450, "Base Score:", GLUT_BITMAP_HELVETICA_18)
        draw_text(VX, 450, f"{int(score)}", GLUT_BITMAP_HELVETICA_18)

        glColor3f(*neon(1.0,0.85,0.0))
        draw_text(LX, 420, f"Coin Bonus (+{coins} x 5):", GLUT_BITMAP_HELVETICA_18)
        draw_text(VX, 420, f"+{coin_bonus}", GLUT_BITMAP_HELVETICA_18)

        # Divider line
        glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
        gluOrtho2D(0,WIN_W,0,WIN_H)
        glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
        glColor3f(*neon(0.6,0.6,0.9)); glLineWidth(1)
        glBegin(GL_LINES)
        glVertex3f(LX, 408, 0); glVertex3f(CX+200, 408, 0)
        glEnd()
        glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        glColor3f(*neon(1.0,1.0,0.3))
        draw_text_lg(LX, 380, "FINAL SCORE:")
        draw_text_lg(VX, 380, f"{final_score}")

        # Buttons: PLAY AGAIN left of centre, MAIN MENU right of centre
        # Each button 190px wide, 40px tall, 20px gap either side of CX
        _draw_button(CX-220, 300, CX-10, 342,
                     "PLAY AGAIN",
                     neon(0.0,1.0,0.5), (0.04,0.18,0.10))
        _draw_button(CX+10, 300, CX+220, 342,
                     "MAIN MENU",
                     neon(0.6,0.6,1.0), (0.08,0.08,0.22))

    # ── RESTART? ─────────────────────────────────────────────────
    elif title == "RESTART?":
        msg = "Are you sure you want to restart?"
        glColor3f(0.90,0.90,0.90)
        # Body text sits 30px below the separator
        draw_text(CX - len(msg)*5, sep_y - 40, msg)

        # Buttons centred in the lower half of the panel, 30px above panel bottom
        btn_y0 = py0 + 30
        btn_y1 = btn_y0 + 48
        _draw_button(CX-210, btn_y0, CX-10, btn_y1,
                     "YES - RESTART",
                     neon(0.0,1.0,0.4), (0.04,0.20,0.10))
        _draw_button(CX+10, btn_y0, CX+210, btn_y1,
                     "NO - GO BACK",
                     neon(1.0,0.3,0.1), (0.22,0.05,0.04))

    # ── PAUSED ───────────────────────────────────────────────────
    else:
        msg = "Press P to resume   |   R to restart"
        glColor3f(0.88,0.88,0.88)
        # Body text sits 40px below the separator, nicely spaced
        draw_text(CX - len(msg)*5, sep_y - 50, msg)

def draw_main_menu():
    """Full-screen main menu with Play and Items buttons."""
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    # Dark background
    glColor3f(0.01, 0.01, 0.08)
    glBegin(GL_QUADS)
    glVertex3f(0,0,0); glVertex3f(WIN_W,0,0)
    glVertex3f(WIN_W,WIN_H,0); glVertex3f(0,WIN_H,0)
    glEnd()

    # Neon grid lines (decoration)
    glColor3f(0.0, 0.12, 0.30); glLineWidth(1)
    glBegin(GL_LINES)
    for gx in range(0, WIN_W, 55):
        glVertex3f(gx, 0, 0); glVertex3f(gx, WIN_H, 0)
    for gy in range(0, WIN_H, 55):
        glVertex3f(0, gy, 0); glVertex3f(WIN_W, gy, 0)
    glEnd()

    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # Title — TIMES_ROMAN_24 ~14px/char
    glColor3f(*neon(0.05, 0.92, 1.00))
    draw_text_lg(WIN_W//2 - len("NEON  DRIFT")*7, WIN_H//2 + 160, "NEON  DRIFT")
    glColor3f(*neon(0.8, 0.8, 1.0))
    subtitle = "5-Lane 3D Obstacle Racing"
    draw_text(WIN_W//2 - len(subtitle)*5, WIN_H//2 + 120, subtitle)

    # Buttons — all 220px wide, centred on WIN_W//2
    # PLAY   y: 440-490
    # ITEMS  y: 375-425
    # EXIT   y: 310-360
    BX0, BX1 = WIN_W//2 - 110, WIN_W//2 + 110
    _draw_button(BX0, 440, BX1, 490,
                 "PLAY",
                 neon(0.0, 1.0, 0.5), (0.02, 0.18, 0.08))
    _draw_button(BX0, 375, BX1, 425,
                 "ITEMS",
                 neon(0.9, 0.6, 0.0), (0.18, 0.10, 0.02))
    _draw_button(BX0, 310, BX1, 360,
                 "EXIT",
                 neon(1.0, 0.2, 0.2), (0.22, 0.03, 0.03))

    # Footer centred
    footer = "[A/D or ARROWS] Steer  [W/S] Speed  [P] Pause  [ESC] Quit"
    glColor3f(0.4, 0.4, 0.6)
    draw_text(WIN_W//2 - len(footer)*3, 30, footer, GLUT_BITMAP_HELVETICA_12)
    glEnable(GL_DEPTH_TEST)


def draw_items_screen():
    """Items screen: shows each powerup model in a 3-D viewport alongside its description."""
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    # Dark background
    glColor3f(0.01, 0.01, 0.08)
    glBegin(GL_QUADS)
    glVertex3f(0,0,0); glVertex3f(WIN_W,0,0)
    glVertex3f(WIN_W,WIN_H,0); glVertex3f(0,WIN_H,0)
    glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

    # Panel header
    glColor3f(*neon(0.8, 0.8, 1.0))
    draw_text_lg(WIN_W//2 - 75, WIN_H - 55, "POWER-UP ITEMS")

    # Each item: (label, sublabel, description, ptype, viewport_x_centre, viewport_y_centre)
    items = [
        ("Score Multiplier", "x2 SCORE  for 10 sec",
         "All points earned are doubled while active.",
         'multiplier', WIN_W//4, WIN_H//2 + 50),
        ("Coin Bag", "+10 COINS  instantly",
         "Immediately adds 10 coins to your counter.",
         'coinbag',   WIN_W//2, WIN_H//2 + 50),
        ("Invincibility", "SHIELD  for 15 sec",
         "No damage taken and no speed penalty on hit.",
         'invincibility', 3*WIN_W//4, WIN_H//2 + 50),
    ]

    spin = bob_time * 90.0   # degrees — 90 deg/sec spin

    for (label, sublabel, desc, ptype, vx, vy) in items:
        # -- 3-D viewport for this item's model --
        vp_size = 160
        glViewport(vx - vp_size//2, vy - vp_size//2, vp_size, vp_size)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(45, 1.0, 1.0, 400.0)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        gluLookAt(0, 20, 80,  0, 0, 0,  0, 1, 0)

        # Spin model around Y
        glRotatef(spin, 0, 1, 0)
        # Draw at origin (ignore ox/oz/bob_offset translations inside draw_powerup)
        if ptype == 'multiplier':
            glColor3f(*neon(1.0, 0.55, 0.0))
            gluSphere(gluNewQuadric(), 13, 12, 12)
            glColor3f(*neon(1.0, 0.9, 0.1))
            box(6, 22, 6); box(22, 6, 6)
        elif ptype == 'coinbag':
            glColor3f(*neon(0.1, 0.5, 1.0))
            box(20, 20, 20)
            glColor3f(*neon(0.6, 0.9, 1.0))
            glPushMatrix(); glTranslatef(0, 14, 0); vcyl(5, 9, 8); glPopMatrix()
        elif ptype == 'invincibility':
            glColor3f(*neon(0.0, 1.0, 0.4))
            gluSphere(gluNewQuadric(), 11, 12, 12)
            for ang in range(0, 360, 60):
                glPushMatrix()
                glRotatef(ang, 0, 1, 0); glTranslatef(16, 0, 0)
                box(6, 6, 6)
                glPopMatrix()

        # -- Restore full viewport and switch back to 2-D for text --
        glViewport(0, 0, WIN_W, WIN_H)

        glDisable(GL_DEPTH_TEST)
        # Label
        glColor3f(*neon(1.0, 1.0, 0.3))
        draw_text_lg(vx - len(label)*7, vy - 60, label)
        # Sublabel
        glColor3f(*neon(0.6, 1.0, 0.6))
        draw_text(vx - len(sublabel)*4, vy - 85, sublabel, GLUT_BITMAP_HELVETICA_12)
        # Description
        glColor3f(0.75, 0.75, 0.85)
        draw_text(vx - len(desc)*3, vy - 105, desc, GLUT_BITMAP_HELVETICA_12)
        glEnable(GL_DEPTH_TEST)

    # Also show coin
    glViewport(WIN_W//2 - 80, 80, 160, 160)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45, 1.0, 1.0, 300.0)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    gluLookAt(0, 0, 55,  0, 0, 0,  0, 1, 0)
    glRotatef(spin, 0, 1, 0)
    glColor3f(*neon(1.0, 0.90, 0.1))
    segs = 14; step = 2.0*math.pi/segs
    glBegin(GL_TRIANGLES)
    for i in range(segs):
        a0,a1 = i*step,(i+1)*step
        glVertex3f(0,0,0)
        glVertex3f(math.cos(a0)*10,math.sin(a0)*10,0)
        glVertex3f(math.cos(a1)*10,math.sin(a1)*10,0)
    glEnd()
    glViewport(0, 0, WIN_W, WIN_H)

    glDisable(GL_DEPTH_TEST)
    glColor3f(*neon(1.0, 1.0, 0.3))
    draw_text_lg(WIN_W//2 - 28, 255, "Coin")
    glColor3f(0.75, 0.75, 0.85)
    draw_text(WIN_W//2 - 100, 233, "+1 coin, +5 bonus pts on Game Over", GLUT_BITMAP_HELVETICA_12)

    # Back button
    _draw_button(WIN_W//2 - 80, 20, WIN_W//2 + 80, 58,
                 "< BACK",
                 neon(0.7, 0.7, 1.0), (0.08, 0.08, 0.20))
    glEnable(GL_DEPTH_TEST)

# ──────────────────────────────────────────────────────────────
# MINIMAP (Updated to handle new types)
# ──────────────────────────────────────────────────────────────
def draw_minimap():
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    mx,my=MINIMAP_X,MINIMAP_Y; mw,mh=MINIMAP_W,MINIMAP_H

    # Background
    glColor3f(0.03,0.03,0.10)
    glBegin(GL_QUADS)
    glVertex3f(mx,my,0); glVertex3f(mx+mw,my,0)
    glVertex3f(mx+mw,my+mh,0); glVertex3f(mx,my+mh,0)
    glEnd()
    glColor3f(*neon(0.0,0.8,1.0)); glLineWidth(1)
    glBegin(GL_LINES)
    glVertex3f(mx,my,0);       glVertex3f(mx+mw,my,0)
    glVertex3f(mx+mw,my,0);   glVertex3f(mx+mw,my+mh,0)
    glVertex3f(mx+mw,my+mh,0);glVertex3f(mx,my+mh,0)
    glVertex3f(mx,my+mh,0);   glVertex3f(mx,my,0)
    glEnd()
    glColor3f(0.5,0.5,0.7)
    draw_text(mx+3,my+mh-14,"MAP",GLUT_BITMAP_HELVETICA_12)

    # Road strip
    rr = (ROAD_HALF*2)/1200.0
    rx0=mx+mw*(0.5-rr*0.5); rx1=mx+mw*(0.5+rr*0.5)
    glColor3f(*road_col())
    glBegin(GL_QUADS)
    glVertex3f(rx0,my+18,0); glVertex3f(rx1,my+18,0)
    glVertex3f(rx1,my+mh-18,0); glVertex3f(rx0,my+mh-18,0)
    glEnd()

    # Helper: map world-x to minimap-x (mirrored: negative world-x → right side)
    def mm_x(world_x):
        # Negate world_x to mirror horizontally
        rel = (-world_x) / float(ROAD_HALF)
        return mx + mw * (0.5 + rel * 0.45)

    # Obstacles
    for o in obstacles:
        if o['hit']: continue
        oz_rel = (o['z'] - player_z) / 700.0
        pmy2 = my + mh//2 + oz_rel * (mh * 0.42)
        pmx2 = mm_x(LANE_CENTERS[o['lane']])
        if my < pmy2 < my+mh:
            if o['type'] == 'fallen_tree':
                glColor3f(1.0, 0.6, 0.0)
            elif o['type'] not in ('pothole', 'cone'):
                glColor3f(1.0, 0.2, 0.0)
            else:
                glColor3f(1.0, 0.8, 0.0)
            glPointSize(4)
            glBegin(GL_POINTS); glVertex3f(pmx2, pmy2, 0); glEnd()

    # Collectables
    for d in decorations:
        if d['type'] in ('coin','multiplier','coinbag','invincibility'):
            oz_rel = (d['z'] - player_z) / 700.0
            pmy2 = my + mh//2 + oz_rel * (mh * 0.42)
            pmx2 = mm_x(d['x'])
            if my < pmy2 < my+mh:
                color = (1,0.8,0) if d['type']=='coin' else (0.5,1.0,0.5)
                glColor3f(*color); glPointSize(6)
                glBegin(GL_POINTS); glVertex3f(pmx2, pmy2, 0); glEnd()

    # Player marker
    pmx2 = mm_x(player_x)
    glColor3f(*neon(0.0,1.0,0.5)); glPointSize(8)
    glBegin(GL_POINTS); glVertex3f(pmx2, my+mh//2, 0); glEnd()

    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glEnable(GL_DEPTH_TEST)


def draw_speed_bar():
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    bx,by,bh=WIN_W-28,68,188
    ratio=(speed-10)/50.0
    glColor3f(0.07,0.07,0.13)
    glBegin(GL_QUADS)
    glVertex3f(bx,by,0); glVertex3f(bx+20,by,0)
    glVertex3f(bx+20,by+bh,0); glVertex3f(bx,by+bh,0)
    glEnd()
    fc=blend((0.2,1.0,0.2),(1.0,0.2,0.2),ratio)
    glColor3f(*neon(*fc))
    fh=int(bh*ratio)
    glBegin(GL_QUADS)
    glVertex3f(bx+2,by+2,0); glVertex3f(bx+18,by+2,0)
    glVertex3f(bx+18,by+2+fh,0); glVertex3f(bx+2,by+2+fh,0)
    glEnd()
    glColor3f(*neon(0.6,0.6,0.9)); glLineWidth(1)
    glBegin(GL_LINES)
    glVertex3f(bx,by,0); glVertex3f(bx+20,by,0)
    glVertex3f(bx+20,by,0); glVertex3f(bx+20,by+bh,0)
    glVertex3f(bx+20,by+bh,0); glVertex3f(bx,by+bh,0)
    glVertex3f(bx,by+bh,0); glVertex3f(bx,by,0)
    glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glEnable(GL_DEPTH_TEST)

# ──────────────────────────────────────────────────────────────
# RESET (Updated to handle new variables)
# ──────────────────────────────────────────────────────────────
def reset_game():
    global player_lane,player_z,player_x,steer_lean,wheel_angle, speed,score,health,coins,game_state,obstacles,decorations,particles, spawn_z_next,day_factor,night_target,auto_day_time,manual_override, multiplier_timer, invincible_timer, powerup_multiplier, invincible, coin_row_next, bob_time, fpv_mode

    player_lane=2; player_z=0.0; player_x=float(LANE_CENTERS[2])
    steer_lean=0.0; wheel_angle=0.0
    speed=30.0; score=0.0; health=5; coins=0
    game_state="play"
    obstacles.clear(); decorations.clear(); particles.clear()
    spawn_z_next=500.0; auto_day_time=0.0
    day_factor=1.0; night_target=1.0; manual_override=False
    multiplier_timer = 0.0; invincible_timer = 0.0
    powerup_multiplier = 1.0; invincible = False
    coin_row_next = 600.0   # reset coin row spawner (global now properly declared)
    bob_time = 0.0; fpv_mode = False

    # Initialize map content
    for i in range(12): spawn_row(500+i*SEGMENT_GAP)
    for i in range(32): spawn_deco(250+i*90)
    # Pre-seed a few coin rows so player sees coins right away
    for i in range(6): spawn_coin_row(400 + i * 200)


# ──────────────────────────────────────────────────────────────
# DISPLAY (No functional changes needed here, only uses the new functions)
# ──────────────────────────────────────────────────────────────
def display():
    sc=sky_col()
    glClearColor(*sc,1.0)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    glViewport(0,0,WIN_W,WIN_H)

    # ── Main Menu ──────────────────────────────────────────────────
    if game_state == "menu":
        glDisable(GL_DEPTH_TEST)
        draw_sky()
        glEnable(GL_DEPTH_TEST)
        draw_main_menu()
        glutSwapBuffers()
        return

    # ── Items Screen ───────────────────────────────────────────────
    if game_state == "items":
        draw_items_screen()
        glutSwapBuffers()
        return

    # ── Normal game render ─────────────────────────────────────────
    glDisable(GL_DEPTH_TEST); draw_sky(); glEnable(GL_DEPTH_TEST)
    setup_camera()
    draw_ground()
    draw_grid_overlay(player_z)
    draw_road_markings(player_z)
    draw_guardrails(player_z)

    # Draw Decorations (Handles coins and powerups)
    for d in decorations:
        ox,oz=d['x'],d['z']
        t=d['type']
        bob = d.get('bob', 0.0)
        if   t=='tree':     draw_tree(ox,oz)
        elif t=='bush':     draw_bush(ox,oz)
        elif t=='grass':    draw_grass_tuft(ox,oz)
        elif t=='lamp':     draw_lamp_post(ox,oz,d['side'])
        elif t=='building': draw_building(ox,oz,d['w'],d['h'],d['d'],d['seed'])
        elif t=='coin':          draw_coin(ox, oz, bob)
        elif t=='multiplier':    draw_powerup(ox, oz, 'multiplier', bob)
        elif t=='coinbag':       draw_powerup(ox, oz, 'coinbag', bob)
        elif t=='invincibility': draw_powerup(ox, oz, 'invincibility', bob)

    # Draw Obstacles (Handles fallen trees)
    for o in obstacles:
        if o['hit']: continue
        ox,oz=LANE_CENTERS[o['lane']],o['z']
        if   o['type']=='pothole':     draw_pothole(ox,oz)
        elif o['type']=='cone':        draw_traffic_cone(ox,oz)
        elif o['type']=='fallen_tree': draw_fallen_tree(ox, oz, -1 if o['lane']==0 else 1)
        else:                          draw_obstacle_car(o['type'],ox,oz)

    # Don't draw the player car in FPV — camera is inside it
    if not fpv_mode:
        draw_player_car(player_x, steer_lean)
    draw_particles()

    # HUD and Minimap drawn last
    draw_hud(); draw_minimap(); draw_speed_bar()
    glutSwapBuffers()

# ──────────────────────────────────────────────────────────────
# IDLE & INPUT HANDLERS (Critical Logic)
# ──────────────────────────────────────────────────────────────
def idle():
    global player_z,player_x,steer_lean,wheel_angle,score, spawn_z_next,day_factor,night_target,auto_day_time,last_time, multiplier_timer, invincible_timer, powerup_multiplier, coin_row_next

    t=glutGet(GLUT_ELAPSED_TIME)/1000.0
    if last_time==0: last_time=t
    dt=min(t-last_time,0.05); last_time=t

    # Always advance animation clock (menu models spin too)
    global bob_time
    bob_time += dt

    # If game is paused, on menus, or game over — just redraw
    if game_state not in ("play",):
        glutPostRedisplay(); return
    
    # --- Powerup Timer Decay ---
    global multiplier_timer, invincible_timer, powerup_multiplier, invincible

    if multiplier_timer > 0:
        multiplier_timer = max(0.0, multiplier_timer - dt)
        if multiplier_timer <= 0:
            powerup_multiplier = 1.0
            multiplier_timer   = 0.0
    
    if invincible_timer > 0:
        invincible_timer = max(0.0, invincible_timer - dt)
        if invincible_timer <= 0:
            invincible       = False
            invincible_timer = 0.0

    # --- Day/Night Cycle (Smooth sine wave) ---
    if not manual_override:
        auto_day_time+=dt
        day_factor=0.5+0.5*math.sin(2*math.pi*auto_day_time/AUTO_CYCLE - math.pi/2)
        day_factor=max(0.0,min(1.0,day_factor))
    else:
        diff=night_target-day_factor
        if abs(diff)>0.002:
            day_factor+=diff*dt/TRANS_DUR*8
            day_factor=max(0.0,min(1.0,day_factor))

    # Move car forward (Physics calculation)
    dist=speed/3.6*18*dt
    player_z+=dist

    # Wheel spin & Steer
    circ=2*math.pi*WHEEL_R
    wheel_angle=(wheel_angle+(dist/circ)*360)%360
    target_x=float(LANE_CENTERS[player_lane])
    player_x+=(target_x-player_x)*8*dt
    steer_lean+=(-steer_lean)*5*dt

    # Score (Modified to use multiplier)
    score+=speed*dt*0.5 * powerup_multiplier

    # Spawn obstacles & decorations
    while spawn_z_next<player_z+SPAWN_AHEAD:
        spawn_row(spawn_z_next)
        if random.random()<0.65: spawn_deco(spawn_z_next+random.uniform(-40,40))
        spawn_z_next+=SEGMENT_GAP+random.uniform(-15,35)

    # Spawn individual coin rows — more frequent than powerups (~every 180 units)
    while coin_row_next < player_z + SPAWN_AHEAD:
        spawn_coin_row(coin_row_next)
        coin_row_next += 180.0 + random.uniform(-30, 30)

    cull_all(); check_collisions(); update_particles(dt)
    glutPostRedisplay()


def keyboard(key,x,y):
    global speed, player_lane, steer_lean, game_state, night_target, manual_override
    global day_factor, health, invincible, confirm_from_state, fpv_mode

    # ESC — use glutLeaveMainLoop so GLUT cleans up properly and the window actually closes
    if key == b'\x1b':
        glutLeaveMainLoop()
        return

    # Menu screens handled via mouse
    if game_state in ("menu", "items"):
        return

    # R key: confirm-restart dialog
    if key in (b'r', b'R'):
        if game_state != "confirm_restart":
            confirm_from_state = game_state
            game_state = "confirm_restart"
        return

    # P key: pause / resume
    if key in (b'p', b'P'):
        if game_state == "play":
            game_state = "pause"
        elif game_state == "pause":
            game_state = "play"
        return

    # C key: toggle first-person / chase camera (works while playing or paused)
    if key in (b'c', b'C'):
        fpv_mode = not fpv_mode
        return

    if game_state != "play":
        return

    # L key: manual day/night toggle
    if key in (b'l', b'L'):
        manual_override = True
        night_target = 0.0 if day_factor > 0.5 else 1.0
        return

    if   key in (b'w', b'W'): speed = min(60, speed + 5)
    elif key in (b's', b'S'): speed = max(10, speed - 5)
    elif key in (b'a', b'A'):
        if player_lane < NUM_LANES - 1: player_lane += 1; steer_lean = -1.0
    elif key in (b'd', b'D'):
        if player_lane > 0:            player_lane -= 1; steer_lean =  1.0


def special_key(key,x,y):
    global speed,player_lane,steer_lean,game_state
    if game_state!="play": return

    if   key==GLUT_KEY_UP:   speed=min(60,speed+5)
    elif key==GLUT_KEY_DOWN: speed=max(10,speed-5)
    elif key==GLUT_KEY_LEFT:
        if player_lane<NUM_LANES-1: player_lane+=1; steer_lean=-1.0
    elif key==GLUT_KEY_RIGHT:
        if player_lane>0: player_lane-=1; steer_lean=1.0

def mouse(button,state,x,y):
    global game_state, confirm_from_state
    if button != GLUT_LEFT_BUTTON or state != GLUT_DOWN:
        return
    oy = WIN_H - y   # convert GLUT (top-origin) to OpenGL (bottom-origin)

    if game_state == "menu":
        BX0, BX1 = WIN_W//2 - 110, WIN_W//2 + 110
        if BX0 <= x <= BX1 and 440 <= oy <= 490:   # PLAY
            reset_game()
            return
        if BX0 <= x <= BX1 and 375 <= oy <= 425:   # ITEMS
            game_state = "items"
            return
        if BX0 <= x <= BX1 and 310 <= oy <= 360:   # EXIT
            glutLeaveMainLoop()
            return

    elif game_state == "items":
        if WIN_W//2-80 <= x <= WIN_W//2+80 and 20 <= oy <= 58:
            game_state = "menu"
            return

    elif game_state == "gameover":
        CX = WIN_W // 2
        # PLAY AGAIN: x[CX-220..CX-10]  y[300..342]
        if CX-220 <= x <= CX-10 and 300 <= oy <= 342:
            reset_game()
        # MAIN MENU: x[CX+10..CX+220]  y[300..342]
        elif CX+10 <= x <= CX+220 and 300 <= oy <= 342:
            game_state = "menu"

    elif game_state == "confirm_restart":
        CX = WIN_W // 2
        # YES: x[CX-210..CX-10]  y[280..328]  (py0=250, btn_y0=py0+30=280)
        if CX-210 <= x <= CX-10 and 280 <= oy <= 328:
            reset_game()
        # NO:  x[CX+10..CX+210]  y[280..328]
        elif CX+10 <= x <= CX+210 and 280 <= oy <= 328:
            game_state = confirm_from_state

# ──────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ──────────────────────────────────────────────────────────────
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(WIN_W,WIN_H)
    glutInitWindowPosition(40,30)
    glutCreateWindow(b"NEON DRIFT | 5-Lane 3D Racer")
    # Start at main menu — world will be initialised when Play is clicked
    global game_state
    game_state = "menu"
    glutDisplayFunc(display)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(special_key)
    glutMouseFunc(mouse)
    glutMainLoop()

if __name__=="__main__":
    main()