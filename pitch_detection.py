"""
Pitch detection: take audio input and extract pitch (frequency) and octave/note.
Uses aubio for robust pitch detection.

--- Quick concepts (Raspberry Pi / hackathon context) ---
  Sample rate (e.g. 44100 Hz): How many numbers we get per second. 44100 is
  standard and fine for a Pi mic; if the Pi or mic only does 16000 or 22050,
  use that and pass it to the functions — pitch detection still works.

  "samples": Quality

  YIN: A classic pitch-detection algorithm (good for music and voice). It finds
  the fundamental frequency by looking at how the waveform repeats. Other options
  in aubio: "yinfft" (faster)

  NumPy arrays: Like lists of numbers, but fixed type and stored in one block
  in memory. You can index them like lists (samples[0], samples[100:200]). Audio
  libs (and aubio) expect them because they're fast and standard for signal processing.
"""

import numpy as np
import aubio

# Standard pitch: A4 = 440 Hz. Note names in 12-TET (equal temperament).
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
A4_HZ = 440.0
MIDI_A4 = 69


def freq_to_pitch_class(freq: float) -> int:
    """
    Convert frequency (Hz) to pitch class 0-11 (C=0, C#=1, ..., B=11).
    Returns -1 if no valid pitch (for use in arrays).
    """
    if freq is None or freq <= 0 or not np.isfinite(freq):
        return -1
    midi = 69 + 12 * np.log2(freq / A4_HZ)
    midi_rounded = int(round(midi))
    midi_rounded = max(0, min(127, midi_rounded))
    return midi_rounded % 12


def freq_to_note_and_octave(freq: float) -> tuple[str, int] | None:
    """
    Convert frequency (Hz) to note name and octave (scientific pitch notation).
    Returns (note_name, octave) e.g. ("A", 4) for 440 Hz, or None if invalid.
    """
    if freq is None or freq <= 0 or not np.isfinite(freq):
        return None
    # MIDI note: 69 + 12 * log2(f / 440)
    midi = 69 + 12 * np.log2(freq / A4_HZ)
    midi_rounded = int(round(midi))
    midi_rounded = max(0, min(127, midi_rounded))
    note_index = midi_rounded % 12
    octave = (midi_rounded // 12) - 1
    return NOTE_NAMES[note_index], octave

def detect_pitch_from_buffer(
    samples: np.ndarray,  # mono waveform: one float or int per time step (length = duration * sample_rate)
    sample_rate: int = 16000,  # same rate your Pi mic used when recording
    hop_size: int = 512,
    method: str = "yin",
) -> tuple[float | None, str | None, int | None]:
    """
    Detect pitch from a numpy buffer of audio (mono float in [-1, 1] or int).
    Returns:
        (frequency_hz, note_name, octave) or (None, None, None) if no clear pitch.
    """
    # aubio wants float32 in roughly [-1, 1]. If you have int16 from a mic, we normalize.
    if samples.dtype != np.float32:
        samples = samples.astype(np.float32) / (np.iinfo(samples.dtype).max if np.issubdtype(samples.dtype, np.integer) else 1.0)
    pitch_detector = aubio.pitch(method, 4096, hop_size, sample_rate)
    pitch_detector.set_unit("Hz")
    pitch_detector.set_silence(-40)

    pitch = 0.0
    # slide over the buffer in chunks of hop_size; last chunk's pitch is what we return
    for start in range(0, len(samples) - hop_size, hop_size):
        chunk = samples[start : start + hop_size]  # numpy slice: like list[start:start+512]
        pitch = pitch_detector(chunk)

    freq = float(pitch) if pitch > 0 else None
    if freq is None:
        return None, None, None
    result = freq_to_note_and_octave(freq)
    if result is None:
        return freq, None, None
    note, octave = result
    return freq, note, octave

def detect_all_pitches_from_buffer(
    samples: np.ndarray,
    sample_rate: int = 16000,
    hop_size: int = 512,
    method: str = "yin",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect pitch at every frame over a buffer; export as numpy arrays.

    Returns:
        freqs: 1D array of frequency (Hz) per frame; 0.0 where no pitch.
        pitch_classes: 1D array of pitch class 0-11 per frame; -1 where no pitch.
    """
    if samples.dtype != np.float32:
        samples = samples.astype(np.float32) / (
            np.iinfo(samples.dtype).max if np.issubdtype(samples.dtype, np.integer) else 1.0
        )
    pitch_detector = aubio.pitch(method, 4096, hop_size, sample_rate)
    pitch_detector.set_unit("Hz")
    pitch_detector.set_silence(-40)

    freqs_list: list[float] = []
    for start in range(0, len(samples) - hop_size, hop_size):
        chunk = samples[start : start + hop_size]
        pitch = pitch_detector(chunk)
        f = float(pitch) if pitch > 0 else 0.0
        freqs_list.append(f)

    freqs = np.array(freqs_list, dtype=np.float32)
    pitch_classes = np.array([freq_to_pitch_class(f) if f > 0 else -1 for f in freqs_list], dtype=np.int32)
    return freqs, pitch_classes

# def detect_pitch_from_file(
#     path: str,
#     hop_size: int = 512,  # samples per analysis frame; smaller = more responsive, more CPU
#     sample_rate: int = 44100,  # must match how the file was recorded (e.g. Pi mic rate)
#     method: str = "yin",  # "yin" = classic, robust; "yinfft" = faster; "schmitt" = another option
# ) -> tuple[float | None, str | None, int | None]:
#     """
#     Detect dominant pitch from an audio file.

#     Returns:
#         (frequency_hz, note_name, octave) or (None, None, None) if no clear pitch.
#     """
#     src = aubio.source(path, sample_rate, hop_size)
#     # 4096 = window size (samples we look at at once). Bigger = more frequency resolution.
#     pitch_detector = aubio.pitch(method, 4096, hop_size, sample_rate)
#     pitch_detector.set_unit("Hz")  # we want frequency in Hz, not MIDI
#     pitch_detector.set_silence(-40)  # below this dB we treat as silence (no pitch)

#     while True:
#         samples, read = src()  # "samples" here = one chunk of the waveform (hop_size numbers)
#         pitch = pitch_detector(samples)
#         if read < hop_size:
#             break

#     freq = float(pitch) if pitch > 0 else None
#     if freq is None:
#         return None, None, None
#     result = freq_to_note_and_octave(freq)
#     if result is None:
#         return freq, None, None
#     note, octave = result
#     return freq, note, octave

# def detect_all_pitches_from_file(
#     path: str,
#     hop_size: int = 512,
#     sample_rate: int = 44100,
#     method: str = "yin",
# ) -> tuple[np.ndarray, np.ndarray]:
#     """
#     Detect pitch at every frame; export as numpy arrays for key-finding etc.

#     Returns:
#         freqs: 1D array of frequency (Hz) per frame; 0.0 where no pitch.
#         pitch_classes: 1D array of pitch class 0-11 (C=0..B=11) per frame; -1 where no pitch.
#     """
#     src = aubio.source(path, sample_rate, hop_size)
#     pitch_detector = aubio.pitch(method, 4096, hop_size, sample_rate)
#     pitch_detector.set_unit("Hz")
#     pitch_detector.set_silence(-40)

#     freqs_list: list[float] = []
#     while True:
#         samples, read = src()
#         pitch = pitch_detector(samples)
#         f = float(pitch) if pitch > 0 else 0.0
#         freqs_list.append(f)
#         if read < hop_size:
#             break

#     freqs = np.array(freqs_list, dtype=np.float32)
#     pitch_classes = np.array([freq_to_pitch_class(f) if f > 0 else -1 for f in freqs_list], dtype=np.int32)
#     return freqs, pitch_classes


def format_pitch(freq: float | None, note: str | None, octave: int | None) -> str:
    """Human-readable pitch string, e.g. 'A4 (440.0 Hz)'."""
    if freq is None:
        return "No pitch detected"
    if note is not None and octave is not None:
        return f"{note}{octave} ({freq:.1f} Hz)"
    return f"{freq:.1f} Hz"


# --- Example usage ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pitch_detection.py <audio_file.wav>")
        print("  Or import and use: detect_pitch_from_file(path) or detect_pitch_from_buffer(samples, sr)")
        sys.exit(0)

    path = sys.argv[1]
    freq, note, octave = detect_pitch_from_buffer(path)
    print(format_pitch(freq, note, octave))