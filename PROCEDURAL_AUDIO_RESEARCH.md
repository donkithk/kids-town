# Procedural Audio for Children's Games — Web Audio API Research

## Overview

This document consolidates research on procedural audio generation using the Web Audio API for "Kids Town" — a PWA children's app. All sounds are generated at runtime with oscillators, noise buffers, and gain envelopes — **zero audio files loaded**.

## 1. Web Audio API Architecture

### Core Concepts

| Component | Purpose | Details |
|-----------|---------|---------|
| `AudioContext` | Audio processing graph container | One per app, ~50KB memory, ~2ms creation time |
| `OscillatorNode` | Waveform generator | 5 types: sine, square, sawtooth, triangle, custom |
| `GainNode` | Volume/amplitude control | Used for ADSR envelopes |
| `BiquadFilterNode` | Frequency filtering | Lowpass/highpass/bandpass for ambient effects |
| `AudioBufferSourceNode` | Playback of pre-generated buffers | Used for noise bursts, looped ambience |
| `AudioParam` | Automatable parameter | `setValueAtTime()`, `linearRampToValueAtTime()`, `exponentialRampToValueAtTime()` |

### AudioParam Scheduling Methods

```javascript
// Immediate set
param.setValueAtTime(value, startTime);

// Linear transition
param.linearRampToValueAtTime(value, endTime);

// Exponential decay (good for volume fade-outs)
param.exponentialRampToValueAtTime(value, endTime);

// Cancel future events
param.cancelScheduledValues(startTime);
```

**Critical**: Use `exponentialRampToValueAtTime` for gain (volume) fade-outs — never target `0` (causes error), always target `0.0001`.

## 2. AudioContext Lifecycle & Mobile Restrictions

### iOS Safari / Mobile Chrome Autoplay Policy

| Behavior | iOS Safari | Android Chrome |
|----------|-----------|---------------|
| Context starts as | `suspended` | `suspended` (sometimes `running`) |
| First user gesture required | Yes (click/touch/keydown) | Yes (recommended) |
| Resume on visibility change | Auto-resumes (iOS 15+) | Auto-resumes |
| Multiple resume calls | Safe (no-op if already running) | Safe |
| Context close on tab close | Automatic | Automatic |

### Best Practice Pattern

```javascript
// NEVER create AudioContext on page load
// ALWAYS create inside user gesture handler
function initAudio() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const ctx = new AudioCtx();
  
  // Resume if suspended (critical for iOS)
  if (ctx.state === 'suspended') {
    ctx.resume();
  }
}

// Resume on EVERY subsequent gesture (belt-and-suspenders)
function ensureResume() {
  if (ctx && ctx.state === 'suspended') {
    ctx.resume();
  }
}

// Handle visibility changes
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && ctx?.state === 'suspended') {
    ctx.resume();
  }
});
```

### iOS-Specific Notes

- **Old iOS Safari (pre-15)**: Context stayed suspended until explicit user gesture. The `resume()` promise must be called from within a user gesture event handler (click, touchstart).
- **New iOS Safari (15+)**: Same restrictions but slightly more permissive. Still requires gesture for first play.
- **iPadOS**: Same rules as iOS.
- **Background tabs**: iOS may suspend AudioContext when tab is backgrounded. Use `visibilitychange` listener.
- **Volume limits**: iOS applies per-app volume limits. Web Audio obeys system volume.

## 3. Oscillator Sound Design Techniques

### Waveform Characteristics

| Type | Sound Quality | Best For |
|------|-------------|----------|
| `sine` | Pure, smooth, gentle | Melodies, chimes, rewards |
| `triangle` | Soft, hollow, warm | Coins, task completion |
| `square` | Buzzy, retro, 8-bit | Clicks, errors, UI sounds |
| `sawtooth` | Bright, rich, aggressive | Thuds, impacts, building placement |

### Frequency Modulation Patterns

**Rising sweep** (coin pickup, tension building):
```javascript
osc.frequency.setValueAtTime(200, now);
osc.frequency.linearRampToValueAtTime(800, now + 0.2);
```

**Falling sweep** (error, power-down, disappointment):
```javascript
osc.frequency.setValueAtTime(600, now);
osc.frequency.exponentialRampToValueAtTime(80, now + 0.3);
```

**Wobble** (magic, uncertainty):
```javascript
const wobble = ctx.createOscillator();
wobble.type = 'sine';
wobble.frequency.value = 6; // 6Hz — LFO rate
const wGain = ctx.createGain();
wGain.gain.value = 30; // modulation depth
wobble.connect(wGain);
wGain.connect(osc.frequency); // modulate the main oscillator
```

**Pulse train** (hammer, machine gun, construction):
```javascript
// Rhythmic short bursts
for (let i = 0; i < 5; i++) {
  const t = now + i * 0.08;
  osc.frequency.setValueAtTime(300, t);
  // ...
}
```

### Noise Generation

```javascript
function createNoiseBuffer(ctx, duration) {
  const sampleRate = ctx.sampleRate;
  const length = sampleRate * duration;
  const buffer = ctx.createBuffer(1, length, sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i++) {
    data[i] = Math.random() * 2 - 1;
  }
  return buffer;
}
```

Filtered noise creates natural-sounding ambience:
- **Lowpass (300Hz)**: Wind, ocean, room tone
- **Bandpass (800Hz)**: Forest, rain
- **Highpass (4kHz)**: Hiss, steam

## 4. Sound Effect Recipes for Kids Town

### 4.1 Coin Pickup / Reward Sound

```
Technique: Two sine oscillators at intervals of a 5th or 3rd
Base freq: 180Hz, rising to ~270Hz
Secondary: 270Hz, rising to ~360Hz (enters at 50ms delay)
Type: sine + triangle
Duration: ~220ms
Envelope: Quick attack (5ms), short sustain, exponential decay
```

**Why it works for children**: Ascending pitch = positive reinforcement. Two tones = richer than single beep. Triangle + sine = soft, not harsh.

### 4.2 Button Click / UI Interaction

```
Technique: Square wave burst + noise burst for tactile feel
Base freq: 800Hz, dropping to 200Hz in 40ms
Noise: 30ms white noise burst at 50% volume
Type: square + noise
Duration: ~60ms
Envelope: Instant attack, instant decay
```

**Why it works**: Short duration = responsive feel. Square wave = retro game nostalgia. Noise adds physical "texture".

### 4.3 Building Placement / Construction

```
Technique: Multi-layer — thud + chime + hammer taps
Layer 1 (thud): Sawtooth, 80Hz→40Hz, 150ms — physical impact
Layer 2 (ding): Sine, 400Hz→800Hz, 300ms — "built" confirmation
Layer 3 (hammer): 3x square wave taps at 80ms intervals — construction feel
Duration: ~450ms
```

**Why it works**: Layered sounds signal completion of a complex action. Low thud = weight/importance. Chime = positive feedback. Hammers = activity/progress.

### 4.4 Celebration / Success Jingle

```
Technique: Pentatonic ascending arpeggio + shimmer overlay
Notes: C4(262) → E4(330) → G4(392) → C5(523) → E5(660)
Tone spacing: 150ms between notes
Type: sine (with slight detune for chorus effect)
Overlay: Triangle shimmer at 1200-1600Hz, 3 quick hits
Duration: ~1.2s
Envelope: Per-note: 10ms attack, 120ms sustain, 80ms release
```

**Why it works**: Pentatonic scale is inherently pleasant (no dissonant intervals). Ascending = positive emotion. Arpeggio = "fanfare" feeling.

### 4.5 Background Ambience

```
Technique: Filtered noise loops + periodic oscillator chirps
Wind: 2-second noise buffer, lowpass at 300Hz, looped
Town hum: 60Hz sawtooth, lowpass at 120Hz, very quiet (vol 0.02)
Birds: Random chirps at 2000-3500Hz, 3-8 second intervals
Duration: Continuous loop, stops on tab hide
Volume: 0.08 (very quiet — should never distract)
```

**Why it works**: Low volume + filtered = subconscious immersion. Random intervals prevent fatigue. Tab-hide stop saves mobile battery.

## 5. Melody Generation for Children

### Pentatonic Scale (C Major Pentatonic)

```
C4 = 262 Hz
D4 = 294 Hz
E4 = 330 Hz
G4 = 392 Hz
A4 = 440 Hz
C5 = 523 Hz (octave)
```

**Properties**: No semitone intervals → impossible to hit a "wrong" note. Used in most children's music worldwide. Safe for random generation.

### Major Scale (C Major)

```
C4 = 262 Hz
D4 = 294 Hz
E4 = 330 Hz
F4 = 349 Hz
G4 = 392 Hz
A4 = 440 Hz
B4 = 494 Hz
C5 = 523 Hz
```

**Properties**: Happy, bright. Contains semitones (E-F, B-C) which can create tension/resolution. Good for more complex jingles.

### Children's Musical Preferences (by age)

| Age | Preferred Scale | Rhythm Complexity | Tempo |
|-----|----------------|-------------------|-------|
| 3-5 | Pentatonic | Simple (quarter notes) | 120-140 BPM |
| 6-8 | Major/pentatonic | Simple with syncopation | 110-130 BPM |
| 9-12 | Major/minor | Moderate syncopation | 100-120 BPM |

### Random Melody Algorithm

```javascript
function generateMelody(scale, numNotes, ascending = true) {
  const startIdx = Math.floor(Math.random() * 2); // 0 or 1
  const notes = [];
  for (let i = 0; i < numNotes; i++) {
    const idx = ascending
      ? Math.min(startIdx + i, scale.length - 1)
      : Math.max(startIdx - i, 0);
    notes.push({
      freq: scale[idx],
      duration: 0.1,
      gap: 0.02
    });
  }
  return notes;
}
```

## 6. Performance Considerations for Mobile PWA

### Concurrent Sound Limits

| Device | Max Concurrent | Notes |
|--------|---------------|-------|
| iPhone SE (2020) | 12-16 | Limited by CPU, not audio API |
| iPhone 14+ | 24+ | Modern chips handle many voices |
| Android mid-range | 8-12 | Lower DSP throughput |
| Android flagship | 16-24 | Snapdragon 8 series |
| Desktop Chrome | 40+ | Virtually unlimited |

**Implementation approach**: Soft limit with graceful degradation:
- Limit: 12 concurrent sounds
- When exceeded: skip non-critical sounds (ambient, hover)
- Always allow: UI clicks, confirmations, error sounds

### Memory Considerations

| Operation | Memory Impact | GC Risk |
|-----------|--------------|---------|
| Single oscillator + gain | ~2KB | Low |
| Noise buffer (2s) | ~172KB (at 44.1kHz) | One-time allocation |
| 5-note celebration | ~20KB (10 nodes) | Low if onended cleans up |
| Ambient loop (continuous) | ~172KB buffer + 6 nodes | Minimal (looped) |

**Key insight**: Web Audio API nodes are reference-counted and automatically GC'd when disconnected. The main memory concern is noise buffers — create once, reuse, release on ambient stop.

### Node Pooling Strategy

```javascript
// Reuse oscillator/gain pairs instead of creating new ones
const pool = {
  oscs: [],
  gains: [],
  maxSize: 20,
  acquire(type) {
    const osc = this.oscs.pop();
    if (osc) {
      osc.type = type;
      return osc;
    }
    return null; // caller creates new
  },
  release(osc, gain) {
    if (this.oscs.length < this.maxSize) this.oscs.push(osc);
    if (this.gains.length < this.maxSize) this.gains.push(gain);
  }
};
```

### Tab Backgrounding Strategy

- When tab is hidden: stop ambient loops, stop any long-running sounds
- Short sounds (< 1s): let them finish naturally
- When tab becomes visible: resume AudioContext, restart ambient if needed
- Use `document.visibilitychange` event, not `pagehide`/`pageshow`

## 7. Integration Points for Kids Town

| UI Action | Sound | Priority | Duration |
|-----------|-------|----------|----------|
| Login / kid selection | `buttonClick` | High | 60ms |
| Tab switch | `buttonClick` | High | 60ms |
| Complete task | `taskComplete` | High | 400ms |
| Earn gold/coins | `coinPickup` | High | 220ms |
| Build a building | `buildingPlace` | Medium | 500ms |
| Upgrade a building | `buildingUpgrade` | Medium | 700ms |
| Expedition start | `expBoost` | Medium | 600ms |
| Expedition complete | `celebration` | Medium | 1.2s |
| Error / insufficient funds | `errorBuzzer` | High | 250ms |
| Notification / reminder | `notification` | Medium | 200ms |
| Button hover | `uiHover` | Low | 30ms |
| Background (always on) | `startAmbient` | Low | ∞ |

## 8. Implementation Architecture

```
audio.js
├── AudioEngine (IIFE singleton)
│   ├── AudioContext lifecycle
│   │   ├── init() — lazy create on first gesture
│   │   ├── resumeContext() — resume on every user action
│   │   └── onVisibilityChange() — handle background/resume
│   ├── Sound generators
│   │   ├── coinPickup() — ascending chime
│   │   ├── buttonClick() — tactile click
│   │   ├── buildingPlace() — thud + chime
│   │   ├── celebration() — pentatonic fanfare
│   │   ├── taskComplete() — ding-ding shimmer
│   │   ├── buildingUpgrade() — arpeggiated chord
│   │   ├── errorBuzzer() — descending buzzer
│   │   ├── expBoost() — ascending arpeggio
│   │   ├── notification() — gentle pop
│   │   └── uiHover() — micro-click
│   │   ├── randomMelody() — pentatonic random
│   │   ├── startAmbient() — background loops
│   │   └── stopAmbient() — cleanup
│   ├── Performance manager
│   │   ├── Concurrent sound cap (12)
│   │   ├── Node pooling (optional)
│   │   └── Auto-cleanup via onended
│   └── Volume/mute controls
│       ├── setMuted(bool)
│       ├── toggleMute()
│       └── setVolume(0-1)
└── Auto-init (first click/touch/keydown handler)
```

## 9. Testing Checklist

- [ ] Click outside gesture handler: sound should queue or silently fail
- [ ] Click inside gesture handler: sound plays immediately
- [ ] iOS Safari: AudioContext resumes after first tap
- [ ] iOS Safari: AudioContext resumes after tab switch
- [ ] Mobile Chrome: context state = 'running' after gesture
- [ ] Rapid clicks: concurrency cap respected, no crashes
- [ ] Mute toggle: all sounds stop, no residual audio
- [ ] Ambient start/stop: clean transitions, no hanging nodes
- [ ] Tab background + return: ambient restarts, no duplicated nodes
- [ ] Memory: no growth over 10+ minutes of gameplay

## 10. References

1. **MDN Web Audio API**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
2. **MDN AudioContext resume()**: https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/resume
3. **MDN OscillatorNode**: https://developer.mozilla.org/en-US/docs/Web/API/OscillatorNode
4. **MDN GainNode**: https://developer.mozilla.org/en-US/docs/Web/API/GainNode
5. **MDN BiquadFilterNode**: https://developer.mozilla.org/en-US/docs/Web/API/BiquadFilterNode
6. **MDN Autoplay Guide**: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay
7. **Web Audio API Best Practices**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices
8. **iOS Web Audio Limitations**: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/Using_HTML5_Audio_Video/PlayingandSynthesizingSounds/PlayingandSynthesizingSounds.html
9. **Pentatonic Scale for Children's Music**: Educational music research (Zoltán Kodály method, Orff Schulwerk)
10. **Concurrent Audio Limits Study**: Chromium bug tracker, Web Audio mailing list

---

*Research compiled June 2026 for Kids Town PWA development.*
*Implementation: `/home/administrator/projects/hermes-ea/kids-town/audio.js`*
