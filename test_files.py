"""This is a file that is gonna test all of my functions"""

import numpy as np
import pretty_midi
import os
from pitch_detection import detect_all_pitches_from_buffer
from create_melody import create_melody, find_key

def generate_sine_wave(freq, duration, sample_rate=16000):
    """Generates a pure sine wave for a specific frequency."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Ensure it's float32 for aubio
    return 0.5 * np.sin(2 * np.pi * freq * t).astype(np.float32)

def test_full_pipeline():
    print("--- Starting System Integration Test ---")
    sr = 8000
    hop_size = 512
    
    # 1. Create a synthetic "Hum" in C Major (C4, E4, G4)
    # C4 approx 261.63 Hz, E4 approx 329.63 Hz, G4 approx 392.00 Hz
    print("[1/4] Generating synthetic audio buffer (C - E - G)...")
    c_note = generate_sine_wave(261.63, 0.5, sr)
    e_note = generate_sine_wave(329.63, 0.5, sr)
    g_note = generate_sine_wave(392.00, 0.5, sr)
    silence = np.zeros(int(sr * 0.2), dtype=np.float32) # Gap between notes
    
    audio_buffer = np.concatenate([c_note, silence, e_note, silence, g_note])

    # 2. Test Pitch Detection
    print("[2/4] Testing pitch_detection.py...")
    freqs, pitch_classes = detect_all_pitches_from_buffer(audio_buffer, sample_rate=sr, hop_size=hop_size)
    
    unique_pcs = np.unique(pitch_classes[pitch_classes >= 0])
    print(f"Detected Pitch Classes: {unique_pcs} (Expected [0, 4, 7])")
    
    # 3. Test Key Detection
    print("[3/4] Testing key detection in create_melody.py...")
    detected_key = find_key(pitch_classes)
    print(f"Detected Key: {detected_key} (Expected C)")
    
    # 4. Test MIDI Generation
    print("[4/4] Generating MIDI file...")
    output_file = "test_output.mid"
    pm = create_melody(
        pitch_classes, 
        output_path=output_file, 
        sample_rate=sr, 
        hop_size=hop_size
    )
    
    if os.path.exists(output_file):
        print(f"SUCCESS: MIDI file '{output_file}' created.")
        print(f"Note count in MIDI: {len(pm.instruments[0].notes)}")
    else:
        print("FAILED: MIDI file was not generated.")

if __name__ == "__main__":
    try:
        test_full_pipeline()
    except Exception as e:
        print(f"ERROR during testing: {e}")