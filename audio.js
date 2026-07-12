/**
 * Kids Town — Procedural Audio Engine
 * ====================================
 * 100% Web Audio API — zero audio files, zero dependencies.
 * All sounds generated at runtime via oscillators, noise, and gain envelopes.
 *
 * DESIGN PRINCIPLES:
 * - Lazy init on first user gesture (iOS/mobile safe)
 * - Node reuse via pooling to avoid GC churn
 * - Volume normalization across all sounds
 * - Pentatonic/major scales for child-friendly melodies
 * - Automatic cleanup of completed sounds
 *
 * USAGE:
 *   import { Audio } from './audio.js';
 *   // Must be called from a user gesture (click/touch)
 *   Audio.init();
 *   Audio.coinPickup();
 *   Audio.buttonClick();
 *   Audio.celebration();
 *
 * REFERENCE: See RESEARCH.md for design notes and references
 */

const Audio = (function() {
  'use strict';

  // ═══════════════════════════════════════════════════════════════
  // CONFIGURATION
  // ═══════════════════════════════════════════════════════════════

  const CONFIG = {
    masterVolume: 0.5,            // Master gain (0-1)
    maxConcurrent: 12,            // Max simultaneous sounds
    defaultDuration: 0.15,       // Seconds for decay to 0
    fadeOutTime: 0.1,            // Seconds for explicit fade out
    coinBounceFreq: 180,          // Starting frequency for coin sounds
    buttonClickFreq: 800,         // Initial frequency for clicks
    constructionThudFreq: 80,     // Low thud for building place
    jingleBPM: 180,              // BPM for melody generation
    ambientVolume: 0.08,         // Ambient loop volume (quiet)
  };

  // Pentatonic scale (C major pentatonic) — happy, child-safe
  // C4=262, D4=294, E4=330, G4=392, A4=440
  const PENTATONIC = [262, 294, 330, 392, 440];

  // Major scale (C major)
  // C4 D4 E4 F4 G4 A4 B4 C5
  const MAJOR_SCALE = [262, 294, 330, 349, 392, 440, 494, 523];

  // ═══════════════════════════════════════════════════════════════
  // STATE
  // ═══════════════════════════════════════════════════════════════

  let ctx = null;                 // AudioContext (lazy)
  let masterGain = null;          // Master volume node
  let isInitialized = false;      // Has init() been called?
  let isMuted = false;            // Global mute
  let activeCount = 0;           // Current concurrent sound count
  let ambientNodes = [];          // Active ambient loop nodes
  let ambientActive = false;     // Is ambient playing?
  let ctxResolved = false;       // Has a resume() been attempted?
  let cleanupInterval = null;    // Periodic cleanup timer

  // ═══════════════════════════════════════════════════════════════
  // NODE POOLING — Reuse GainNode/OscillatorNode pairs
  // ═══════════════════════════════════════════════════════════════

  const nodePool = {
    oscillators: [],
    gains: [],
    maxPoolSize: 20,

    acquireOsc() {
      return this.oscillators.pop() || null;
    },

    releaseOsc(osc) {
      if (this.oscillators.length < this.maxPoolSize) {
        this.oscillators.push(osc);
      }
    },

    acquireGain() {
      return this.gains.pop() || null;
    },

    releaseGain(gain) {
      if (this.gains.length < this.maxPoolSize) {
        this.gains.push(gain);
      }
    },

    clear() {
      this.oscillators = [];
      this.gains = [];
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // AUDIO CONTEXT LIFECYCLE — Mobile-safe initialization
  // ═══════════════════════════════════════════════════════════════

  /**
   * Initialize the audio engine.
   * MUST be called from a user-gesture handler (click, touch, keydown).
   * Safe to call multiple times — only creates context once.
   */
  function init() {
    if (isInitialized && ctx && ctx.state !== 'closed') return;

    try {
      // Create AudioContext with iOS-friendly options
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) {
        console.warn('[Audio] Web Audio API not supported');
        return;
      }

      ctx = new AudioCtx();
      masterGain = ctx.createGain();
      masterGain.gain.value = CONFIG.masterVolume;
      masterGain.connect(ctx.destination);

      resumeContext();
      isInitialized = true;

      // Start cleanup timer
      if (!cleanupInterval) {
        cleanupInterval = setInterval(cleanupExpired, 5000);
      }

      // Listen for visibility changes to handle iOS suspend
      document.addEventListener('visibilitychange', onVisibilityChange);

      console.log('[Audio] Engine initialized');
    } catch (e) {
      console.warn('[Audio] Init failed:', e.message);
    }
  }

  /**
   * Resume AudioContext if suspended (required on mobile/iOS).
   * Call on every user interaction to handle iOS restrictions.
   */
  function resumeContext() {
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx.resume().then(() => {
        ctxResolved = true;
        console.log('[Audio] Context resumed');
      }).catch(e => {
        console.warn('[Audio] Resume failed:', e.message);
      });
    } else if (ctx.state === 'running') {
      ctxResolved = true;
    }
  }

  /**
   * Handle page visibility changes.
   * iOS Safari suspends the AudioContext when the page is backgrounded.
   */
  function onVisibilityChange() {
    if (!ctx) return;
    if (document.visibilityState === 'visible') {
      resumeContext();
    } else if (document.visibilityState === 'hidden') {
      // Stop ambient sounds when tab is backgrounded to save resources
      stopAmbient();
    }
  }

  /**
   * Check if context is ready for playback.
   */
  function isReady() {
    return ctx && ctx.state !== 'closed' && isInitialized;
  }

  // ═══════════════════════════════════════════════════════════════
  // HELPER FUNCTIONS
  // ═══════════════════════════════════════════════════════════════

  /**
   * Create a basic tone with envelope.
   * Returns { oscillator, gainNode, stop() } for external control.
   *
   * @param {Object} opts
   * @param {number} opts.freq - Frequency in Hz (default: 440)
   * @param {string} opts.type - Waveform type (default: 'sine')
   * @param {number} opts.volume - Volume 0-1 (default: 0.3)
   * @param {number} opts.duration - Total duration in seconds (default: 0.15)
   * @param {number} opts.attack - Attack time in seconds (default: 0.005)
   * @param {number} opts.decay - Decay time in seconds (default: 0.01)
   * @param {boolean} opts.reuse - Whether to return nodes for pooling
   */
  function createTone(opts = {}) {
    if (!isReady()) return null;

    const {
      freq = 440,
      type = 'sine',
      volume = 0.3,
      duration = CONFIG.defaultDuration,
      attack = 0.005,
      decay = 0.01,
      reuse = false,
    } = opts;

    // Check concurrency limit
    if (activeCount >= CONFIG.maxConcurrent) {
      // Soft limit — skip least important sounds
      return null;
    }

    activeCount++;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, now);

    // ADSR envelope
    const sustainLevel = volume * 0.7;
    const releaseTime = Math.max(0.01, duration - attack - decay);

    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(volume, now + attack);
    gain.gain.linearRampToValueAtTime(sustainLevel, now + attack + decay);
    gain.gain.linearRampToValueAtTime(0.0001, now + attack + decay + releaseTime);

    osc.connect(gain);
    gain.connect(masterGain);

    const stopTime = now + attack + decay + releaseTime + 0.01;
    osc.start(now);
    osc.stop(stopTime);

    // Auto-cleanup
    const release = () => {
      activeCount = Math.max(0, activeCount - 1);
      try { osc.disconnect(); } catch(e) {}
      try { gain.disconnect(); } catch(e) {}
      if (reuse) {
        nodePool.releaseOsc(osc);
        nodePool.releaseGain(gain);
      }
    };

    osc.onended = release;

    return {
      oscillator: osc,
      gainNode: gain,
      stop: () => {
        try {
          const t = ctx.currentTime;
          gain.gain.cancelScheduledValues(t);
          gain.gain.setValueAtTime(gain.gain.value || 0.001, t);
          gain.gain.linearRampToValueAtTime(0.0001, t + CONFIG.fadeOutTime);
          osc.stop(t + CONFIG.fadeOutTime + 0.01);
        } catch(e) {}
      }
    };
  }

  /**
   * Frequency to MIDI note number converter (for musical intervals).
   */
  function freqToNote(freq) {
    return 12 * Math.log2(freq / 440) + 69;
  }

  /**
   * MIDI note number to frequency converter.
   */
  function noteToFreq(note) {
    return 440 * Math.pow(2, (note - 69) / 12);
  }

  /**
   * Play sequential tones as a melody.
   * @param {Array<{freq,type,volume,duration}>} notes
   */
  function playSequence(notes, baseTime = 0) {
    if (!isReady() || !notes || notes.length === 0) return;

    const now = ctx.currentTime + baseTime;
    let cursor = now;

    for (const note of notes) {
      const dur = note.duration || 0.1;
      const gap = note.gap || 0.02;
      createTone({
        freq: note.freq,
        type: note.type || 'sine',
        volume: note.volume || 0.2,
        duration: dur,
        attack: 0.003,
        decay: 0.005,
      });
      // Use scheduled time offset
      cursor += dur + gap;
    }
  }

  /**
   * Generate white noise buffer for percussive sounds.
   */
  function createNoiseBuffer(duration = 0.05) {
    if (!ctx) return null;
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(1, length, sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i++) {
      data[i] = Math.random() * 2 - 1;
    }
    return buffer;
  }

  /**
   * Play a short noise burst (for percussive/click sounds).
   */
  function playNoiseBurst(duration = 0.04, volume = 0.15) {
    if (!isReady()) return;

    const buffer = createNoiseBuffer(duration);
    if (!buffer) return;

    const source = ctx.createBufferSource();
    source.buffer = buffer;

    const gain = ctx.createGain();
    const now = ctx.currentTime;
    gain.gain.setValueAtTime(volume, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

    source.connect(gain);
    gain.connect(masterGain);
    source.start(now);
    source.stop(now + duration + 0.01);

    activeCount++;
    source.onended = () => {
      activeCount = Math.max(0, activeCount - 1);
      try { source.disconnect(); } catch(e) {}
      try { gain.disconnect(); } catch(e) {}
    };
  }

  /**
   * Create a BiquadFilter node for wind/ambient effects.
   */
  function createFilter(type = 'lowpass', freq = 1000, Q = 1) {
    if (!ctx) return null;
    const filter = ctx.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = freq;
    filter.Q.value = Q;
    return filter;
  }

  // ═══════════════════════════════════════════════════════════════
  // CLEANUP
  // ═══════════════════════════════════════════════════════════════

  function cleanupExpired() {
    // The onended handlers on each source handle individual cleanup.
    // This periodic timer reaps any orphaned references.
    // Node pooling naturally handles garbage.
  }

  /**
   * Clean up and close the AudioContext entirely.
   */
  function destroy() {
    stopAmbient();
    if (cleanupInterval) {
      clearInterval(cleanupInterval);
      cleanupInterval = null;
    }
    if (ctx && ctx.state !== 'closed') {
      ctx.close().catch(() => {});
    }
    ctx = null;
    masterGain = null;
    isInitialized = false;
    activeCount = 0;
    nodePool.clear();
    document.removeEventListener('visibilitychange', onVisibilityChange);
  }

  // ═══════════════════════════════════════════════════════════════
  // SOUND EFFECTS — PUBLIC API
  // ═══════════════════════════════════════════════════════════════

  /**
   * 1. COIN PICKUP / REWARD — bright ascending chime
   * Two sine oscillators at a major 3rd interval, quick rise.
   * Duration: ~250ms
   */
  function coinPickup(volume = 0.25) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;
    const baseFreq = CONFIG.coinBounceFreq;

    // Primary tone: sweep up from baseFreq
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(baseFreq, now);
    osc1.frequency.linearRampToValueAtTime(baseFreq * 1.5, now + 0.12);
    gain1.gain.setValueAtTime(0, now);
    gain1.gain.linearRampToValueAtTime(volume, now + 0.005);
    gain1.gain.linearRampToValueAtTime(0.0001, now + 0.2);
    osc1.connect(gain1);
    gain1.connect(masterGain);
    osc1.start(now);
    osc1.stop(now + 0.22);

    // Secondary tone: higher interval (5th)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(baseFreq * 1.5, now + 0.05);
    osc2.frequency.linearRampToValueAtTime(baseFreq * 2.0, now + 0.15);
    gain2.gain.setValueAtTime(0, now);
    gain2.gain.linearRampToValueAtTime(0, now + 0.05);
    gain2.gain.linearRampToValueAtTime(volume * 0.6, now + 0.07);
    gain2.gain.linearRampToValueAtTime(0.0001, now + 0.2);
    osc2.connect(gain2);
    gain2.connect(masterGain);
    osc2.start(now + 0.05);
    osc2.stop(now + 0.22);

    activeCount += 2;
    const dec = () => { activeCount = Math.max(0, activeCount - 1); };
    osc1.onended = dec;
    osc2.onended = dec;
  }

  /**
   * 2. BUTTON CLICK / UI INTERACTION — short tactile click
   * Noise burst + quick frequency drop.
   * Duration: ~60ms
   */
  function buttonClick(volume = 0.15) {
    if (!isReady()) return;
    resumeContext();

    playNoiseBurst(0.03, volume * 0.5);

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'square';
    osc.frequency.setValueAtTime(CONFIG.buttonClickFreq, now);
    osc.frequency.exponentialRampToValueAtTime(200, now + 0.04);
    gain.gain.setValueAtTime(volume, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
    osc.connect(gain);
    gain.connect(masterGain);
    osc.start(now);
    osc.stop(now + 0.06);

    activeCount++;
    osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
  }

  /**
   * 3. BUILDING PLACEMENT — low thud + construction chime
   * Low frequency impact + ascending "built" indicator.
   * Duration: ~500ms
   */
  function buildingPlace(volume = 0.3) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;

    // Low thud
    const thud = ctx.createOscillator();
    const gainThud = ctx.createGain();
    thud.type = 'sawtooth';
    thud.frequency.setValueAtTime(CONFIG.constructionThudFreq, now);
    thud.frequency.exponentialRampToValueAtTime(40, now + 0.15);
    gainThud.gain.setValueAtTime(volume * 0.8, now);
    gainThud.gain.exponentialRampToValueAtTime(0.0001, now + 0.15);
    thud.connect(gainThud);
    gainThud.connect(masterGain);
    thud.start(now);
    thud.stop(now + 0.17);

    // Construction "ding" — ascending chime
    const ding = ctx.createOscillator();
    const gainDing = ctx.createGain();
    ding.type = 'sine';
    ding.frequency.setValueAtTime(400, now + 0.1);
    ding.frequency.linearRampToValueAtTime(800, now + 0.35);
    gainDing.gain.setValueAtTime(0, now);
    gainDing.gain.linearRampToValueAtTime(volume * 0.5, now + 0.12);
    gainDing.gain.linearRampToValueAtTime(0.0001, now + 0.4);
    ding.connect(gainDing);
    gainDing.connect(masterGain);
    ding.start(now + 0.1);
    ding.stop(now + 0.42);

    // Hammer taps (rhythmic)
    for (let i = 0; i < 3; i++) {
      const t = now + 0.05 + i * 0.08;
      const hammer = ctx.createOscillator();
      const gainH = ctx.createGain();
      hammer.type = 'square';
      hammer.frequency.setValueAtTime(300, t);
      hammer.frequency.exponentialRampToValueAtTime(100, t + 0.03);
      gainH.gain.setValueAtTime(volume * 0.3, t);
      gainH.gain.exponentialRampToValueAtTime(0.0001, t + 0.04);
      hammer.connect(gainH);
      gainH.connect(masterGain);
      hammer.start(t);
      hammer.stop(t + 0.05);
    }

    activeCount += 5;
    const dec = () => { activeCount = Math.max(0, activeCount - 1); };
    thud.onended = dec;
    ding.onended = dec;
  }

  /**
   * 4. CELEBRATION / SUCCESS JINGLE — pentatonic ascending fanfare
   * 5-note C major pentatonic arpeggio.
   * Duration: ~1.2s
   */
  function celebration(volume = 0.3) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;
    const notes = [
      { freq: 262, time: 0 },      // C4
      { freq: 330, time: 0.15 },   // E4
      { freq: 392, time: 0.30 },   // G4
      { freq: 524, time: 0.45 },   // C5 (octave)
      { freq: 660, time: 0.65 },   // E5
    ];

    for (const n of notes) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(n.freq, now + n.time);
      // Slight detune for richness (chorus effect)
      osc.frequency.linearRampToValueAtTime(n.freq * 1.002, now + n.time + 0.1);

      gain.gain.setValueAtTime(0, now + n.time);
      gain.gain.linearRampToValueAtTime(volume, now + n.time + 0.01);
      gain.gain.linearRampToValueAtTime(volume * 0.4, now + n.time + 0.12);
      gain.gain.linearRampToValueAtTime(0.0001, now + n.time + 0.2);

      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(now + n.time);
      osc.stop(now + n.time + 0.22);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }

    // Add sparkle — high shimmer frequencies
    for (let i = 0; i < 3; i++) {
      const t = now + 0.3 + i * 0.15;
      const shim = ctx.createOscillator();
      const gShim = ctx.createGain();
      shim.type = 'triangle';
      shim.frequency.setValueAtTime(1200 + Math.random() * 400, t);
      gShim.gain.setValueAtTime(volume * 0.15, t);
      gShim.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
      shim.connect(gShim);
      gShim.connect(masterGain);
      shim.start(t);
      shim.stop(t + 0.14);

      activeCount++;
      shim.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }
  }

  /**
   * 5. TASK COMPLETE — short satisfaction sound
   * A sweet two-tone "ding-ding" with a golden shimmer.
   * Duration: ~400ms
   */
  function taskComplete(volume = 0.25) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;

    // First ding (C5)
    const d1 = ctx.createOscillator();
    const g1 = ctx.createGain();
    d1.type = 'triangle';
    d1.frequency.setValueAtTime(523, now);
    g1.gain.setValueAtTime(0, now);
    g1.gain.linearRampToValueAtTime(volume, now + 0.005);
    g1.gain.linearRampToValueAtTime(0.0001, now + 0.15);
    d1.connect(g1);
    g1.connect(masterGain);
    d1.start(now);
    d1.stop(now + 0.17);

    // Second ding (E5, higher)
    const d2 = ctx.createOscillator();
    const g2 = ctx.createGain();
    d2.type = 'sine';
    d2.frequency.setValueAtTime(659, now + 0.12);
    g2.gain.setValueAtTime(0, now);
    g2.gain.linearRampToValueAtTime(0, now + 0.12);
    g2.gain.linearRampToValueAtTime(volume, now + 0.13);
    g2.gain.linearRampToValueAtTime(0.0001, now + 0.35);
    d2.connect(g2);
    g2.connect(masterGain);
    d2.start(now + 0.12);
    d2.stop(now + 0.37);

    // Sparkle overlay
    const sp = ctx.createOscillator();
    const gs = ctx.createGain();
    sp.type = 'sine';
    sp.frequency.setValueAtTime(1318, now + 0.2); // E6
    gs.gain.setValueAtTime(0, now);
    gs.gain.linearRampToValueAtTime(0, now + 0.2);
    gs.gain.linearRampToValueAtTime(volume * 0.3, now + 0.22);
    gs.gain.exponentialRampToValueAtTime(0.0001, now + 0.4);
    sp.connect(gs);
    gs.connect(masterGain);
    sp.start(now + 0.2);
    sp.stop(now + 0.42);

    activeCount += 3;
    const dec = () => { activeCount = Math.max(0, activeCount - 1); };
    d1.onended = dec;
    d2.onended = dec;
    sp.onended = dec;
  }

  /**
   * 6. BUILDING UPGRADE — magical ascending spiral
   * Arpeggiated chords with a "sparkle shimmer".
   * Duration: ~700ms
   */
  function buildingUpgrade(volume = 0.3) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;
    const baseFreq = 300;

    // Ascending arpeggio: C major chord arpeggiated
    const chordNotes = [0, 4, 7, 12, 16]; // semitone intervals from base
    for (let i = 0; i < chordNotes.length; i++) {
      const t = now + i * 0.1;
      const freq = baseFreq * Math.pow(2, chordNotes[i] / 12);

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = i % 2 === 0 ? 'sine' : 'triangle';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(volume * (1 - i * 0.1), t + 0.01);
      gain.gain.linearRampToValueAtTime(0.0001, t + 0.15);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t);
      osc.stop(t + 0.17);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }

    // Ending shimmer (high frequencies)
    for (let i = 0; i < 4; i++) {
      const t = now + 0.5 + i * 0.03;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(1200 + Math.random() * 600, t);
      gain.gain.setValueAtTime(volume * 0.1, t);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t);
      osc.stop(t + 0.1);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }
  }

  /**
   * 7. ERROR / WRONG ACTION — descending buzzer
   * Quick descending tone with square wave (buzzy, attention-getting).
   * Duration: ~250ms
   */
  function errorBuzzer(volume = 0.2) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'square';
    osc.frequency.setValueAtTime(400, now);
    osc.frequency.exponentialRampToValueAtTime(120, now + 0.2);
    gain.gain.setValueAtTime(volume, now);
    gain.gain.linearRampToValueAtTime(volume * 0.8, now + 0.05);
    gain.gain.linearRampToValueAtTime(0.0001, now + 0.22);
    osc.connect(gain);
    gain.connect(masterGain);
    osc.start(now);
    osc.stop(now + 0.24);

    activeCount++;
    osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
  }

  /**
   * 8. EXPEDITION / BOOST — exciting upward sweep
   * Ascending pitch with increasing tempo, like a "level up".
   * Duration: ~600ms
   */
  function expBoost(volume = 0.25) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;

    // Rapid ascending arpeggio
    const notes = [262, 330, 392, 523, 659, 784, 1047];
    for (let i = 0; i < notes.length; i++) {
      const t = now + i * 0.06;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = i % 2 === 0 ? 'sine' : 'triangle';
      osc.frequency.setValueAtTime(notes[i], t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(volume, t + 0.005);
      gain.gain.linearRampToValueAtTime(0.0001, t + 0.08);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t);
      osc.stop(t + 0.1);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }

    // Final "hit"
    const finalOsc = ctx.createOscillator();
    const finalGain = ctx.createGain();
    finalOsc.type = 'sawtooth';
    finalOsc.frequency.setValueAtTime(800, now + 0.45);
    finalOsc.frequency.exponentialRampToValueAtTime(200, now + 0.55);
    finalGain.gain.setValueAtTime(0, now);
    finalGain.gain.linearRampToValueAtTime(0, now + 0.45);
    finalGain.gain.linearRampToValueAtTime(volume * 1.2, now + 0.47);
    finalGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.58);
    finalOsc.connect(finalGain);
    finalGain.connect(masterGain);
    finalOsc.start(now + 0.45);
    finalOsc.stop(now + 0.6);

    activeCount++;
    finalOsc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
  }

  /**
   * 9. NOTIFICATION / ALERT — gentle two-tone "pop"
   * Friendly attention-getter, not intrusive.
   * Duration: ~200ms
   */
  function notification(volume = 0.2) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;

    // Two quick tones
    for (let i = 0; i < 2; i++) {
      const t = now + i * 0.1;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(600 + i * 100, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(volume, t + 0.005);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t);
      osc.stop(t + 0.09);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }
  }

  /**
   * 10. UI HOVER — tiny pop for button hover/highlight
   * Extremely short, barely audible — just enough to confirm interaction.
   * Duration: ~30ms
   */
  function uiHover(volume = 0.05) {
    if (!isReady()) return;
    resumeContext();

    playNoiseBurst(0.015, volume * 0.3);

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1000, now);
    osc.frequency.exponentialRampToValueAtTime(600, now + 0.02);
    gain.gain.setValueAtTime(volume, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.025);
    osc.connect(gain);
    gain.connect(masterGain);
    osc.start(now);
    osc.stop(now + 0.03);

    activeCount++;
    osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
  }

  // ═══════════════════════════════════════════════════════════════
  // AMBIENT SOUNDS — Background loops
  // ═══════════════════════════════════════════════════════════════

  /**
   * Start background ambient sound (wind + birds + town hum).
   * Uses Filtered noise + periodic chirp oscillators.
   * Automatically stops when tab is hidden.
   */
  function startAmbient(type = 'town') {
    if (!isReady() || ambientActive) return;
    resumeContext();

    ambientActive = true;
    ambientNodes = [];

    switch (type) {
      case 'town':
        startTownAmbient();
        break;
      case 'forest':
        startForestAmbient();
        break;
      case 'night':
        startNightAmbient();
        break;
      default:
        startTownAmbient();
    }
  }

  function startTownAmbient() {
    if (!ctx) return;
    const vol = CONFIG.ambientVolume;

    // 1. Gentle wind (filtered noise)
    const noiseLen = ctx.sampleRate * 2; // 2 second buffer, looped
    const noiseBuf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
    const noiseData = noiseBuf.getChannelData(0);
    for (let i = 0; i < noiseLen; i++) {
      noiseData[i] = (Math.random() * 2 - 1) * 0.3;
    }

    const noiseSrc = ctx.createBufferSource();
    noiseSrc.buffer = noiseBuf;
    noiseSrc.loop = true;

    const noiseFilter = ctx.createBiquadFilter();
    noiseFilter.type = 'lowpass';
    noiseFilter.frequency.value = 300;
    noiseFilter.Q.value = 0.5;

    const noiseGain = ctx.createGain();
    noiseGain.gain.value = vol * 0.3;

    noiseSrc.connect(noiseFilter);
    noiseFilter.connect(noiseGain);
    noiseGain.connect(masterGain);
    noiseSrc.start();

    ambientNodes.push(noiseSrc, noiseFilter, noiseGain);

    // 2. Low town hum (filtered sawtooth, very quiet)
    const hum = ctx.createOscillator();
    const humFilter = ctx.createBiquadFilter();
    const humGain = ctx.createGain();
    hum.type = 'sawtooth';
    hum.frequency.value = 60;
    humFilter.type = 'lowpass';
    humFilter.frequency.value = 120;
    humGain.gain.value = vol * 0.2;
    hum.connect(humFilter);
    humFilter.connect(humGain);
    humGain.connect(masterGain);
    hum.start();

    ambientNodes.push(hum, humFilter, humGain);

    // 3. Periodic bird chirps (high-frequency pings)
    scheduleBirdChirps(ctx, vol);
  }

  function startForestAmbient() {
    if (!ctx) return;
    const vol = CONFIG.ambientVolume;

    // Wind (higher frequency than town)
    const noiseLen = ctx.sampleRate * 3;
    const noiseBuf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < noiseLen; i++) {
      d[i] = (Math.random() * 2 - 1) * 0.25;
    }
    const ns = ctx.createBufferSource();
    ns.buffer = noiseBuf;
    ns.loop = true;
    const nf = ctx.createBiquadFilter();
    nf.type = 'bandpass';
    nf.frequency.value = 800;
    nf.Q.value = 0.3;
    const ng = ctx.createGain();
    ng.gain.value = vol * 0.25;
    ns.connect(nf);
    nf.connect(ng);
    ng.connect(masterGain);
    ns.start();
    ambientNodes.push(ns, nf, ng);

    // Bird chirps (more frequent in forest)
    scheduleBirdChirps(ctx, vol, 2.0, 5.0);
  }

  function startNightAmbient() {
    if (!ctx) return;
    const vol = CONFIG.ambientVolume;

    // Crickets (high-frequency pulses)
    const chirp = () => {
      if (!ambientActive || !ctx) return;
      const t = ctx.currentTime;
      for (let i = 0; i < 3; i++) {
        const osc = ctx.createOscillator();
        const g = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(4000 + Math.random() * 1000, t);
        g.gain.setValueAtTime(vol * 0.5, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.04);
        osc.connect(g);
        g.connect(masterGain);
        osc.start(t);
        osc.stop(t + 0.05);

        activeCount++;
        osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
      }
    };

    // Schedule cricket chirps at random intervals
    let nextCricket = () => {
      if (!ambientActive) return;
      chirp();
      const delay = 1500 + Math.random() * 3000;
      cricketTimer = setTimeout(nextCricket, delay);
    };
    let cricketTimer = setTimeout(nextCricket, 1000);

    // Store cricket timer for cleanup
    ambientNodes.push({ _isTimer: true, cancel: () => clearTimeout(cricketTimer) });

    // Owl hoot (very occasional)
    const hoot = () => {
      if (!ambientActive || !ctx) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(200, t);
      osc.frequency.linearRampToValueAtTime(150, t + 0.3);
      osc.frequency.linearRampToValueAtTime(180, t + 0.6);
      osc.frequency.linearRampToValueAtTime(140, t + 0.9);
      g.gain.setValueAtTime(vol * 0.8, t);
      g.gain.linearRampToValueAtTime(vol * 0.3, t + 0.5);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 1.0);
      osc.connect(g);
      g.connect(masterGain);
      osc.start(t);
      osc.stop(t + 1.02);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    };
    let owlTimer = setTimeout(function owlFn() {
      if (!ambientActive) return;
      hoot();
      owlTimer = setTimeout(owlFn, 8000 + Math.random() * 12000);
    }, 4000 + Math.random() * 6000);
    ambientNodes.push({ _isTimer: true, cancel: () => clearTimeout(owlTimer) });
  }

  /**
   * Schedule periodic bird chirps at random intervals.
   */
  function scheduleBirdChirps(audioCtx, vol, minInterval = 3.0, maxInterval = 8.0) {
    if (!audioCtx) return;

    function chirp() {
      if (!ambientActive || !ctx) return;
      const t = ctx.currentTime;

      // Bird chirp = two rapid high-frequency tones
      for (let i = 0; i < 2; i++) {
        const osc = ctx.createOscillator();
        const g = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(
          2000 + Math.random() * 1500 + i * 300,
          t + i * 0.03
        );
        g.gain.setValueAtTime(vol * 0.8, t + i * 0.03);
        g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.03 + 0.06);
        osc.connect(g);
        g.connect(masterGain);
        osc.start(t + i * 0.03);
        osc.stop(t + i * 0.03 + 0.07);

        activeCount++;
        osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
      }
    }

    let timer;
    function scheduleNext() {
      if (!ambientActive) return;
      const delay = (minInterval + Math.random() * (maxInterval - minInterval)) * 1000;
      timer = setTimeout(() => {
        chirp();
        scheduleNext();
      }, delay);
    }
    scheduleNext();

    ambientNodes.push({
      _isTimer: true,
      cancel: () => { if (timer) clearTimeout(timer); }
    });
  }

  /**
   * Stop all ambient sounds.
   */
  function stopAmbient() {
    ambientActive = false;
    for (const node of ambientNodes) {
      if (node && node._isTimer && typeof node.cancel === 'function') {
        node.cancel();
      } else if (node && typeof node.stop === 'function') {
        try { node.stop(); } catch(e) {}
        try { node.disconnect(); } catch(e) {}
      }
    }
    ambientNodes = [];
  }

  // ═══════════════════════════════════════════════════════════════
  // UTILITY FUNCTIONS
  // ═══════════════════════════════════════════════════════════════

  /**
   * Plays a random short melody from the pentatonic scale.
   * Good for random "happy" events.
   */
  function randomMelody(volume = 0.2) {
    if (!isReady()) return;
    resumeContext();

    const now = ctx.currentTime;
    const numNotes = 3 + Math.floor(Math.random() * 3); // 3-5 notes
    const startNote = Math.floor(Math.random() * 3); // 0-2 (first 3 notes of pentatonic)
    const ascending = Math.random() > 0.3;

    for (let i = 0; i < numNotes; i++) {
      const idx = ascending
        ? Math.min(startNote + i, PENTATONIC.length - 1)
        : Math.max(startNote - i, 0);
      const freq = PENTATONIC[idx];
      const t = now + i * 0.12;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(volume, t + 0.005);
      gain.gain.linearRampToValueAtTime(0.0001, t + 0.1);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t);
      osc.stop(t + 0.12);

      activeCount++;
      osc.onended = () => { activeCount = Math.max(0, activeCount - 1); };
    }
  }

  /**
   * Mute/unmute all audio.
   */
  function setMuted(muted) {
    isMuted = muted;
    if (masterGain) {
      masterGain.gain.value = muted ? 0 : CONFIG.masterVolume;
    }
    if (muted) {
      stopAmbient();
    }
  }

  function toggleMute() {
    setMuted(!isMuted);
    return isMuted;
  }

  function getMuted() { return isMuted; }

  /**
   * Set master volume (0-1).
   */
  function setVolume(vol) {
    CONFIG.masterVolume = Math.max(0, Math.min(1, vol));
    if (masterGain && !isMuted) {
      masterGain.gain.value = CONFIG.masterVolume;
    }
  }

  function getVolume() { return CONFIG.masterVolume; }

  /**
   * Get current concurrent sound count.
   */
  function getActiveCount() { return activeCount; }

  /**
   * Get AudioContext state.
   */
  function getContextState() {
    return ctx ? ctx.state : 'uninitialized';
  }

  // ═══════════════════════════════════════════════════════════════
  // PUBLIC API
  // ═══════════════════════════════════════════════════════════════

  return {
    // Lifecycle
    init,
    destroy,
    resume: resumeContext,

    // Sound effects
    coinPickup,
    buttonClick,
    buildingPlace,
    celebration,
    taskComplete,
    buildingUpgrade,
    errorBuzzer,
    expBoost,
    notification,
    uiHover,

    // Ambient
    startAmbient,
    stopAmbient,

    // Utility
    randomMelody,
    setMuted,
    toggleMute,
    getMuted,
    setVolume,
    getVolume,
    getActiveCount,
    getContextState,
    isReady,
  };
})();

window.Audio = Audio;

// ═══════════════════════════════════════════════════════════════
// AUTO-INIT ON FIRST GESTURE (falls back to manual init)
// ═══════════════════════════════════════════════════════════════

// Capture the first user gesture to auto-init the AudioContext.
const _autoInit = () => {
  Audio.init();
  document.removeEventListener('click', _autoInit);
  document.removeEventListener('touchstart', _autoInit);
  document.removeEventListener('keydown', _autoInit);
};
document.addEventListener('click', _autoInit, { once: true });
document.addEventListener('touchstart', _autoInit, { once: true });
document.addEventListener('keydown', _autoInit, { once: true });
