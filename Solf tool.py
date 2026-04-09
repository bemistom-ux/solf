import streamlit as st
import random
import numpy as np
from scipy.io import wavfile
import io
import os
from music21 import stream, note, chord, key, meter, pitch, environment

# --- 0. MUSESCORE CONFIG ---
try:
    env = environment.Environment()
    paths = ['/Applications/MuseScore 4.app/Contents/MacOS/mscore', '/Applications/MuseScore 3.app/Contents/MacOS/mscore']
    for p in paths:
        if os.path.exists(p):
            env['musescoreDirectPNGPath'] = p
            break
except:
    pass

# --- 1. AUDIO ENGINE (E-Piano / Organ / Sine) ---
def generate_audio_buffer(score, bpm=70, timbre="E-Piano"):
    sample_rate = 44100
    total_audio = np.array([], dtype=np.float32)
    quarter_duration = 60.0 / bpm 

    for element in score.recurse():
        if isinstance(element, (note.Note, chord.Chord)):
            freqs = [p.frequency for p in element.pitches] if isinstance(element, chord.Chord) else [element.pitch.frequency]
            duration = element.quarterLength * quarter_duration
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            tone = np.zeros_like(t)

            for f in freqs:
                if timbre == "E-Piano":
                    # Fundamental + decaying harmonics for a bell-like strike
                    tone += np.sin(2 * np.pi * f * t) 
                    tone += 0.4 * np.sin(2 * np.pi * 2.01 * f * t) * np.exp(-t*4)
                    tone += 0.15 * np.sin(2 * np.pi * 3.99 * f * t) * np.exp(-t*8)
                elif timbre == "Organ":
                    tone += np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t)
                else: # Sine
                    tone += np.sin(2 * np.pi * f * t)

            tone = (tone / (len(freqs) if isinstance(element, chord.Chord) else 1)) * 0.6
            window = np.ones_like(tone)
            fade = int(sample_rate * 0.02)
            if len(tone) > fade * 2:
                window[:fade] = np.linspace(0, 1, fade)
                window[-fade:] = np.linspace(1, 0, fade)
            
            total_audio = np.concatenate([total_audio, tone * window, np.zeros(int(sample_rate * 0.02))])

    if total_audio.size > 0:
        total_audio = total_audio / (np.max(np.abs(total_audio)) + 1e-6)
    
    audio_int16 = (total_audio * 32767).astype(np.int16)
    byte_io = io.BytesIO()
    wavfile.write(byte_io, sample_rate, audio_int16)
    return byte_io.getvalue()

# --- 2. SOLFÈGE MAPPING LOGIC ---
def get_solfege_name(degree, mode):
    # Major Scale Syllables
    maj = {1:'Do', 2:'Re', 3:'Mi', 4:'Fa', 5:'Sol', 6:'La', 7:'Ti', 8:'Do'}
    # Minor Scale Syllables (Do-based)
    min_scale = {1:'Do', 2:'Re', 3:'Me', 4:'Fa', 5:'Sol', 6:'Le', 7:'Te', 8:'Do'}
    
    if mode == 'minor':
        return min_scale.get(degree, "??")
    return maj.get(degree, "??")

# --- 3. DRILL LOGIC ---
def generate_unified_drill(k_name, mode, ts_str, v_range, leap, rhythm_list, show_labels):
    s = stream.Score()
    p = stream.Part()
    k = key.Key(k_name, mode)
    p.append(k)
    p.append(meter.TimeSignature(ts_str))
    
    ranges = {"Soprano": "C4", "Alto": "G3", "Tenor": "C3", "Baritone": "G2"}
    base = pitch.Pitch(ranges[v_range])
    tonic = k.pitchFromDegree(1)
    while tonic.ps < base.ps: tonic = tonic.transpose(12)
    
    scale_pitches = k.getScale().getPitches(tonic, tonic.transpose(12))
    
    # 1. ANCHOR CHORD
    anchor = chord.Chord([k.pitchFromDegree(1), k.pitchFromDegree(3), k.pitchFromDegree(5)], 
                         quarterLength=4.0 if ts_str=="4/4" else 3.0)
    anchor.addLyric("Anchor")
    p.append(anchor)

    # 2. 4 MEASURES OF MELODY
    curr_deg = 1
    beats_per_measure = 4.0 if ts_str == "4/4" else 3.0 
    
    for _ in range(4):
        beats = 0
        while beats < beats_per_measure:
            pattern = random.choice(rhythm_list)
            if beats + sum(pattern) <= beats_per_measure:
                for d in pattern:
                    curr_deg = max(1, min(8, curr_deg + random.randint(-leap, leap)))
                    n = note.Note(scale_pitches[curr_deg-1], quarterLength=d)
                    if show_labels:
                        deg_num = k.getScaleDegreeAndAccidentalFromPitch(n.pitch)[0]
                        n.addLyric(get_solfege_name(deg_num, mode))
                    p.append(n)
                beats += sum(pattern)
            else:
                rem = beats_per_measure - beats
                p.append(note.Note(scale_pitches[curr_deg-1], quarterLength=rem))
                break
    s.append(p)
    return s

# --- 4. UI ---
st.set_page_config(page_title="Solfège Lab v3.1", layout="wide")
st.title("🎹 Advanced Solfège & Dictation Lab")

with st.sidebar:
    st.header("1. Musical Setup")
    u_ts = st.selectbox("Meter", ["4/4", "6/8"])
    u_key = st.selectbox("Key", ['C', 'G', 'F', 'D', 'Bb', 'Eb', 'A'])
    u_mode = st.radio("Mode", ["major", "minor"])
    u_range = st.selectbox("Vocal Range", ["Baritone", "Tenor", "Alto", "Soprano"])
    u_bpm = st.slider("BPM", 40, 120, 60)
    u_leap = st.slider("Leap Complexity", 1, 3, 1)
    u_timbre = st.selectbox("Instrument Sound", ["E-Piano", "Organ", "Sine"])
    u_labels = st.checkbox("Show Solfège Syllables", value=True)
    
    st.header("2. Rhythms")
    if u_ts == "4/4":
        r_opts = {"Monkey (1/4)": [1.0], "Elephant (2/8)": [0.5, 0.5], "Alligator (4/16)": [0.25]*4}
    else: # 6/8
        r_opts = {"Dotted Quarter": [1.5], "Wombat (3/8s)": [0.5]*3, "Humpty (Quarter-8th)": [1.0, 0.5]}
    
    active_rhythms = [r_opts[r] for r in r_opts if st.checkbox(r, value=True)]

if st.button("Generate New Drill", type="primary"):
    st.session_state['drill'] = generate_unified_drill(u_key, u_mode, u_ts, u_range, u_leap, active_rhythms, u_labels)
    try:
        img_id = random.randint(1, 9999)
        st.session_state['drill'].write('musicxml.png', fp=f"drill_{img_id}")
        st.session_state['img_path'] = f"drill_{img_id}-1.png"
    except:
        st.session_state['img_path'] = None

if 'drill' in st.session_state:
    st.divider()
    
    st.subheader("1. Listen to the Melody")
    audio = generate_audio_buffer(st.session_state['drill'], bpm=u_bpm, timbre=u_timbre)
    st.audio(audio, format="audio/wav")
    
    st.subheader("2. Score Display")
    reveal = st.checkbox("Reveal Score (Dictation Mode)", value=True)
    
    if reveal:
        if st.session_state['img_path'] and os.path.exists(st.session_state['img_path']):
            st.image(st.session_state['img_path'])
        else:
            st.warning("Ensure MuseScore is installed. Showing notes as text:")
            notes = [f"{n.lyric or n.name}" for n in st.session_state['drill'].recurse().notes]
            st.code(" | ".join(notes))
