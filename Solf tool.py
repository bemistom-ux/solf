import streamlit as st
import random
import os
import numpy as np
from scipy.io import wavfile
import io
from music21 import stream, note, chord, key, meter, pitch, environment

# --- 1. THE SYSTEM HANDSHAKE ---
# Direct link to your confirmed MuseScore 4 path
env = environment.Environment()
mscore_path = '/Applications/MuseScore 4.app/Contents/MacOS/mscore'

if os.path.exists(mscore_path):
    env['musescoreDirectPNGPath'] = mscore_path
    env['musicxmlPath'] = mscore_path

# --- 2. THE ZOO DEFINITIONS ---
SIMPLE_ZOO = {
    "Bear": [1.0], "Monkey": [0.5, 0.5], "Tiger": [0.75, 0.25],
    "Elephant": [0.25, 0.25, 0.5], "Grasshopper": [0.5, 0.25, 0.25],
    "Alligator": [0.25, 0.25, 0.25, 0.25], "Box Turtle": [0.25, 0.5, 0.25]
}

# --- 3. AUDIO ENGINE ---
def generate_audio(score, bpm=60):
    sample_rate = 44100
    total_audio = np.array([], dtype=np.float32)
    beat_dur = 60.0 / bpm 
    for element in score.recurse():
        if isinstance(element, (note.Note, chord.Chord)):
            freqs = [p.frequency for p in element.pitches] if isinstance(element, chord.Chord) else [element.pitch.frequency]
            dur = element.quarterLength * beat_dur
            t = np.linspace(0, dur, int(sample_rate * dur), False)
            tone = np.zeros_like(t)
            for f in freqs:
                tone += np.sin(2 * np.pi * f * t) + 0.4*np.sin(2*np.pi*2*f*t)*np.exp(-t*5)
            total_audio = np.concatenate([total_audio, tone, np.zeros(int(sample_rate * 0.01))])
    if total_audio.size > 0: total_audio = total_audio / (np.max(np.abs(total_audio)) + 1e-6)
    byte_io = io.BytesIO()
    wavfile.write(byte_io, sample_rate, (total_audio * 32767).astype(np.int16))
    return byte_io.getvalue()

# --- 4. DRILL GENERATOR ---
def generate_unified_drill(u_key, u_mode, u_ts, u_range, u_measures):
    s = stream.Score()
    p = stream.Part()
    k = key.Key(u_key, u_mode)
    p.append(k)
    p.append(meter.TimeSignature(u_ts))
    
    # Octave range setup
    ranges = {"Soprano": "C4", "Alto": "G3", "Tenor": "C3", "Baritone": "G2"}
    tonic_pitch = k.pitchFromDegree(1)
    while tonic_pitch.ps < pitch.Pitch(ranges[u_range]).ps: 
        tonic_pitch = tonic_pitch.transpose(12)
    pitches = k.getScale().getPitches(tonic_pitch, tonic_pitch.transpose(12))

    # Measure 1: Anchor Stinger
    m1 = stream.Measure(number=1)
    stinger = chord.Chord([k.pitchFromDegree(1), k.pitchFromDegree(3), k.pitchFromDegree(5)])
    stinger.duration.quarterLength = 2.0
    m1.append(stinger)
    m1.append(note.Rest(quarterLength=2.0))
    p.append(m1)

    # Drill Measures
    for m_num in range(2, u_measures + 2):
        m = stream.Measure(number=m_num)
        beats_filled = 0
        while beats_filled < 4.0:
            animal = random.choice(list(SIMPLE_ZOO.keys()))
            pattern = SIMPLE_ZOO[animal]
            for dur in pattern:
                n = note.Note(random.choice(pitches), quarterLength=dur)
                # Map Solfege to Lyrics
                deg = k.getScaleDegreeFromPitch(n.pitch)
                solf_map = {1:"Do", 2:"Re", 3:"Mi", 4:"Fa", 5:"Sol", 6:"La", 7:"Ti"}
                n.addLyric(solf_map.get(deg, n.pitch.name))
                m.append(n)
            beats_filled += sum(pattern)
        p.append(m)
    
    s.append(p)
    return s

# --- 5. UI & SESSION STATE ---
st.set_page_config(page_title="SolfMaster v4.21", layout="wide")
st.title("🎼 SolfMaster v4.21")

if 'img_path' not in st.session_state:
    st.session_state['img_path'] = None

with st.sidebar:
    u_key = st.selectbox("Key", ['C', 'G', 'F', 'D', 'Bb', 'Eb', 'A'])
    u_mode = st.radio("Mode", ["major", "minor"])
    u_ts = st.selectbox("Time Signature", ["4/4"])
    u_range = st.selectbox("Range", ["Baritone", "Tenor", "Alto", "Soprano"])
    u_measures = st.number_input("Measures", 1, 8, 2)

# --- 6. EXECUTION BLOCK ---
if st.button("Generate New Drill", type="primary"):
    drill_score = generate_unified_drill(u_key, u_mode, u_ts, u_range, u_measures)
    st.session_state['drill'] = drill_score
    
    try:
        # Prevent caching with unique ID
        img_id = random.randint(1, 9999)
        base_name = f"drill_{img_id}"
        
        # Write file (this triggers MuseScore)
        drill_score.write('musicxml.png', fp=base_name)
        
        # Update session state with the auto-generated filename
        st.session_state['img_path'] = f"{base_name}-1.png"
    except Exception as e:
        st.error(f"Render Error: {e}")
        st.session_state['img_path'] = None

# --- 7. DISPLAY RESULTS ---
if st.session_state['img_path'] and os.path.exists(st.session_state['img_path']):
    st.divider()
    # Audio
    st.audio(generate_audio(st.session_state['drill']))
    # Image
    st.image(st.session_state['img_path'])
    
    # Cleanup old PNGs to keep folder tidy
    for f in os.listdir():
        if f.endswith(".png") and f != st.session_state['img_path']:
            try: os.remove(f)
            except: pass
