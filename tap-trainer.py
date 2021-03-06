#! /usr/bin/python3

# This program is (C) 2021 by folkert@vanheusden.com.
# License: GPL v3.0

import configparser
import pygame
import pygame.midi
import random
import sys
import threading
import time

from enum import Enum
from os.path import expanduser

home_dir = expanduser("~")
cfg_file = home_dir + '/.tap-trainer.cfg'
cfg_section = 'main'

config = configparser.RawConfigParser()
config.read(cfg_file)

try:
    BPM = config.getint(cfg_section, 'BPM')

    expert = config.getboolean(cfg_section, 'expert')

except configparser.NoSectionError:
    BPM = 116
    expert = False

class Wait(Enum):
    t_none = None
    t1 = 1
    t2 = 2
    t4 = 3

def gen_pattern(ticks, allow_1st_sleep):
    out = []

    while len(out) < 4:
        choice = random.randint(0, 3)

        if choice == 0:
            out.append(Wait.t1)
        
        elif choice == 1:
            if len(out) < 3:
                out.append(Wait.t2)
                out.append(Wait.t_none)

        elif choice == 2:
            if len(out) == 0:
                out.append(Wait.t4)
                out.append(Wait.t_none)
                out.append(Wait.t_none)
                out.append(Wait.t_none)

        elif choice == 3 and (allow_1st_sleep or len(out) > 0):
            out.append(Wait.t_none)

    return out

def dump_config():
    config = configparser.RawConfigParser()
    config.add_section(cfg_section)
    config.set(cfg_section, 'BPM', BPM)
    config.set(cfg_section, 'expert', expert)

    with open(cfg_file, 'w') as configfile:
        config.write(configfile)

pygame.init()

pygame.fastevent.init()

pygame.midi.init()
midi_in = pygame.midi.Input(pygame.midi.get_default_input_id())

BLACK = (  0,   0,   0)
WHITE = (255, 255, 255)
RED   = (255,  40,  40)
GREEN = ( 40, 255,  40)
BLUE  = ( 40,  40, 255)

line_width = 5

bar_size = 4

screen_info = pygame.display.Info()
size = [screen_info.current_w, screen_info.current_h]

screen = pygame.display.set_mode(size, pygame.FULLSCREEN)

key_left = pygame.K_z
key_right = pygame.K_SLASH

qx = size[0] // 4
qy = size[1] // 4
dx = size[0] // 2 // bar_size
dy = size[1] // 2 // 5

pygame.display.set_caption('Tap-trainer')

count_ok = count_fail = 0

font_small = pygame.font.Font(pygame.font.get_default_font(), 16)
font_big = pygame.font.Font(pygame.font.get_default_font(), dy)

def draw_note(x, y, which, color):
    lw = int(line_width * 1.5)
    radius = dy // 2
    xp = x + int(radius * 1.5) // 2 + line_width

    if which != Wait.t_none:
        pygame.draw.circle(screen, color, [x, y], radius, lw)

    if which == Wait.t_none and color == RED:
        pygame.draw.line(screen, RED, [xp - radius, y - radius], [xp + radius, y + radius], lw)
        pygame.draw.line(screen, RED, [xp + radius, y - radius], [xp - radius, y + radius], lw)

    if which == Wait.t1:
        pygame.draw.circle(screen, color, [x, y], radius) # closed circle
        pygame.draw.line(screen, color, [xp, y], [xp, y - dy * 3], lw)

    elif which == Wait.t2:
        pygame.draw.line(screen, color, [xp, y], [xp, y - dy * 3], lw)

    elif which == Wait.t4:
        # it's just a circle
        pass

def draw_bar(which, qx, top, pattern, ok, pos, draw_marker, expert):
    for lines in range(0, 5):
        pygame.draw.line(screen, WHITE, [qx, top + lines * dy], [qx * 3, top + lines * dy], line_width)

    pygame.draw.line(screen, WHITE, [qx, top], [qx, top + 4 * dy], line_width)
    pygame.draw.line(screen, WHITE, [qx * 3 - dx // 4, top], [qx * 3 - dx // 4, top + 4 * dy], line_width)
    pygame.draw.line(screen, WHITE, [qx * 3, top], [qx * 3, top + 4 * dy], line_width)

    text_surface = font_big.render(which, True, WHITE)
    screen.blit(text_surface, dest=(qx // 3, top + int(1.5 * dy)))

    nr = 0
    for n in pattern:
        if nr == pos and expert == False:
            c = BLUE
        elif ok[nr]:
            c = GREEN
        elif ok[nr] == False:
            c = RED
        else:
            c = WHITE

        x = qx + dx * nr * 7 // 8 + dx // 2
        y = top + dy * 3

        if n == Wait.t_none and nr == pos and draw_marker and expert == False:
            pygame.draw.circle(screen, BLUE, [x, y], dy // 8)

        else:
            draw_note(x, y, n, c)

        nr += 1

def draw_screen(pattern_left, ok_left, pattern_right, ok_right, pos, expert, BPM):
    screen.fill(BLACK)

    text_surface = font_small.render('Tap-trainer, (C) 2021 by folkert@vanheusden.com', True, WHITE)
    screen.blit(text_surface, dest=(0, 0))

    info = "press 'q' to exit | %d BPM | " % BPM
 
    text_surface = font_small.render(info + 'expert' if expert else info + 'beginner', True, WHITE)
    screen.blit(text_surface, dest=(size[0] - text_surface.get_width(), 0))

    draw_marker = pos < len(pattern_left) and pattern_left[pos] == Wait.t_none and pattern_right[pos] == Wait.t_none

    draw_bar('L', qx, dy // 2, pattern_left, ok_left, pos, draw_marker, expert)

    draw_bar('R', qx, dy // 2 + qy * 2, pattern_right, ok_right, pos, draw_marker, expert)

    total = count_ok + count_fail
    if total > 0:
        str_ = '%3d%%' % (count_ok / total * 100)

        text_surface = font_big.render(str_, True, WHITE)
        screen.blit(text_surface, dest=(size[0] - text_surface.get_width(), size[1] - dy))

    pygame.display.flip()

def midi_poller():
    global midi_in

    while True:
        # really need blocking functions here
        while not midi_in.poll():
            time.sleep(0.001)

        midi_events = midi_in.read(100)

        midi_evs = pygame.midi.midis2events(midi_events, midi_in.device_id)

        for m_e in midi_evs:
            pygame.fastevent.post(m_e)

th = threading.Thread(target=midi_poller)
th.start()

slp = 60.0 / BPM

pos = 0

start_ts = None

while True:
    if pos == 0:
        if random.choice([False, True]):
            pattern_left = gen_pattern(bar_size, False)
            pattern_right = gen_pattern(bar_size, pattern_left[0] != None)

        else:
            pattern_right = gen_pattern(bar_size, False)
            pattern_left = gen_pattern(bar_size, pattern_right[0] != None)

        ok_left = [ None ] * bar_size
        ok_right = [ None ] * bar_size

    redraw = True
    got_left = got_right = False
    while start_ts == None or time.time() - start_ts <= 60.0 / BPM:
        if redraw:
            redraw = False
            draw_screen(pattern_left, ok_left, pattern_right, ok_right, pos, expert, BPM)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

            if event.type == pygame.midi.MIDIIN:
                cmd = event.status & 0xf0
                channel = event.status & 0x0f
                note = event.data1
                velocity = event.data2

                if cmd == 0x90 and channel != 9 and velocity > 0:  # note-on, no percussion
                    if note > 64:
                        if ok_right[pos] != None:
                            ok_right[pos] = False
                        else:
                            ok_right[pos] = pattern_right[pos] != Wait.t_none

                        redraw = got_right = True

                    else:
                        if ok_left[pos] != None:
                            ok_left[pos] = False
                        else:
                            ok_left[pos] = pattern_left[pos] != Wait.t_none

                        redraw = got_left = True

                    if start_ts == None:
                        start_ts = time.time()

            elif event.type == pygame.KEYDOWN:
                correct_key = False

                if event.key == key_left:
                    if ok_left[pos] != None:
                        ok_left[pos] = False
                    else:
                        ok_left[pos] = pattern_left[pos] != Wait.t_none

                    correct_key = redraw = got_left = True

                elif event.key == key_right:
                    if ok_right[pos] != None:
                        ok_right[pos] = False
                    else:
                        ok_right[pos] = pattern_right[pos] != Wait.t_none

                    correct_key = redraw = got_right = True

                elif event.key == pygame.K_q:
                    sys.exit(0)

                elif event.key == pygame.K_e:
                    expert = not expert
                    redraw = True
                    dump_config();

                elif event.key == pygame.K_MINUS:
                    if BPM > 25:
                        BPM -= 1

                    redraw = True

                    dump_config();

                elif event.unicode == '+':  # because of shift
                    if BPM < 240:
                        BPM += 1

                    redraw = True

                    dump_config();

                if start_ts == None and correct_key:
                    start_ts = time.time()

        if got_left and got_right:
            break

        time.sleep(0.001) # pygame 2.0.0 has 'wait(timeout)'

    # clear any stray key presses
    pygame.event.clear()

    if pattern_left[pos] != Wait.t_none and ok_left[pos] == None:
        ok_left[pos] = False

    if pattern_right[pos] != Wait.t_none and ok_right[pos] == None:
        ok_right[pos] = False

    pos += 1

    sleep_left = 60.0 / BPM - (time.time() - start_ts)

    if sleep_left >= 0.0:
        time.sleep(sleep_left)

    if pos == len(pattern_left):
        draw_screen(pattern_left, ok_left, pattern_right, ok_right, pos, expert, BPM)

        pos = 0

        start_ts = None

        for ok in ok_left + ok_right:
            if ok == False:
                count_fail += 1
            else:
                count_ok += 1

        time.sleep(60.0 / BPM)

    else:
        start_ts = time.time()

pygame.quit()
