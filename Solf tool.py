import streamlit as st
import streamlit.components.v1 as components
import random
import numpy as np
from scipy.io import wavfile
import io
from music21 import stream, note, chord, key, meter, pitch, duration

# --- 1. THE ZOO DEFINITIONS (UNCHANGED) ---
SIMPLE_ZOO = {
    "Bear": [1.0], "Monkey": [0.5, 0.5], "Tiger": [0.75, 0.25],
    "Elephant": [0.25, 0.25, 0.5], "Grasshopper": [0.5, 0.25, 0.25],
    "Alligator": [0.25, 0.25, 0.25, 0.25], "Box Turtle": [0.25, 0.5, 0.25],
    "Trip-o-let": "TRIPLET"
}

COMPOUND_ZOO = {
    "Bear": [1.5], "Wallaby": [0.5, 0.5, 0.5], "Lemur": [1.0, 0.5],
    "Wombat": [0.5, 1.0], "Mastodon": [0.75, 0.25, 0.5],
    "Kingfisher": [1.0, 0.25, 0.25], "Kookaburra": [0.75, 0.25, 0.25, 0.25],
    "Purple Alligator": [0.25]*6, "Yellow Elephant": [0.25,0.25,0.25,0.25,0.5],
    "Green Alligator": [0.5,0.25,0.25,0.25,0.25], "Du-plet": "DUPLET"
}

# --- 2. AUDIO ENGINE (UNCHANGED) ---
def generate_audio_v410(score, bpm=60, timbre="E-Piano"):
    sample_rate = 44100; total_audio = np.array([], dtype=np.float32); beat_dur = 60.0 / bpm 
    for element in score.recurse():
        if isinstance(element, (note.Note, chord.Chord)):
            freqs = [p.frequency for p in element.pitches] if isinstance(element, chord.Chord) else [element.pitch.frequency]
            dur = element.quarterLength * beat_dur; t = np.linspace(0, dur, int(sample_rate * dur), False); tone = np.zeros_like(t)
            for f in freqs:
                if timbre == "E-Piano": tone += np.sin(2 * np.pi * f * t) + 0.4*np.sin(2*np.pi*2*f*t)*np.exp(-t*5)
                elif timbre == "Percussion": tone += np.sin(2 * np.pi * 1400 * t) * np.exp(-t*80)
                else: tone += np.sin(2 * np.pi * f * t) + 0.5*np.sin(2*np.pi*2*f*t)
            total_audio = np.concatenate([total_audio, tone, np.zeros(int(sample_rate * 0.01))])
        elif isinstance(element, note.Rest):
            total_audio = np.concatenate([total_audio, np.zeros(int(sample_rate * element.quarterLength * beat_dur))])
    if total_audio.size > 0: total_audio = total_audio / (np.max(np.abs(total_audio)) + 1e-6)
    byte_io = io.BytesIO(); wavfile.write(byte_io, sample_rate, (total_audio * 32767).astype(np.int16)); return byte_io.getvalue()

# --- 3. DRILL BUILDER (UNCHANGED) ---
def build_zoo_drill_v410(u_meter, u_key, u_mode, u_range, u_animals, u_measures):
    s = stream.Score(); p = stream.Part(); k = key.Key(u_key, u_mode); p.append(k); p.append(meter.TimeSignature(u_meter))
    animal_history = []; ranges = {"Soprano": "C4", "Alto": "G3", "Tenor": "C3", "Baritone": "G2"}
    tonic_pitch = k.pitchFromDegree(1)
    while tonic_pitch.ps < pitch.Pitch(ranges[u_range]).ps: tonic_pitch = tonic_pitch.transpose(12)
    pitches = k.getScale().getPitches(tonic_pitch, tonic_pitch.transpose(12))
    anchor_m = stream.Measure(number=1); stinger = chord.Chord([k.pitchFromDegree(1), k.pitchFromDegree(3), k.pitchFromDegree(5)])
    stinger.duration.quarterLength = 2.0 if u_meter == '4/4' else 1.5; anchor_m.append(stinger); anchor_m.append(note.Rest(quarterLength=stinger.duration.quarterLength)); p.append(anchor_m)
    zoo = SIMPLE_ZOO if u_meter == '4/4' else COMPOUND_ZOO
    for m_num in range(2, u_measures + 2):
        m = stream.Measure(number=m_num); beats_needed = 4.0 if u_meter == '4/4' else 3.0; beats_filled = 0; measure_animals = []
        while beats_filled < beats_needed:
            choice = random.choice(u_animals); measure_animals.append(choice); pattern = zoo[choice]
            if pattern == "TRIPLET":
                t_notes = [note.Note(random.choice(pitches), type='eighth') for _ in range(3)]
                for n in t_notes: n.duration.appendTuplet(duration.Tuplet(3, 2))
                m.append(t_notes); beats_filled += 1.0
            elif pattern == "DUPLET":
                d_notes = [note.Note(random.choice(pitches), type='quarter') for _ in range(2)]
                for n in d_notes: n.duration.appendTuplet(duration.Tuplet(2, 3))
                m.append(d_notes); beats_filled += 1.5
            else:
                for dur in pattern: 
                    new_note = note.Note(random.choice(pitches), quarterLength=dur)
                    new_note.lyric = new_note.pitch.german.replace('is','').replace('es','') # Rough Solfege
                    m.append(new_note)
                beats_filled += sum(pattern)
        p.append(m); animal_history.append(f"Measure {m_num}: " + ", ".join(measure_animals))
    s.append(p); return s, animal_history

# --- 4. THE WEB-STAFF RENDERER (VEXFLOW + SOLFEGE) ---
def render_vexflow_v410(score, meter_val, measures_count):
    vex_notes = []
    for p in score.parts:
        for m in p.getElementsByClass('Measure'):
            if m.number == 1: continue 
            for n in m.notesAndRests:
                p_name = f"{n.pitch.name.lower()}/{n.pitch.octave}" if n.isNote else "b/4"
                dur = "q" if n.quarterLength == 1.0 else "8" if n.quarterLength == 0.5 else "16" if n.quarterLength == 0.25 else "h"
                type_suffix = "r" if n.isRest else ""
                lyric = f".addAnnotation(0, new Annotation('{n.pitch.name}').setVerticalJustification(Annotation.VerticalJustify.BOTTOM))" if n.isNote else ""
                vex_notes.append(f"new StaveNote({{keys: ['{p_name}'], duration: '{dur}{type_suffix}' }}){lyric}")

    notes_js = ",\n            ".join(vex_notes)
    beats_per_measure = 4 if meter_val == '4/4' else 3
    
    vex_html = f"""
    <div id="boo" style="background: white; padding: 20px; border-radius: 10px;"></div>
    <script src="https://cdn.jsdelivr.net/npm/vexflow@4.2.2/build/cjs/vexflow.js"></script>
    <script>
        const {{ Renderer, Stave, StaveNote, Voice, Formatter, Annotation }} = Vex.Flow;
        const div = document.getElementById("boo");
        const renderer = new Renderer(div, Renderer.Backends.SVG);
        renderer.resize(800, 200);
        const context = renderer.getContext();
        const stave = new Stave(10, 40, 750);
        stave.addClef("treble").addTimeSignature("{meter_val}");
        stave.setContext(context).draw();
        const notes = [{notes_js}];
        const voice = new Voice({{num_beats: {measures_count} * {beats_per_measure}, beat_value: 4}});
        voice.addTickables(notes);
        new Formatter().joinVoices([voice]).format([voice], 700);
        voice.draw(context, stave);
    </script>
    """
    components.html(vex_html, height=280)

# --- 5. APP UI ---
st.set_page_config(page_title="SolfMaster v4.10")
st.title("🎼 SolfMaster v4.10")

with st.sidebar:
    u_meter = st.radio("Meter", ['4/4', '6/8'])
    u_key = st.selectbox("Key", ['C', 'G', 'F', 'D', 'Bb', 'Eb', 'A'])
    u_mode = st.radio("Mode", ["major", "minor"])
    available = list(SIMPLE_ZOO.keys()) if u_meter == '4/4' else list(COMPOUND_ZOO.keys())
    # RESTORED LABEL:
    u_all = st.checkbox("Randomize All Animals", value=True)
    u_animals = available if u_all else st.multiselect("Select Zoo Animals:", available, default=available[:2])
    u_range = st.selectbox("Range", ["Baritone", "Tenor", "Alto", "Soprano"])
    u_bpm = st.slider("BPM", 40, 120, 60); u_timbre = st.selectbox("Sound", ["E-Piano", "Percussion", "Organ"])
    u_measures = st.number_input("Measures", 1, 8, 2)
    # DICTATION MODE:
    u_dictation = st.checkbox("Dictation Mode (Hide Answer)", value=False)

if st.button("Generate New Drill"):
    current_pool = u_animals if u_animals else available[:1]
    st.session_state['score'], st.session_state['history'] = build_zoo_drill_v410(u_meter, u_key, u_mode, u_range, current_pool, u_measures)

if 'score' in st.session_state:
    st.divider()
    st.audio(generate_audio_v410(st.session_state['score'], u_bpm, u_timbre))
    
    # REVEAL LOGIC:
    if not u_dictation or st.checkbox("Reveal Answer"):
        st.subheader("Results")
        render_vexflow_v410(st.session_state['score'], u_meter, u_measures)
        for line in st.session_state['history']: 
            st.write(f"**{line}**")
