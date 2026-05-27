import streamlit as st
import random
import numpy as np
from scipy.io import wavfile
import io
import os
from music21 import stream, note, chord, key, meter, pitch, environment, duration

# --- 0. SYSTEM CONFIG ---
try:
    env = environment.Environment()
    mscore_path = '/Applications/MuseScore 4.app/Contents/MacOS/mscore'
    if os.path.exists(mscore_path):
        env['musescoreDirectPNGPath'] = mscore_path
except:
    pass

# --- 1. THE ATOMIC ZOO (Rhythmic Cells) ---
# Simple Time (4/4) - Each cell is 1.0 beat
SIMPLE_ZOO = {
    "Bear": [1.0],
    "Monkey": [0.5, 0.5],
    "Tiger": [0.75, 0.25],
    "Elephant": [0.25, 0.25, 0.5],
    "Grasshopper": [0.5, 0.25, 0.25],
    "Alligator": [0.25, 0.25, 0.25, 0.25],
    "Box Turtle": [0.25, 0.5, 0.25],
    "Trip-o-let": "TRIPLET" # Handled via Tuplet logic
}

# Compound Time (6/8) - Each cell is 1.5 beats (one pulse)
COMPOUND_ZOO = {
    "Bear": [1.5],
    "Wallaby": [0.5, 0.5, 0.5],
    "Lemur": [1.0, 0.5],
    "Wombat": [0.5, 1.0],
    "Mastodon": [0.75, 0.25, 0.5],
    "Kingfisher": [1.0, 0.25, 0.25],
    "Kookaburra": [0.75, 0.25, 0.25, 0.25],
    "Purple Alligator": [0.25] * 6,
    "Yellow Elephant": [0.25, 0.25, 0.25, 0.25, 0.5],
    "Green Alligator": [0.5, 0.25, 0.25, 0.25, 0.25],
    "Du-plet": "DUPLET" # Handled via Tuplet logic
}

# --- 2. AUDIO ENGINE ---
def generate_audio_v45(score, bpm=60, timbre="E-Piano"):
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
                if timbre == "Percussion":
                    tone += np.sin(2 * np.pi * 1400 * t) * np.exp(-t*80)
                elif timbre == "E-Piano":
                    tone += np.sin(2 * np.pi * f * t) + 0.4*np.sin(2*np.pi*2*f*t)*np.exp(-t*5)
                else: # Organ
                    tone += np.sin(2 * np.pi * f * t) + 0.5*np.sin(2*np.pi*2*f*t)
            tone = (tone / (len(freqs) if isinstance(element, chord.Chord) else 1)) * 0.7
            total_audio = np.concatenate([total_audio, tone, np.zeros(int(sample_rate * 0.01))])
        elif isinstance(element, note.Rest):
            total_audio = np.concatenate([total_audio, np.zeros(int(sample_rate * element.quarterLength * beat_dur))])

    if total_audio.size > 0:
        total_audio = total_audio / (np.max(np.abs(total_audio)) + 1e-6)
    byte_io = io.BytesIO()
    wavfile.write(byte_io, sample_rate, (total_audio * 32767).astype(np.int16))
    return byte_io.getvalue()

# --- 3. DRILL BUILDING LOGIC ---
def build_zoo_drill(u_meter, u_key, u_mode, u_range, u_animals, u_measures):
    s = stream.Score()
    p = stream.Part()
    k = key.Key(u_key, u_mode)
    p.append(k)
    ts = meter.TimeSignature(u_meter)
    p.append(ts)

    # Range Setup (Baritone Focus)
    ranges = {"Soprano": "C4", "Alto": "G3", "Tenor": "C3", "Baritone": "G2"}
    tonic_pitch = k.pitchFromDegree(1)
    while tonic_pitch.ps < pitch.Pitch(ranges[u_range]).ps:
        tonic_pitch = tonic_pitch.transpose(12)
    pitches = k.getScale().getPitches(tonic_pitch, tonic_pitch.transpose(12))

    # --- MEASURE 1: THE ANCHOR ---
    anchor_m = stream.Measure(number=1)
    anchor_m.append(meter.TimeSignature(u_meter))
    stinger = chord.Chord([k.pitchFromDegree(1), k.pitchFromDegree(3), k.pitchFromDegree(5)])
    if u_meter == '4/4':
        stinger.duration.quarterLength = 2.0 # Half note
        anchor_m.append(stinger)
        anchor_m.append(note.Rest(quarterLength=2.0))
    else: # 6/8
        stinger.duration.quarterLength = 1.5 # Dotted quarter
        anchor_m.append(stinger)
        anchor_m.append(note.Rest(quarterLength=1.5))
    p.append(anchor_m)

    # --- MEASURES 2+: THE DRILL ---
    zoo = SIMPLE_ZOO if u_meter == '4/4' else COMPOUND_ZOO
    current_deg = 1

    for m_num in range(2, u_measures + 2):
        m = stream.Measure(number=m_num)
        beats_needed = 4.0 if u_meter == '4/4' else 3.0 # music21 treats 6/8 measure as 3.0 quarterLengths
        beats_filled = 0
        
        while beats_filled < beats_needed:
            choice = random.choice(u_animals)
            pattern = zoo[choice]
            
            # Handle Tuplets on the fly
            if pattern == "TRIPLET":
                t_notes = []
                for _ in range(3):
                    current_deg = max(1, min(8, current_deg + random.randint(-1, 1)))
                    n = note.Note(pitches[current_deg-1], type='eighth')
                    t_notes.append(n)
                t_group = stream.Voice()
                t_group.append(t_notes)
                t_group.notes[0].expressions.append(note.Note()) # Placeholder for tuplet visual
                # music21 triplet math
                for n in t_notes:
                    n.duration.appendTuplet(duration.Tuplet(3, 2))
                m.append(t_notes)
                beats_filled += 1.0
            elif pattern == "DUPLET":
                d_notes = []
                for _ in range(2):
                    current_deg = max(1, min(8, current_deg + random.randint(-1, 1)))
                    n = note.Note(pitches[current_deg-1], type='quarter')
                    d_notes.append(n)
                for n in d_notes:
                    n.duration.appendTuplet(duration.Tuplet(2, 3))
                m.append(d_notes)
                beats_filled += 1.5
            else:
                # Standard pattern
                for dur in pattern:
                    current_deg = max(1, min(8, current_deg + random.randint(-1, 1)))
                    n = note.Note(pitches[current_deg-1], quarterLength=dur)
                    m.append(n)
                beats_filled += sum(pattern)
        p.append(m)
    
    s.append(p)
    return s

# --- 4. STREAMLIT INTERFACE ---
st.set_page_config(page_title="SolfMaster v4.5", layout="wide")
st.title("🎼 SolfMaster v4.5: The Zoo Master")

with st.sidebar:
    st.header("1. Meter & Key")
    u_meter = st.radio("Time Signature", ['4/4', '6/8'])
    u_key = st.selectbox("Key", ['C', 'G', 'F', 'D', 'Bb', 'Eb', 'A'])
    u_mode = st.radio("Mode", ["major", "minor"])
    
    st.divider()
    st.header("2. A La Carte Zoo")
    available_animals = list(SIMPLE_ZOO.keys()) if u_meter == '4/4' else list(COMPOUND_ZOO.keys())
    u_animals = st.multiselect("Pick your Animals to drill:", available_animals, default=available_animals[:3])
    
    if st.button("Randomize My Zoo"):
        u_animals = available_animals
        
    st.divider()
    st.header("3. Voice & Sound")
    u_range = st.selectbox("Vocal Range", ["Baritone", "Tenor", "Alto", "Soprano"])
    u_bpm = st.slider("Tempo (BPM)", 40, 120, 60)
    u_timbre = st.selectbox("Instrument", ["E-Piano", "Percussion", "Organ"])
    u_measures = st.number_input("Drill Measures", 1, 8, 4)
    u_dictation = st.checkbox("Dictation Mode (Hide Score)")

if not u_animals:
    st.warning("Please select at least one animal from the menu to start.")
else:
    if st.button("Generate Training Drill", type="primary"):
        st.session_state['score'] = build_zoo_drill(u_meter, u_key, u_mode, u_range, u_animals, u_measures)
        st.session_state['audio'] = generate_audio_v45(st.session_state['score'], u_bpm, u_timbre)
        try:
            fn = f"zoo_out_{random.randint(1,999)}"
            st.session_state['score'].write('musicxml.png', fp=fn)
            st.session_state['img'] = f"{fn}-1.png"
        except: st.session_state['img'] = None

if 'score' in st.session_state:
    st.divider()
    st.audio(st.session_state['audio'])
    if u_dictation:
        if st.checkbox("Reveal Answer"):
            if st.session_state.get('img') and os.path.exists(st.session_state['img']):
                st.image(st.session_state['img'])
    else:
        if st.session_state.get('img') and os.path.exists(st.session_state['img']):
            st.image(st.session_state['img'])
