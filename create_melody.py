"""
Take pitch arrays from pitch_detection (numpy only) and find key, then generate melody with pretty_midi.
Pitch: from pitch_detection only. Key: from librosa only (key_to_degrees for major keys).
"""

import numpy as np
import pretty_midi
import librosa

from makeuoft import pitch_detection
from pitch_detection import (
    NOTE_NAMES,
    detect_all_pitches_from_buffer,
    detect_pitch_from_buffer,
    format_pitch,
    freq_to_note_and_octave as fq,
)


def find_key(pitch_classes: np.ndarray) -> str:
    """
    Find the most likely **major** key using librosa (key_to_degrees) only.
    Pitch data must come from pitch_detection; this function only does key finding.
    """
    valid = pitch_classes[pitch_classes >= 0]
    h = np.bincount(valid, minlength=12)  # we want the quantity of notes played
    h /= np.sum(h)  

    major_profile = np.array([
        6.35, 2.23, 3.48, 2.33,
        4.38, 4.09, 2.52, 5.19,
        2.39, 3.66, 2.29, 2.88
    ]) # we are relating everything to how close it is to c major
    major_profile /= np.sum(major_profile)

    result = None
    best_score = -1

    for i in range(12):
        r = np.roll(major_profile, i) # we can test against different keys
        score = np.dot(r,h) #

        if score > best_score:
            best_score = score
            result = i
    return pitch_detection.NOTE_NAMES[result]
