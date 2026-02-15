"""
Take pitch arrays from pitch_detection (numpy only) and find key, then generate melody with pretty_midi.
- Registers your melody from the sounds you give (pitch + length).
- Continues by taking the last 4 notes and moving them up 2 scale degrees.
- Adds a 1-5-6-4 (I, V, vi, IV) chord progression.
- Adds a swing drum pattern.
"""

import numpy as np
import pretty_midi
import aubio
import scipy

from pitch_detection import (
    NOTE_NAMES,
    NOTE_TO_PC,
    detect_all_pitches_from_buffer,
    detect_pitch_from_buffer,
    format_pitch,
    freq_to_note_and_octave as fq,
)

# Major scale: semitones from root for degrees 1–7 (C major = C D E F G A B).
MAJOR_SCALE_SEMITONES = [0, 2, 4, 5, 7, 9, 11]


def find_key(pitch_classes: np.ndarray) -> str:
    """
    Find the most likely **major** key using librosa (key_to_degrees) only.
    Pitch data must come from pitch_detection; this function only does key finding.
    """
    valid = pitch_classes[pitch_classes >= 0]
    if len(valid) == 0:
        return "C"
    h = np.bincount(valid, minlength=12).astype(np.float32)  # we want the quantity of notes played
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
        score = np.dot(r,h) # and then we see how close they are to each other

        if score > best_score:
            best_score = score
            result = i
    return NOTE_NAMES[result]


def key_name_to_root_pc(key_name: str) -> int:
    """Key name (e.g. 'C', 'F#') -> pitch class 0–11."""
    return NOTE_NAMES.index(key_name) if key_name in NOTE_NAMES else 0


def pitch_class_to_scale_degree(pc: int, key_root_pc: int) -> int:
    """Map pitch class to scale degree 1–7 in the given major key. Non-scale notes snap to nearest."""
    d = (pc - key_root_pc) % 12
    best_deg, best_dist = 1, 12
    for deg, semit in enumerate(MAJOR_SCALE_SEMITONES):
        dist = min((d - semit) % 12, (semit - d) % 12)
        if dist < best_dist:
            best_dist = dist
            best_deg = deg + 1
    return best_deg


def scale_degree_to_pitch_class(degree: int, key_root_pc: int, octave_up: bool = False) -> int:
    """Scale degree 1–7 -> pitch class 0–11. octave_up: add 12 if we wrapped past 7."""
    idx = (degree - 1) % 7
    pc = (key_root_pc + MAJOR_SCALE_SEMITONES[idx]) % 12
    return pc


def transpose_note_up_scale_degrees(
    pitch_class: int, key_root_pc: int, steps: int = 2) -> tuple[int, int]:
    """Move a note up `steps` scale degrees in the key. Returns (pitch_class, octave_offset)."""
    deg = pitch_class_to_scale_degree(pitch_class, key_root_pc)
    new_deg = (deg - 1 + steps) % 7 + 1
    octave_up = 1 if (deg - 1 + steps) >= 7 else 0
    new_pc = scale_degree_to_pitch_class(new_deg, key_root_pc)
    return new_pc, octave_up


def pitch_classes_to_note_events(
    pitch_classes: np.ndarray,
    sample_rate: int = 8000,
    hop_size: int = 512,
    silence_frames: int = 1
) -> list[tuple[int, float, float]]:
    """
    Convert a per-frame pitch-class array into (pitch_class, start_time, duration) notes.

    Consecutive frames with the same pitch become one note; duration = frames * (hop_size / sample_rate).
    Skips invalid frames (pitch_class < 0 or > 11).
    Returns list of (pitch_class, start_sec, duration_sec).
    """
    frame_duration = hop_size / float(sample_rate)
    events: list[tuple[int, float, float]] = []
    i = 0
    while i < len(pitch_classes):
        pc = int(pitch_classes[i])
        if pc < 0 or pc > 11:
            i += 1
            continue
        start = i
        current = pc
        j = i + 1
        last_valid = i
        while j < len(pitch_classes) and int(pitch_classes[j]) == pc:
            next_pc = int(pitch_classes[j])
            if next_pc == current:
                last_valid = j
                j += 1
            elif next_pc < 0 or next_pc > 11:
                look_ahead_range = pitch_classes[j : j + silence_frames + 1]
                if current in look_ahead_range.astype(int):
                    # It's just a tiny gap, keep the note going
                    j += 1
                else:
                    # True silence or different note found
                    break
            else:
                # A different valid pitch started. Stop this note.
                break
        duration = (j - i) * frame_duration
        start_sec = start * frame_duration
        
        events.append((current, start_sec, duration))
        
        # Move i to the end of this note
        i = j
        
    return events


def _add_chord(
    inst: pretty_midi.Instrument,
    root_pc: int,
    is_minor: bool,
    start: float,
    duration: float,
    base_midi: int = 60,
    velocity: int = 55,
) -> None:
    """Add a triad (root, third, fifth) to the instrument."""
    third = 3 if is_minor else 4
    for semit in (0, third, 7):
        midi_note = base_midi + (root_pc + semit) % 12
        if (root_pc + semit) >= 12:
            midi_note += 12
        midi_note = max(0, min(127, midi_note))
        inst.notes.append(
            pretty_midi.Note(velocity=velocity, pitch=midi_note, start=start, end=start + duration)
        )

def get_nearest_musical_duration(duration, beat_seconds):
    """Snaps a duration to the closest standard musical value."""
    # Multipliers: 1/4 (16th), 1/2 (8th), 1 (Quarter), 2 (Half), 4 (Whole)
    multipliers = [0.25, 0.5, 1.0, 2.0, 4.0]
    allowed_durations = [m * beat_seconds for m in multipliers]
    
    # Find the closest duration from our list
    return min(allowed_durations, key=lambda x: abs(x - duration))

def _add_swing_drum_pattern(
    drum_inst: pretty_midi.Instrument,
    start_time: float,
    num_bars: int,
    tempo: float = 120,
    velocity_kick: int = 70,
    velocity_snare: int = 60,
    velocity_hihat: int = 60,
) -> None:
    """Add a simple swing pattern: kick 1&3, snare 2&4, hi-hat 8ths with swing."""
    beat_duration = 60.0 / tempo
    bar_duration = 4 * beat_duration
    eighth = beat_duration / 2
    # Swing: second 8th of each beat is delayed (roughly 2:1 ratio)
    swing_shift = eighth * 0.33  # delay the "and" of each beat

    KICK = 36
    SNARE = 38
    CLOSED_HH = 42

    for bar in range(num_bars):
        t0 = start_time + bar * bar_duration
        # Kick on 1 and 3
        drum_inst.notes.append(
            pretty_midi.Note(velocity=velocity_kick, pitch=KICK, start=t0, end=t0 + eighth * 1.5)
        )
        drum_inst.notes.append(
            pretty_midi.Note(
                velocity=velocity_kick,
                pitch=KICK,
                start=t0 + 2 * beat_duration,
                end=t0 + 2 * beat_duration + eighth * 1.5,
            )
        )
        # Snare on 2 and 4
        drum_inst.notes.append(
            pretty_midi.Note(
                velocity=velocity_snare,
                pitch=SNARE,
                start=t0 + beat_duration,
                end=t0 + beat_duration + eighth * 1.5,
            )
        )
        drum_inst.notes.append(
            pretty_midi.Note(
                velocity=velocity_snare,
                pitch=SNARE,
                start=t0 + 3 * beat_duration,
                end=t0 + 3 * beat_duration + eighth * 1.5,
            )
        )
        # Hi-hat: 8ths with swing (first 8th on beat, second 8th delayed)
        for beat_idx in range(4):
            b = t0 + beat_idx * beat_duration
            drum_inst.notes.append(
                pretty_midi.Note(velocity=velocity_hihat, pitch=CLOSED_HH, start=b, end=b + eighth * 0.5)
            )
            drum_inst.notes.append(
                pretty_midi.Note(
                    velocity=velocity_hihat,
                    pitch=CLOSED_HH,
                    start=b + eighth + swing_shift,
                    end=b + eighth + swing_shift + eighth * 0.5,
                )
            )


def create_melody(
    pitch_classes: np.ndarray,
    output_path: str = "melody.mid",
    *,
    sample_rate: int = 8000,
    hop_size: int = 512,
    fixed_note_duration: float | None = None,
    velocity: int = 115,
    program: int = 0,
    base_octave: int = 4,
    tempo: float = 120,
) -> pretty_midi.PrettyMIDI:
    """
    Register your melody from the pitch-class array (with note lengths), then:
    - Play the registered melody (your input).
    - Continue with the last 4 notes moved up 2 scale degrees (same lengths).
    - Add I, V, vi, IV chords (1 bar each).
    - Add a swing drum pattern.

    pitch_classes: from detect_all_pitches_from_buffer(samples, sample_rate, hop_size)[1].
    Pass sample_rate (and hop_size) so note lengths are derived from how long you held each pitch.
    """
    pm = pretty_midi.PrettyMIDI()
    seconds_per_beat = 60.0 / tempo
    whole_note = seconds_per_beat * 4
    half_note = seconds_per_beat * 2
    quarter_note = seconds_per_beat
    eighth_note = seconds_per_beat / 2
    sixteenth_note = seconds_per_beat / 4
    bar_duration = seconds_per_beat * 4
    key_name = find_key(pitch_classes)
    key_root_pc = key_name_to_root_pc(key_name)

    # 1) Convert to note events (pitch_class, start_sec, duration_sec) — this registers your melody + lengths
    if fixed_note_duration is not None:
        frame_dur = fixed_note_duration
        t = 0.0
        events = []
        for i in range(len(pitch_classes)):
            pc = int(pitch_classes[i])
            if 0 <= pc <= 11:
                events.append((pc, t, frame_dur))
            t += frame_dur
    else:
        events = pitch_classes_to_note_events(pitch_classes, sample_rate=sample_rate, hop_size=hop_size)
        if not events:
            frame_dur = 0.25
            t = 0.0
            for i in range(len(pitch_classes)):
                pc = int(pitch_classes[i])
                if 0 <= pc <= 11:
                    events.append((pc, t, frame_dur))
                t += frame_dur

    beat = 60.0 / tempo
    bar_duration = 4 * beat
    min_duration = 0.12

    melody_inst = pretty_midi.Instrument(program=1)
    chord_inst = pretty_midi.Instrument(program=4)  # electric piano / chord
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True)

    # 2) Add the registered melody (your input, with your note lengths)
    events = [e for e in events if e[2] > 0.12] # Ignore notes shorter than 0.1 seconds
    first_note_start = events[0][1]
    current_grid_time = 0.0
    for pc, start, duration in events:
        # If the first note is a '0' and it's super short, it's just mic noise.
        adjusted_start = start - first_note_start
        q_start = round(adjusted_start / eighth_note) * eighth_note
        q_start += 0.02
        q_start = max(q_start, current_grid_time)
        
        q_duration = get_nearest_musical_duration(duration, seconds_per_beat)
        
        # C. Snap the pitch to the detected key (optional: steps=0 just forces it into the scale)
        new_pc, octave_offset = transpose_note_up_scale_degrees(pc, key_root_pc, steps=0)
        
        midi_note = (base_octave + 1 + octave_offset) * 12 + new_pc
        midi_note = max(0, min(127, midi_note))
        
        melody_inst.notes.append(
            pretty_midi.Note(
                velocity=velocity, 
                pitch=midi_note, 
                start=q_start, 
                end=q_start + q_duration
            )
        )
        current_grid_time = q_start + q_duration

    # 3) Last 4 notes, up 2 scale degrees (same lengths), placed after the last note
    last_four = events[-4:] if len(events) >= 4 else events
    end_of_melody = max((start + duration for _, start, duration in events), default=0.0)
    if last_four:
        t_cont = end_of_melody + 0.1  # small gap
        for pc, _, duration in last_four:
            new_pc, octave_up = transpose_note_up_scale_degrees(pc, key_root_pc, steps=2)
            duration = max(min_duration, duration)
            midi_note = (base_octave + 1 + octave_up) * 12 + new_pc
            midi_note = max(0, min(127, midi_note))
            melody_inst.notes.append(
                pretty_midi.Note(velocity=velocity, pitch=midi_note, start=t_cont, end=t_cont + duration)
            )
            t_cont += duration
        end_of_melody = t_cont

    # 4) Chords: I, V, vi, IV — each chord 1 bar, repeat until we cover melody + continuation
    chord_roots = [
        key_root_pc,  # I
        (key_root_pc + 7) % 12,  # V
        (key_root_pc + 9) % 12,  # vi
        (key_root_pc + 5) % 12,  # IV
    ]
    chord_minor = [False, False, True, False]  # vi is minor
    total_time = end_of_melody
    num_bars = max(4, int(total_time / bar_duration) + 1)
    chord_start = 0.0
    for i in range(num_bars):
        root = chord_roots[i % 4]
        is_minor = chord_minor[i % 4]
        _add_chord(chord_inst, root, is_minor, chord_start, bar_duration, base_midi=48, velocity=72)
        chord_start += bar_duration

    # 5) Swing drums for the same number of bars
    _add_swing_drum_pattern(drum_inst, 0.0, num_bars=num_bars, tempo=tempo)

    pm.instruments.append(melody_inst)
    pm.instruments.append(chord_inst)
    pm.instruments.append(drum_inst)
    pm.write(output_path)
    return pm
    