# -*- coding: utf-8 -*-
"""Shared design tokens for the README assets.

Light paper + deep green ink, warm and typographic. No gradients, no shadows,
no dark navy anywhere.
"""

# surfaces
BG = '#F4F3ED'          # warm paper
PANEL = '#FFFFFF'       # raised card
CARD = '#EAEAE3'        # muted card (the "before" side)
DARK = '#21382E'        # inverse panel used once, for the workflow

# ink
INK = '#193A2B'         # primary
ACCENT = '#397B51'      # accent green
MUTED = '#62766A'       # secondary text
FAINT = '#778177'       # labels on the muted card
GHOST = '#7B857B'       # the vague "before" titles
ON_DARK = '#F4F2EC'
ON_DARK_MUTED = '#B9CEC2'
ON_DARK_DIM = '#A8C1B2'

# lines
HAIRLINE = '#E3EAE1'
CARD_LINE = '#D1D7CD'
ARROW = '#76A287'
ARROW_ON_DARK = '#89B69C'

# pale row tints, cycled across rows of three
TINTS = ('#E8F1E7', '#EFF2FA', '#F6EEF4')

FONT = '-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif'
EMOJI = 'Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif'


def svg_open(w, h, title, desc, radius=22, fill=BG):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" role="img" aria-labelledby="t d">\n'
        '  <title id="t">%s</title>\n'
        '  <desc id="d">%s</desc>\n'
        '  <rect width="%d" height="%d" rx="%d" fill="%s"/>\n'
    ) % (w, h, w, h, title, desc, w, h, radius, fill)
