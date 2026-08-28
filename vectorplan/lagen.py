"""Scheidt het plan in kleurlagen: blauwe straatnamen, grijze gebouwen, rode zones."""
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

def lees(pad):
    return np.asarray(Image.open(pad).convert('RGB')).astype(np.int16)

def maskers(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    grijstint = (abs(r - g) < 14) & (abs(g - b) < 14) & (abs(r - b) < 14)
    return {
        'blauw':  (b - r > 60) & (b - g > 60) & (b > 120),
        'rood':   (r - g > 30) & (r - b > 30) & (r > 170),
        'vulling': grijstint & (r >= 140) & (r <= 225),
        'lijn':   grijstint & (r < 140),
        'wit':    grijstint & (r > 225),
    }
