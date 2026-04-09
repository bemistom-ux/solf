import streamlit as st
import random
import numpy as np
from scipy.io import wavfile
import io
import os
from music21 import stream, note, chord, key, meter, pitch, environment

# --- 0. SYSTEM CONFIG ---
try:
    env = environment.Environment()
    mscore_path = '/Applications/MuseScore 4.app/Contents/MacOS/mscore'
    if os.path.exists(mscore_path):
        env['musescoreDirectPNGPath'] = mscore_path
except:
    pass

# --- 1. DATA & LEVELS ---
LEVELS = {
    1: {"name": "The Pulse", "desc": "Quarter Notes only (The Monkey).", "pool": [[1.0]]},
    2: {"name": "The Breath", "desc": "Adds Quarter Rests (The Silent Monkey).", "pool": [[1.0], ['R', 1.0]]},
    3: {"name": "Division", "desc": "Adds Eighth Notes (The Elephant).", "pool": [[1.0], ['R', 1.0], [0.5, 0.5]]},
    4: {"name": "The Gap", "desc": "Eighths following Rests.", "pool": [[1.0], ['R', 1.0], [0.5, 0.5], ['R', 1.0, 0.5, 0.5]]},
    5: {"name": "The Dot", "desc": "Dotted Quarters (The Tiger).", "pool": [[1.0], [0.5, 0.5], [1.5, 0.5]]},
    6: {"name": "Sub-Division", "desc": "Sixteenths (The Alligator).", "pool": [[1.0], [0.5, 0.5], [0.25, 0.25, 0.25, 0.25]]},
    7: {"name": "Syncopation", "desc": "Tied notes and 'Box Turtles'.", "pool": [[1.0], [0.5, 1.0, 0.5], [0.5, 0.25, 0.25]]},
    8: {"name": "Compound", "desc": "6/8 Time (Wombats & Humptys).", "pool": [[1.5], [0.5, 0.5, 0.5], [1.0, 0.5]]}
}

# --- 2. AUDIO ENGINE ---
def generate_audio_v4(score, bpm=60, timbre="E-Piano"):
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
def build_drill(level, mode, u_key, u_range, u_hide_labels):
    is_68 = (level == 8)
    ts_str = '6/8' if is_68 else '4/4'
    s = stream.Score()
    p = stream.Part()
    k = key.Key(u_key, mode)
    p.append(k)
    p.append(meter.TimeSignature(ts_str))

    ranges = {"Soprano": "C4", "Alto": "G3", "Tenor": "C3", "Baritone": "G2"}
    tonic_pitch = k.pitchFromDegree(1)
    while tonic_pitch.ps < pitch.Pitch(ranges[u_range]).ps:
        tonic_pitch = tonic_pitch.transpose(12)
    pitches = k.getScale().getPitches(tonic_pitch, tonic_pitch.transpose(12))

    s_map = {1:'Do', 2:'Re', 3:'Mi', 4:'Fa', 5:'Sol', 6:'La', 7:'Ti', 8:'Do'}
    if mode == 'minor':
        s_map[3], s_map[6], s_map[7] = 'Me', 'Le', 'Te'

    # Stinger
    stinger = chord.Chord([k.pitchFromDegree(1), k.pitchFromDegree(3), k.pitchFromDegree(5)], quarterLength=1.0)
    p.append(stinger)
    p.append(note.Rest(quarterLength=1.0))

    pool = LEVELS[level]["pool"]
    num_meas = st.session_state.get('meas_count', 4)
    limit = 3.0 if is_68 else 4.0
    
    for _ in range(num_meas):
        m_beats = 0
        while m_beats < limit:
            cell = random.choice(pool)
            dur_sum = sum([item if isinstance(item, (float, int)) else 1.0 for item in cell])
            if m_beats + dur_sum <= limit:
                for val in cell:
                    if val == 'R': p.append(note.Rest(quarterLength=1.0))
                    else:
                        if st.session_state.get('is_rhythm_only'): n = note.Note("B4", quarterLength=val)
                        else:
                            curr_deg = random.randint(1, 8)
                            n = note.Note(pitches[curr_deg-1], quarterLength=val)
                            if not u_hide_labels: n.addLyric(s_map[curr_deg])
                        p.append(n)
                m_beats += dur_sum
            else:
                p.append(note.Rest(quarterLength=(limit - m_beats)))
                break
    s.append(p)
    return s

# --- 4. USER INTERFACE ---
st.set_page_config(page_title="SolfMaster v4.3", layout="wide")
st.title("🎼 SolfMaster v4.3")

with st.sidebar:
    st.header("Settings")
    u_level = st.slider("Skill Level", 1, 8, 1)
    st.info(LEVELS[u_level]['desc'])
    u_focus = st.radio("Focus", ["Melodic + Rhythm", "Rhythm Only"])
    st.session_state['is_rhythm_only'] = (u_focus == "Rhythm Only")
    st.session_state['meas_count'] = st.selectbox("Length", [1, 2, 4], index=2)
    u_key = st.selectbox("Key", ['C', 'G', 'F', 'D', 'Bb', 'Eb', 'A'])
    u_mode = st.radio("Mode", ["major", "minor"])
    u_range = st.selectbox("Vocal Range", ["Baritone", "Tenor", "Alto", "Soprano"])
    u_bpm = st.slider("BPM", 40, 120, 65)
    u_timbre = st.selectbox("Sound", ["E-Piano", "Percussion", "Organ"])
    u_labels = st.checkbox("Show Labels", value=True)
    u_dictation = st.checkbox("Dictation (Hide Score)")

if st.button("Generate Training Drill", type="primary"):
    st.session_state['score'] = build_drill(u_level, u_mode, u_key, u_range, not u_labels)
    st.session_state['audio'] = generate_audio_v4(st.session_state['score'], u_bpm, u_timbre)
    try:
        fn = f"dr_{random.randint(1,999)}"
        st.session_state['score'].write('musicxml.png', fp=fn)
        st.session_state['img'] = f"{fn}-1.png"
    except: st.session_state['img'] = None

if 'score' in st.session_state:
    st.audio(st.session_state['audio'])
    if not u_dictation or st.checkbox("Reveal Answer"):
        if st.session_state.get('img') and os.path.exists(st.session_state['img']):
            st.image(st.session_state['img'])
        else:
            st.warning("Score image failed. Try installing MuseScore 4.")
