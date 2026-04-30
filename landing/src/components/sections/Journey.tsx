"use client";

import { useEffect } from "react";

const JOURNEY_CSS = `
  /* ===== CSS VARIABLES ===== */
  .journey-wrap {
    --carbon:#0A0A0B;
    --carbon-100:#141416;
    --carbon-200:#1C1C1F;
    --carbon-300:#222225;
    --carbon-400:#2A2A2E;
    --border:#2A2A2E;
    --border-subtle:#1F1F23;
    --bruma:#F5F5F7;
    --bruma-muted:#C7C7CC;
    --plomo:#8E8E93;
    --plomo-light:#AEAEB2;
    --krypton:#D4FF00;
    --krypton-dim:rgba(212,255,0,0.08);
    --krypton-glow:rgba(212,255,0,0.22);
    --ok:#7BE495;
    --warn:#FFC857;
    --err:#FF7A7A;
    --blue:#7DB9FF;
  }

  /* ===== PROGRESS BAR ===== */
  #j-progress {
    position:fixed; top:0; left:0; height:2px;
    background:var(--krypton); z-index:70; width:0%;
    box-shadow:0 0 12px var(--krypton-glow);
    pointer-events:none;
  }

  /* ===== RAIL ===== */
  .j-rail {
    position:fixed; right:28px; top:50%; transform:translateY(-50%);
    z-index:55; display:flex; flex-direction:column; gap:14px;
    pointer-events:none;
  }
  .j-rail-step {
    display:flex; align-items:center; gap:10px;
    color:var(--plomo); font-size:11px;
    font-family:'JetBrains Mono',monospace; letter-spacing:0.05em;
    opacity:0.55; transition:opacity .4s, color .4s;
    pointer-events:auto; cursor:pointer;
    justify-content:flex-end;
  }
  .j-rail-step .num {
    width:22px; height:22px; border-radius:50%;
    border:1px solid var(--border); display:grid; place-items:center;
    font-size:10px; background:var(--carbon-100);
    transition:all .4s;
  }
  .j-rail-step.active { opacity:1; color:var(--bruma); }
  .j-rail-step.active .num { background:var(--krypton); color:var(--carbon); border-color:var(--krypton); box-shadow:0 0 16px var(--krypton-glow); }
  .j-rail-step.done { opacity:0.9; color:var(--plomo-light); }
  .j-rail-step.done .num { background:var(--krypton-dim); color:var(--krypton); border-color:rgba(212,255,0,0.3); }
  @media(max-width:980px){ .j-rail { display:none; } }

  /* ===== SCROLLY STRUCTURE ===== */
  .j-scrolly { position:relative; }
  .j-stage { position:relative; height:600vh; }
  .j-stage.short { height:400vh; }
  .j-stage.tall { height:750vh; }
  .j-stage-sticky {
    position:sticky; top:0; height:100vh;
    display:grid; grid-template-columns:minmax(360px, 1fr) 1.25fr;
    gap:40px; padding:80px 80px;
    align-items:center;
  }
  /* ===== COPY COLUMN ===== */
  .j-copy { max-width:460px; }
  .j-stage-eyebrow {
    display:inline-flex; align-items:center; gap:10px;
    font-family:'JetBrains Mono',monospace; font-size:11px;
    letter-spacing:0.18em; text-transform:uppercase;
    color:var(--krypton); margin-bottom:18px; font-weight:600;
  }
  .j-stage-eyebrow .ix {
    padding:2px 8px; border-radius:5px; background:var(--krypton-dim);
    border:1px solid rgba(212,255,0,0.25);
  }
  .j-copy h2 {
    font-size:clamp(34px, 4.2vw, 54px); line-height:1.05;
    letter-spacing:-0.025em; font-weight:700;
    margin:0 0 18px; text-wrap:balance;
    color:var(--bruma);
  }
  .j-copy h2 em { font-family:'Instrument Serif',serif; font-style:italic; font-weight:400; color:var(--krypton); }
  .j-copy p { color:var(--plomo-light); font-size:17px; margin:0 0 14px; text-wrap:pretty; }
  .j-copy p b { color:var(--bruma); font-weight:600; }
  .j-copy .kvs {
    margin-top:22px; display:flex; flex-direction:column; gap:8px;
    font-size:13px; color:var(--plomo-light);
    font-family:'JetBrains Mono',monospace;
  }
  .j-copy .kvs div { display:flex; gap:14px; align-items:baseline; }
  .j-copy .kvs .k { color:var(--plomo); min-width:120px; }
  .j-copy .kvs .v { color:var(--bruma); }
  .j-copy .kvs .v b { color:var(--krypton); font-weight:600; }

  /* ===== CANVAS ===== */
  .j-canvas {
    position:relative; height:min(82vh, 700px);
    border-radius:18px;
    background:linear-gradient(180deg, var(--carbon-100), var(--carbon-200));
    border:1px solid var(--border);
    overflow:hidden;
    box-shadow:0 40px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(212,255,0,0.03);
  }
  .j-canvas-bar {
    display:flex; align-items:center; gap:10px;
    padding:12px 16px; border-bottom:1px solid var(--border);
    font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--plomo);
    position:relative; overflow:hidden;
  }
  .j-upload-progress {
    position:absolute; bottom:0; left:0; height:2px;
    background:var(--krypton); width:0%;
    box-shadow:0 0 8px var(--krypton-glow);
    transition:width .12s linear;
  }
  .j-canvas-bar .dots { display:flex; gap:6px; }
  .j-canvas-bar .dots i { width:9px; height:9px; border-radius:50%; background:var(--carbon-400); }
  .j-canvas-bar .file { background:var(--carbon-300); color:var(--bruma-muted); padding:3px 10px; border-radius:5px; font-size:11px; }
  .j-canvas-bar .status { margin-left:auto; color:var(--krypton); display:inline-flex; align-items:center; gap:6px; font-size:11px; }
  .j-canvas-bar .status .d { width:7px; height:7px; border-radius:50%; background:var(--krypton); box-shadow:0 0 8px var(--krypton); animation:j-pulse 1.5s ease-in-out infinite; }
  .j-canvas-body { position:absolute; inset:45px 0 0 0; padding:24px 28px; }

  /* ===== KEYFRAMES ===== */
  @keyframes j-pulse { 50%{ opacity:0.4; } }
  @keyframes j-bounce { 0%,100%{ transform:translateY(0); } 50%{ transform:translateY(6px); } }
  @keyframes j-scan { to{ background:var(--krypton); } }
  @keyframes j-btnpulse { 50%{ box-shadow:0 0 0 6px rgba(212,255,0,0.15); } }
  @keyframes j-hintbounce { 0%,100%{ opacity:0.5; transform:translateY(-3px); } 50%{ opacity:1; transform:translateY(3px); } }

  /* ===== STAGE 1 · UPLOAD ===== */
  .j-doc-float {
    position:relative; width:220px; height:280px;
    margin:0 auto; top:50%; transform:translate(0, calc(-50% + var(--float, -40px)));
    border-radius:10px;
    background:linear-gradient(180deg, #FAFAFA, #E5E5E7);
    box-shadow:0 40px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05);
    padding:24px 20px;
    transition:transform .6s cubic-bezier(0.2,0.8,0.2,1);
  }
  .j-doc-float::before {
    content:""; position:absolute; top:0; right:0; width:36px; height:36px;
    background:linear-gradient(135deg, #E5E5E7 50%, #C7C7CC 50%);
    border-top-right-radius:10px;
  }
  .j-doc-float .page-title { font-size:9px; color:#1C1C1F; font-weight:600; margin-bottom:10px; letter-spacing:-0.01em; }
  .j-doc-float .line { height:4px; background:#C7C7CC; border-radius:2px; margin-bottom:5px; }
  .j-doc-float .line:nth-child(2) { width:85%; }
  .j-doc-float .line:nth-child(3) { width:92%; }
  .j-doc-float .line:nth-child(4) { width:76%; }
  .j-doc-float .line:nth-child(5) { width:88%; margin-top:10px; }
  .j-doc-float .line:nth-child(6) { width:60%; }
  .j-doc-float .line:nth-child(7) { width:90%; margin-top:10px; }
  .j-doc-float .line:nth-child(8) { width:70%; }
  .j-doc-float .tag {
    position:absolute; bottom:14px; right:14px;
    font-size:8px; background:#1C1C1F; color:#FAFAFA;
    padding:2px 6px; border-radius:3px; font-family:'JetBrains Mono',monospace; font-weight:600;
  }
  .j-upload-beam {
    position:absolute; left:50%; top:50%;
    width:1px; height:0; transform:translate(-50%, -50%);
    background:linear-gradient(180deg, transparent, var(--krypton), transparent);
    opacity:0; transition:height .8s ease, opacity .4s;
    box-shadow:0 0 20px var(--krypton);
  }
  .j-upload-beam.on { opacity:0.8; height:400px; }
  .j-file-meta {
    position:absolute; inset:auto 0 30px 0; text-align:center;
    font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--plomo);
  }
  .j-file-meta b { color:var(--bruma); font-weight:500; }
  .j-file-meta .big { font-size:15px; color:var(--bruma); }

  /* ===== STAGE 2 · ANALYSIS ===== */
  .j-analysis { position:absolute; inset:45px 0 0 0; padding:28px; }
  .j-pages-grid {
    display:grid; grid-template-columns:repeat(18, 1fr); gap:3px;
    margin-bottom:28px;
  }
  .page-cell {
    aspect-ratio:0.7; background:var(--carbon-300);
    border-radius:2px; transition:background .3s, box-shadow .3s;
  }
  .page-cell.scanned { background:var(--krypton); box-shadow:0 0 8px var(--krypton-glow); }
  .page-cell.scanning { background:rgba(212,255,0,0.4); animation:j-scan 0.4s ease-in-out infinite alternate; }
  .j-extractions { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  .extract-card {
    padding:14px 16px; border:1px solid var(--border);
    border-radius:10px; background:var(--carbon-100);
    opacity:0; transform:translateY(12px);
    transition:all .5s cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  .extract-card.in { opacity:1; transform:translateY(0); }
  .extract-card .lbl {
    font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--plomo);
    letter-spacing:0.1em; text-transform:uppercase; margin-bottom:6px;
  }
  .extract-card .val { color:var(--bruma); font-size:14px; line-height:1.5; }
  .extract-card .val b { color:var(--krypton); font-weight:600; }
  .extract-card.big { grid-column:span 2; }
  .j-pill-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
  .j-pill {
    display:inline-flex; align-items:center; gap:5px;
    padding:3px 9px; border-radius:999px;
    background:var(--krypton-dim); color:var(--krypton);
    font-size:11px; font-family:'JetBrains Mono',monospace;
    border:1px solid rgba(212,255,0,0.2);
  }
  .j-pill.muted { background:var(--carbon-300); color:var(--bruma-muted); border-color:var(--border); }

  /* ===== STAGE 3 · SPELLING ===== */
  .j-spell { position:absolute; inset:45px 0 0 0; padding:26px 30px; display:flex; flex-direction:column; }
  .j-spell-text {
    font-size:15px; line-height:1.95; color:var(--bruma-muted);
    font-family:'Georgia', serif; flex:1;
  }
  .j-spell-err {
    position:relative; color:var(--bruma-muted);
    border-bottom:2px solid transparent; padding-bottom:1px;
    transition:color .35s ease, border-bottom-color .35s ease, background-color .35s ease;
  }
  .j-spell-err.revealed {
    color:var(--bruma);
    border-bottom:2px wavy var(--err);
    background-color:rgba(255,122,122,0.07);
  }
  .j-spell-protected {
    color:var(--bruma-muted); font-weight:500;
    border-bottom:1.5px dotted transparent;
    transition:color .35s ease, border-bottom-color .35s ease, font-weight .35s ease, background-color .35s ease;
  }
  .j-spell-protected.revealed {
    color:var(--krypton); font-weight:600;
    border-bottom-color:var(--krypton);
    background-color:rgba(212,255,0,0.06);
  }
  .j-spell-stats {
    display:grid; grid-template-columns:repeat(3, 1fr); gap:10px;
    margin-top:18px; padding-top:16px; border-top:1px solid var(--border);
  }
  .j-spell-stat { text-align:center; }
  .j-spell-stat .n {
    font-size:22px; font-weight:700; letter-spacing:-0.02em;
    font-feature-settings:'tnum'; color:var(--bruma);
  }
  .j-spell-stat .n.err { color:var(--err); }
  .j-spell-stat .n.ok { color:var(--ok); }
  .j-spell-stat .n.proj { color:var(--krypton); }
  .j-spell-stat .l { font-size:11px; color:var(--plomo); font-family:'JetBrains Mono',monospace; letter-spacing:0.05em; text-transform:uppercase; margin-top:2px; }
  .j-callout {
    display:flex; gap:10px; padding:10px 12px; margin-top:14px;
    border:1px dashed rgba(212,255,0,0.3); border-radius:8px;
    background:rgba(212,255,0,0.04);
    font-size:12px; color:var(--bruma-muted); line-height:1.5;
  }
  .j-callout svg { flex-shrink:0; color:var(--krypton); margin-top:2px; }
  .j-callout b { color:var(--bruma); font-weight:500; }

  /* ===== STAGE 4 · EDITORIAL ===== */
  .j-editorial { position:absolute; inset:45px 0 0 0; padding:24px 28px; }
  .j-edit-head { font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--plomo); margin-bottom:14px; }
  .j-edit-head b { color:var(--krypton); font-weight:500; }
  .j-edit-layers { display:flex; flex-direction:column; gap:10px; }
  .edit-layer {
    display:flex; align-items:center; gap:14px;
    padding:12px 14px;
    border:1px solid var(--border); border-radius:10px;
    background:var(--carbon-100);
    opacity:0.35; transition:all .5s;
  }
  .edit-layer.active { opacity:1; border-color:rgba(212,255,0,0.3); background:var(--carbon-200); box-shadow:0 0 24px rgba(212,255,0,0.08); }
  .edit-layer.done { opacity:0.7; }
  .edit-layer .icon {
    width:34px; height:34px; flex-shrink:0;
    border-radius:8px; background:var(--carbon-300);
    display:grid; place-items:center; color:var(--plomo); transition:all .4s;
  }
  .edit-layer.active .icon { background:var(--krypton); color:var(--carbon); }
  .edit-layer .content { flex:1; min-width:0; }
  .edit-layer .title { font-weight:600; font-size:14px; color:var(--bruma); margin-bottom:2px; }
  .edit-layer .desc { font-size:12px; color:var(--plomo-light); }
  .edit-layer .count {
    font-family:'JetBrains Mono',monospace; font-size:13px;
    color:var(--krypton); font-weight:600; min-width:38px; text-align:right;
  }
  .edit-layer.done .count { color:var(--bruma-muted); }
  .j-voice-quote {
    margin-top:16px; padding:14px 16px;
    background:var(--carbon-200); border-left:2px solid var(--krypton);
    border-radius:4px;
    font-family:'Instrument Serif',serif; font-style:italic;
    font-size:15px; color:var(--bruma-muted); line-height:1.6;
  }
  .j-voice-quote b {
    color:var(--bruma); font-style:normal; font-family:'Inter',sans-serif;
    font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:0.1em;
    display:block; margin-top:8px;
  }

  /* ===== STAGE 5 · REVIEW ===== */
  .j-review { position:absolute; inset:45px 0 0 0; padding:24px 28px; display:flex; flex-direction:column; }
  .j-review-paragraph {
    padding:16px 18px; border-radius:12px;
    border:1px solid var(--border); background:var(--carbon-100);
    font-family:'Georgia', serif; font-size:14.5px; line-height:1.9;
    margin-bottom:14px; position:relative;
  }
  .j-review-paragraph .label {
    position:absolute; top:-8px; left:14px;
    font-family:'JetBrains Mono',monospace; font-size:9px;
    padding:2px 8px; border-radius:4px;
    background:var(--carbon); border:1px solid var(--border);
    color:var(--plomo); letter-spacing:0.1em; text-transform:uppercase;
  }
  .j-del {
    padding:1px 4px; border-radius:3px; margin-right:2px;
    background:transparent; color:inherit; text-decoration:none;
    transition:background .35s, color .35s;
  }
  .j-del.marked { background:rgba(255,122,122,0.14); color:#FFA8A8; text-decoration:line-through; }
  .j-ins {
    padding:1px 5px; border-radius:3px; font-weight:inherit;
    background:transparent; color:inherit;
    transition:background .35s, color .35s, font-weight .2s;
  }
  .j-ins.shown { background:rgba(123,228,149,0.18); color:#C3F4D0; font-weight:500; }
  .j-review-actions {
    display:flex; gap:10px; align-items:center;
    margin-top:auto; padding-top:12px; border-top:1px solid var(--border);
  }
  .j-btn-accept, .j-btn-reject {
    display:inline-flex; align-items:center; gap:6px;
    padding:8px 14px; border-radius:8px;
    font-family:inherit; font-size:12px; font-weight:600;
    border:1px solid var(--border); background:var(--carbon-100); color:var(--bruma);
    cursor:pointer; transition:all .2s;
  }
  .j-btn-accept.primary { background:var(--krypton); color:var(--carbon); border-color:var(--krypton); }
  .j-btn-accept.pulsing { animation:j-btnpulse 1.6s ease-in-out infinite; }
  .j-review-meta {
    margin-left:auto; font-family:'JetBrains Mono',monospace;
    font-size:11px; color:var(--plomo);
  }
  .j-review-meta b { color:var(--krypton); font-weight:500; }
  .j-explain-chip {
    display:inline-flex; align-items:center; gap:6px;
    padding:3px 9px; border-radius:5px;
    background:var(--carbon-300); border:1px solid var(--border);
    font-family:'JetBrains Mono',monospace; font-size:10px;
    color:var(--bruma-muted); margin:0 4px; vertical-align:1px;
  }
  .j-explain-chip .cat { color:var(--krypton); }

  /* ===== STAGE 6 · FINALE ===== */
  .j-finale { position:absolute; inset:45px 0 0 0; padding:30px; display:grid; grid-template-columns:auto 1fr; gap:28px; align-items:center; }
  .j-book {
    width:180px; height:250px; position:relative;
    border-radius:4px 10px 10px 4px;
    background:linear-gradient(135deg, #1C1C1F, #0A0A0B);
    border:1px solid var(--border);
    box-shadow:
      -20px 0 0 -4px #141416,
      -40px 0 0 -8px #1C1C1F,
      0 30px 60px rgba(0,0,0,0.6),
      0 0 40px rgba(212,255,0,0.08);
    padding:28px 18px;
    transform-origin:left center;
    transform:rotateY(var(--book-rot, -18deg));
    transition:transform 1s cubic-bezier(0.2,0.8,0.2,1);
  }
  .j-book::before {
    content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
    background:var(--krypton); opacity:0.7;
  }
  .j-book .bt {
    font-family:'Instrument Serif',serif; font-style:italic;
    font-size:18px; color:var(--krypton); margin-bottom:30px;
    letter-spacing:-0.01em; line-height:1.2;
  }
  .j-book .ba { font-size:9px; color:var(--plomo); letter-spacing:0.1em; text-transform:uppercase; font-family:'JetBrains Mono',monospace; }
  .j-book .bs { position:absolute; bottom:22px; left:18px; font-size:9px; color:var(--plomo); font-family:'JetBrains Mono',monospace; letter-spacing:0.1em; }
  .j-book .bs b { color:var(--krypton); font-weight:500; }
  .j-book-lines { margin-top:20px; }
  .j-book-lines i { display:block; height:2px; background:var(--plomo); opacity:0.3; margin-bottom:5px; border-radius:1px; }
  .j-book-lines i:nth-child(2) { width:85%; }
  .j-book-lines i:nth-child(3) { width:70%; }
  .j-finale-metrics { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .j-metric {
    padding:14px 16px; border:1px solid var(--border); border-radius:10px;
    background:var(--carbon-100);
  }
  .j-metric .n {
    font-size:26px; font-weight:700; letter-spacing:-0.02em;
    color:var(--krypton); font-feature-settings:'tnum'; line-height:1;
  }
  .j-metric .u { font-size:13px; color:var(--plomo-light); font-weight:400; margin-left:2px; }
  .j-metric .l { font-size:11px; color:var(--plomo); font-family:'JetBrains Mono',monospace; letter-spacing:0.05em; text-transform:uppercase; margin-top:6px; }
  .j-metric.wide { grid-column:span 2; }

  /* ===== OUTRO ===== */
  .j-outro {
    min-height:80vh; display:grid; place-items:center;
    padding:100px 24px; text-align:center;
    position:relative; overflow:hidden;
    background:var(--carbon);
  }
  .j-outro::before {
    content:""; position:absolute; inset:0;
    background:radial-gradient(circle at 50% 50%, rgba(212,255,0,0.08), transparent 60%);
    pointer-events:none;
  }
  .j-outro-inner { max-width:780px; position:relative; }
  .j-outro h3 {
    font-size:clamp(36px, 5vw, 60px); line-height:1.05;
    letter-spacing:-0.025em; font-weight:700;
    margin:0 0 18px; text-wrap:balance; color:var(--bruma);
  }
  .j-outro h3 em { font-family:'Instrument Serif',serif; font-style:italic; font-weight:400; color:var(--krypton); }
  .j-outro p { color:var(--plomo-light); font-size:17px; max-width:52ch; margin:0 auto 32px; }
  .j-btn-primary {
    display:inline-flex; align-items:center; gap:8px;
    background:var(--krypton); color:var(--carbon);
    padding:14px 22px; border-radius:12px;
    font-weight:600; font-size:15px; text-decoration:none;
    box-shadow:0 0 0 1px rgba(212,255,0,0.3), 0 10px 32px rgba(212,255,0,0.22);
    transition:transform .15s, box-shadow .15s;
  }
  .j-btn-primary:hover { transform:translateY(-1px); box-shadow:0 0 0 1px rgba(212,255,0,0.5), 0 14px 40px rgba(212,255,0,0.3); }

  /* ===== MOBILE ≤1100px: sticky panel, compact copy, canvas fills height ===== */
  @media(max-width:1100px) {
    .j-stage { height:280vh; }
    .j-stage.short { height:220vh; }
    .j-stage.tall { height:340vh; }

    .j-stage-sticky {
      position:sticky; top:0; height:100svh;
      display:flex; flex-direction:column;
      padding:68px 16px 14px; gap:10px;
      overflow:hidden;
    }

    .j-copy { max-width:100%; flex-shrink:0; width:100%; }
    .j-stage-eyebrow { font-size:10px; letter-spacing:0.12em; margin-bottom:6px; }
    .j-copy h2 { font-size:clamp(18px,5vw,24px); line-height:1.08; margin-bottom:6px; letter-spacing:-0.018em; }
    .j-copy p { font-size:12px; line-height:1.5; margin:0 0 5px; }
    .j-copy p + p { display:none; }
    .j-copy .kvs { margin-top:8px; font-size:10px; gap:4px; }
    .j-copy .kvs .k { min-width:78px; }

    .j-canvas { flex:1; min-height:0; overflow:hidden; width:100%; }
    .j-canvas-bar { padding:9px 13px; font-size:10.5px; }
    .j-canvas-bar .dots i { width:7px; height:7px; }
    .j-canvas-body { padding:14px 16px; }

    .j-doc-float { width:140px; height:185px; padding:16px 12px; top:46%; }
    .j-file-meta { font-size:10.5px; bottom:14px; }
    .j-file-meta .big { font-size:12.5px; }

    .j-analysis { padding:12px 14px; }
    .j-pages-grid { grid-template-columns:repeat(12,1fr); gap:2px; margin-bottom:10px; }
    .j-extractions { grid-template-columns:1fr 1fr; gap:7px; }
    .extract-card { padding:8px 10px; }
    .extract-card .lbl { font-size:8.5px; margin-bottom:3px; }
    .extract-card .val { font-size:11px; line-height:1.4; overflow-wrap:break-word; word-break:break-word; }
    .j-pill { font-size:9px; padding:2px 5px; }
    .j-pill-row { gap:3px; margin-top:3px; }

    .j-spell { padding:12px 14px; }
    .j-spell-text { font-size:12.5px; line-height:1.65; overflow-wrap:break-word; word-break:normal; }
    .j-callout { font-size:10px; padding:7px 9px; margin-top:8px; gap:7px; }
    .j-spell-stats { margin-top:10px; padding-top:9px; gap:5px; }
    .j-spell-stat .n { font-size:18px; }
    .j-spell-stat .l { font-size:9px; }

    .j-editorial { padding:12px 14px; }
    .j-edit-head { font-size:9px; margin-bottom:8px; }
    .j-edit-layers { gap:7px; }
    .edit-layer { padding:9px 11px; gap:10px; }
    .edit-layer .icon { width:28px; height:28px; border-radius:6px; flex-shrink:0; }
    .edit-layer .icon svg { width:13px; height:13px; }
    .edit-layer .title { font-size:12px; margin-bottom:1px; }
    .edit-layer .desc { font-size:9.5px; line-height:1.25; color:var(--plomo); }
    .edit-layer .count { font-size:11px; min-width:28px; flex-shrink:0; white-space:nowrap; }
    .j-voice-quote { font-size:11.5px; padding:8px 10px; margin-top:8px; line-height:1.4; }
    .j-voice-quote b { font-size:8.5px; margin-top:5px; }

    .j-review { padding:10px 12px; }
    .j-review-paragraph { padding:9px 11px; font-size:11.5px; line-height:1.55; margin-bottom:7px; }
    .j-review-paragraph .label { font-size:7.5px; padding:1px 5px; }
    .j-review-actions { flex-wrap:wrap; gap:5px; padding-top:8px; }
    .j-btn-accept, .j-btn-reject { padding:5px 9px; font-size:10px; }
    .j-review-meta { margin-left:0; font-size:9px; order:10; width:100%; }
    .j-explain-chip { font-size:8px; padding:2px 5px; margin:0 1px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

    .j-finale { padding:14px; grid-template-columns:auto 1fr; gap:14px; overflow:hidden; align-items:center; perspective:600px; }
    .j-book { width:100px; height:140px; padding:14px 11px; }
    .j-book .bt { font-size:11px; margin-bottom:8px; }
    .j-book .ba { font-size:7.5px; }
    .j-book .bs { font-size:7px; bottom:10px; left:11px; }
    .j-book-lines { margin-top:8px; }
    .j-finale-metrics { grid-template-columns:1fr 1fr; gap:5px; }
    .j-metric { padding:7px 9px; }
    .j-metric .n { font-size:16px; }
    .j-metric .u { font-size:9.5px; }
    .j-metric .l { font-size:8px; margin-top:2px; }
    .j-metric.wide { grid-column:span 2; }
    .j-metric.wide .n { font-size:12px; flex-wrap:wrap; gap:3px; }

    .j-outro { min-height:60vh; padding:56px 20px; }
    .j-outro h3 { font-size:clamp(24px,6.5vw,36px); }
    .j-outro p { font-size:14px; max-width:100%; }
    .j-btn-primary { padding:12px 18px; font-size:13px; }

    /* Scroll hint — mobile only */
    #j-scroll-hint {
      position:fixed; bottom:26px; left:50%; transform:translateX(-50%);
      z-index:60; display:flex; flex-direction:column; align-items:center; gap:5px;
      font-family:'JetBrains Mono',monospace; font-size:8px; letter-spacing:0.15em;
      text-transform:uppercase; color:rgba(212,255,0,0.55);
      opacity:0; transition:opacity .7s;
      pointer-events:none;
    }
    .j-hint-chevron {
      width:12px; height:12px;
      border-right:1.5px solid currentColor;
      border-bottom:1.5px solid currentColor;
      animation:j-hintbounce 1.4s ease-in-out infinite;
    }
  }

  /* ===== TABLET (481–1100px): more room, slightly larger type ===== */
  @media(min-width:481px) and (max-width:1100px) {
    .j-stage { height:320vh; }
    .j-stage.short { height:250vh; }
    .j-stage.tall { height:400vh; }
    .j-stage-sticky { padding:72px 28px 16px; gap:12px; }
    .j-copy h2 { font-size:clamp(22px,4vw,30px); }
    .j-copy p { font-size:13px; line-height:1.55; }
    .j-copy .kvs { font-size:11px; gap:5px; margin-top:10px; }
    .j-copy .kvs .k { min-width:88px; }
    .j-extractions { grid-template-columns:1fr 1fr; }
    .j-book { width:120px; height:166px; padding:18px 13px; }
    .j-book .bt { font-size:13px; margin-bottom:12px; }
    .j-metric .n { font-size:20px; }
    .j-finale { grid-template-columns:auto 1fr; }
  }

  /* ===== PHONE (≤480px): tightest layout ===== */
  @media(max-width:480px) {
    .j-stage { height:260vh; }
    .j-stage.short { height:200vh; }
    .j-stage.tall { height:310vh; }
    .j-stage-sticky { padding:62px 14px 12px; gap:6px; }
    .j-copy h2 { font-size:clamp(17px,5vw,20px); margin-bottom:4px; }
    .j-copy p { font-size:11px; line-height:1.45; margin:0 0 4px; }
    .j-copy .kvs { margin-top:6px; font-size:9.5px; gap:3px; }
    .j-copy .kvs .k { min-width:66px; }
    .j-canvas-bar .file { display:none; }
    .j-extractions { grid-template-columns:1fr; }

    /* Stage 4: hide verbose desc on smallest screens */
    .edit-layer { padding:7px 9px; gap:8px; }
    .edit-layer .desc { display:none; }
    .edit-layer .title { font-size:11.5px; }
    .j-voice-quote { font-size:11px; }

    /* Stage 5: chips truncate rather than wrap */
    .j-explain-chip { font-size:7.5px; max-width:calc(50% - 4px); }

    /* Stage 6: stack book above metrics on very small */
    .j-finale { grid-template-columns:1fr; justify-items:center; }
    .j-finale-metrics { grid-template-columns:1fr 1fr; width:100%; }
  }
`;

export function Journey() {
  useEffect(() => {
    const PAGES = 54;
    const pagesEl = document.getElementById("j-pages");
    if (pagesEl && pagesEl.children.length === 0) {
      for (let i = 0; i < PAGES; i++) {
        const c = document.createElement("div");
        c.className = "page-cell";
        pagesEl.appendChild(c);
      }
    }

    const progressBar = document.getElementById("j-progress");
    const railSteps = Array.from(document.querySelectorAll(".j-rail-step"));

    function setRail(step: number) {
      railSteps.forEach((el, i) => {
        el.classList.remove("active", "done");
        if (i === step) el.classList.add("active");
        else if (i < step) el.classList.add("done");
      });
    }

    railSteps.forEach((el) => {
      (el as HTMLElement).addEventListener("click", () => {
        const n = parseInt((el as HTMLElement).dataset.step || "0", 10);
        const target = document.querySelector(`[data-stage="${n}"]`);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    function getStageProgress(stage: Element): number {
      const r = stage.getBoundingClientRect();
      const vh = window.innerHeight;
      const total = r.height - vh;
      if (total <= 0) return r.top < 0 ? 1 : 0;
      const traveled = -r.top;
      return Math.max(0, Math.min(1, traveled / total));
    }

    const stages = Array.from(document.querySelectorAll("[data-stage]"));
    const stageByNumber = stages.reduce<Map<number, Element>>((map, stage) => {
      const stageNumber = parseInt(
        (stage as HTMLElement).dataset.stage || "0",
        10
      );
      if (stageNumber > 0) map.set(stageNumber, stage);
      return map;
    }, new Map());

    // Stage 1
    const doc1 = document.getElementById("doc1");
    const beam = document.getElementById("beam");
    const s1status = document.getElementById("s1status") as HTMLElement | null;
    const s1pages = document.getElementById("s1pages");
    const s1size = document.getElementById("s1size");
    const s1prog = document.getElementById("s1prog") as HTMLElement | null;
    const docLines = doc1 ? Array.from(doc1.querySelectorAll(".line")) as HTMLElement[] : [];

    function updateStage1(p: number) {
      if (!doc1 || !beam || !s1status) return;

      // Float doc up
      doc1.style.setProperty("--float", (-40 + p * 40) + "px");

      // Upload progress bar fills 0→100% as p goes 0.05→0.5
      const uploadPct = Math.max(0, Math.min(1, (p - 0.05) / 0.45));
      if (s1prog) s1prog.style.width = uploadPct * 100 + "%";

      // Doc lines brighten progressively as file uploads
      docLines.forEach((line, i) => {
        const threshold = 0.1 + (i / Math.max(1, docLines.length)) * 0.4;
        line.style.background = p > threshold ? "rgba(212,255,0,0.35)" : "";
        line.style.transition = "background .4s";
      });

      // Status text phases
      if (p < 0.18) {
        s1status.style.opacity = "0";
      } else if (p < 0.5) {
        s1status.style.opacity = "1";
        const pct = Math.min(99, Math.floor(uploadPct * 100));
        s1status.innerHTML = `<span class="d"></span> cargando ${pct}%`;
        if (s1pages) s1pages.textContent = "—";
        if (s1size) s1size.textContent = "—";
      } else if (p < 0.62) {
        s1status.innerHTML = `<span class="d"></span> procesando…`;
      } else {
        s1status.innerHTML = `<span class="d"></span> recibido`;
        if (s1pages) s1pages.textContent = "312";
        if (s1size) s1size.textContent = "2,4 MB";
      }

      // Beam on during processing phase
      if (p > 0.3 && p < 0.75) beam.classList.add("on");
      else beam.classList.remove("on");
    }

    // Stage 2
    const pageCells = Array.from(document.querySelectorAll(".page-cell"));
    const extractCards = Array.from(document.querySelectorAll(".extract-card"));
    const s2page = document.getElementById("s2page");

    function updateStage2(p: number) {
      const fillP = Math.min(1, p / 0.55);
      const scannedCount = Math.floor(PAGES * fillP);
      pageCells.forEach((c, i) => {
        c.classList.remove("scanned", "scanning");
        if (i < scannedCount) c.classList.add("scanned");
        else if (i === scannedCount && p < 0.55) c.classList.add("scanning");
      });
      if (s2page) s2page.textContent = String(Math.floor(312 * fillP));
      extractCards.forEach((el, i) => {
        const threshold = 0.55 + i * 0.1;
        if (p > threshold) el.classList.add("in");
        else el.classList.remove("in");
      });
    }

    // Stage 3
    const sErr = document.getElementById("sErr");
    const sProt = document.getElementById("sProt");
    const sConf = document.getElementById("sConf");
    const spellErrs = Array.from(document.querySelectorAll(".j-spell-err"));
    const spellProts = Array.from(document.querySelectorAll(".j-spell-protected"));
    const s3callout = document.querySelector(".j-callout") as HTMLElement | null;

    function revealStaggered(els: Element[], startT: number, p: number) {
      els.forEach((el, i) => {
        const t = startT + (i / Math.max(1, els.length)) * 0.55;
        el.classList.toggle("revealed", p > t);
      });
    }

    function updateStage3(p: number) {
      revealStaggered(spellErrs, 0.08, p);
      revealStaggered(spellProts, 0.15, p);
      if (sErr) sErr.textContent = String(Math.floor(14 * Math.min(1, p / 0.6)));
      if (sProt) sProt.textContent = String(Math.floor(23 * Math.min(1, p / 0.75)));
      if (sConf) sConf.textContent = String(Math.floor(98 * Math.min(1, p / 0.9)));
      // Callout slides in once most errors are marked
      if (s3callout) {
        const show = p > 0.68;
        s3callout.style.opacity = show ? "1" : "0";
        s3callout.style.transform = show ? "translateY(0)" : "translateY(8px)";
        s3callout.style.transition = "opacity .5s, transform .5s";
      }
    }

    // Stage 4
    const editLayers = Array.from(document.querySelectorAll(".edit-layer"));
    const editCounts: [number, number][] = [
      [12, 12],
      [7, 9],
      [4, 6],
      [3, 5],
    ];
    const voiceQuote = document.getElementById("voiceQuote");

    function updateStage4(p: number) {
      const perLayer = 0.22;
      editLayers.forEach((el, i) => {
        const start = i * perLayer;
        const end = start + perLayer;
        const countEl = el.querySelector(".count");
        const [done, total] = editCounts[i];
        el.classList.remove("active", "done");
        if (p < start) {
          if (countEl) countEl.textContent = "— / " + total;
        } else if (p >= start && p < end) {
          el.classList.add("active");
          const t = (p - start) / perLayer;
          if (countEl) countEl.textContent = Math.floor(done * t) + " / " + total;
        } else {
          el.classList.add("done");
          if (countEl) countEl.textContent = done + " / " + total;
        }
      });
      if (voiceQuote) {
        if (p > 0.88) {
          voiceQuote.style.opacity = "1";
          voiceQuote.style.transform = "translateY(0)";
        } else {
          voiceQuote.style.opacity = "0";
          voiceQuote.style.transform = "translateY(10px)";
        }
      }
    }

    // Stage 5
    const btnAccept = document.getElementById("btnAccept") as HTMLButtonElement | null;
    const revOrig = document.getElementById("revOrig") as HTMLElement | null;
    const revSug = document.getElementById("revSug") as HTMLElement | null;
    const revChips = document.getElementById("revChips") as HTMLElement | null;
    const delSpans = Array.from(document.querySelectorAll(".j-del")) as HTMLElement[];
    const insSpans = Array.from(document.querySelectorAll(".j-ins")) as HTMLElement[];
    let acceptTriggered = false;

    function updateStage5(p: number) {
      // Phase 1 (p 0.1→0.25): original paragraph fades in
      if (revOrig) revOrig.style.opacity = String(Math.max(0, Math.min(1, (p - 0.1) / 0.15)));

      // Phase 2 (p 0.25→0.5): del spans get struck through one by one
      delSpans.forEach((span, i) => {
        const t = 0.25 + (i / Math.max(1, delSpans.length)) * 0.25;
        span.classList.toggle("marked", p > t);
      });

      // Phase 3 (p 0.42→0.57): suggested paragraph fades in
      if (revSug) {
        const sp = Math.max(0, Math.min(1, (p - 0.42) / 0.15));
        revSug.style.opacity = String(sp);
        revSug.style.transform = sp < 1 ? `translateY(${(1 - sp) * 10}px)` : "";
      }

      // Phase 4 (p 0.55→0.72): ins spans appear one by one
      insSpans.forEach((span, i) => {
        const t = 0.55 + (i / Math.max(1, insSpans.length)) * 0.17;
        span.classList.toggle("shown", p > t);
      });

      // Phase 5 (p 0.7→0.82): explain chips fade in
      if (revChips) {
        const cp = Math.max(0, Math.min(1, (p - 0.7) / 0.12));
        revChips.style.opacity = String(cp);
        revChips.style.transform = cp < 1 ? `translateY(${(1 - cp) * 6}px)` : "";
      }

      // Phase 6 (p > 0.8): accept button triggers
      if (!btnAccept || !revSug) return;
      if (p > 0.8 && !acceptTriggered) {
        acceptTriggered = true;
        btnAccept.classList.remove("pulsing");
        btnAccept.style.background = "var(--ok)";
        btnAccept.style.borderColor = "var(--ok)";
        btnAccept.innerHTML =
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg> Aceptado';
        revSug.style.boxShadow = "0 0 0 1px rgba(123,228,149,0.3), 0 0 32px rgba(123,228,149,0.08)";
      } else if (p < 0.6 && acceptTriggered) {
        acceptTriggered = false;
        btnAccept.classList.add("pulsing");
        btnAccept.style.background = "";
        btnAccept.style.borderColor = "";
        btnAccept.innerHTML =
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg> Aceptar';
        revSug.style.boxShadow = "";
      }
    }

    // Stage 6
    const book = document.getElementById("book");
    const metricNums = Array.from(document.querySelectorAll(".j-metric .n[data-count]"));

    function updateStage6(p: number) {
      if (book) {
        const rot = -18 + p * 18;
        book.style.setProperty("--book-rot", rot + "deg");
      }
      metricNums.forEach((el) => {
        const target = parseInt((el as HTMLElement).dataset.count || "0", 10);
        const cur = Math.floor(target * Math.min(1, p / 0.7));
        el.textContent = cur.toLocaleString("es-ES");
      });
    }

    const scrollHint = document.getElementById("j-scroll-hint") as HTMLElement | null;

    function onScroll() {
      const docEl = document.documentElement;
      const maxScroll = docEl.scrollHeight - window.innerHeight;
      const scrollP = maxScroll > 0 ? window.scrollY / maxScroll : 0;
      if (progressBar) progressBar.style.width = scrollP * 100 + "%";

      let activeStage = 0;
      for (let i = 0; i < stages.length; i++) {
        const r = stages[i].getBoundingClientRect();
        if (
          r.top <= window.innerHeight * 0.5 &&
          r.bottom > window.innerHeight * 0.5
        ) {
          activeStage = parseInt(
            (stages[i] as HTMLElement).dataset.stage || "0",
            10
          );
          break;
        }
      }
      setRail(activeStage);

      let showHint = false;
      for (let n = 1; n <= 6; n++) {
        const stage = stageByNumber.get(n);
        if (!stage) continue;
        const p = getStageProgress(stage);
        if (p >= 0 && p < 0.06) { showHint = true; }
        if (n === 1) updateStage1(p);
        else if (n === 2) updateStage2(p);
        else if (n === 3) updateStage3(p);
        else if (n === 4) updateStage4(p);
        else if (n === 5) updateStage5(p);
        else if (n === 6) updateStage6(p);
      }
      if (scrollHint) scrollHint.style.opacity = showHint ? "0.85" : "0";
    }

    let ticking = false;

    function handleScroll() {
      if (!ticking) {
        requestAnimationFrame(() => {
          onScroll();
          ticking = false;
        });
        ticking = true;
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    onScroll();

    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return (
    <div className="journey-wrap" id="journey">
      {/* eslint-disable-next-line react/no-danger */}
      <style dangerouslySetInnerHTML={{ __html: JOURNEY_CSS }} />

      {/* Fixed progress bar */}
      <div id="j-progress" />

      {/* Fixed rail */}
      <nav className="j-rail" id="j-rail">
        <div className="j-rail-step" data-step="1">
          <span className="lbl">Cargar</span>
          <span className="num">1</span>
        </div>
        <div className="j-rail-step" data-step="2">
          <span className="lbl">Leer</span>
          <span className="num">2</span>
        </div>
        <div className="j-rail-step" data-step="3">
          <span className="lbl">Ortografía</span>
          <span className="num">3</span>
        </div>
        <div className="j-rail-step" data-step="4">
          <span className="lbl">Editar</span>
          <span className="num">4</span>
        </div>
        <div className="j-rail-step" data-step="5">
          <span className="lbl">Revisar</span>
          <span className="num">5</span>
        </div>
        <div className="j-rail-step" data-step="6">
          <span className="lbl">Entregar</span>
          <span className="num">6</span>
        </div>
      </nav>

      <div className="j-scrolly">

        {/* ====== STAGE 1 · UPLOAD ====== */}
        <section className="j-stage short" data-stage="1" id="stage-1">
          <div className="j-stage-sticky">
            <div className="j-copy">
              <div className="j-stage-eyebrow">
                <span className="ix">01</span> Sueltas tu DOCX
              </div>
              <h2>
                Empiezas donde estabas: con tu <em>manuscrito</em>.
              </h2>
              <p>
                Arrastras el archivo o lo seleccionas. Sin convertir, sin
                aplanar, sin tocar tu maquetación. STYLIA acepta{" "}
                <b>DOCX de hasta 500 páginas</b> —novelas, ensayos, tesis,
                informes— y empieza a trabajar en segundos.
              </p>
              <div className="kvs">
                <div>
                  <span className="k">Formato</span>
                  <span className="v">
                    .docx <b>·</b> estilos, tablas y notas preservadas
                  </span>
                </div>
                <div>
                  <span className="k">Tamaño máx.</span>
                  <span className="v">
                    <b>500 MB</b> · 1000 páginas
                  </span>
                </div>
                <div>
                  <span className="k">Privacidad</span>
                  <span className="v">No entrenamos modelos con tu texto</span>
                </div>
              </div>
            </div>
            <div className="j-canvas">
              <div className="j-canvas-bar">
                <div className="dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span className="file">stylia.app / cargar</span>
                <span
                  className="status"
                  id="s1status"
                  style={{ opacity: 0 }}
                >
                  <span className="d"></span> recibido
                </span>
                <div className="j-upload-progress" id="s1prog" />
              </div>
              <div
                className="j-canvas-body"
                style={{ position: "relative", height: "calc(100% - 45px)" }}
              >
                <div className="j-upload-beam" id="beam"></div>
                <div className="j-doc-float" id="doc1">
                  <div className="page-title">Capítulo 3</div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="line"></div>
                  <div className="tag">DOCX</div>
                </div>
                <div className="j-file-meta">
                  <div className="big">
                    <b id="s1name">manuscrito-novela.docx</b>
                  </div>
                  <div style={{ marginTop: "6px" }}>
                    <span id="s1pages">—</span> páginas ·{" "}
                    <span id="s1size">—</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====== STAGE 2 · ANALYSIS ====== */}
        <section className="j-stage tall" data-stage="2" id="stage-2">
          <div className="j-stage-sticky">
            <div className="j-copy">
              <div className="j-stage-eyebrow">
                <span className="ix">02</span> Lo lee entero, no por trozos
              </div>
              <h2>
                Antes de corregir, STYLIA <em>entiende</em>.
              </h2>
              <p>
                Recorre página por página. Identifica capítulos, personajes,
                lugares, términos técnicos y tu voz. Deduce el género, el
                público y el tono. Todo eso alimenta las correcciones
                siguientes — sin este paso, cualquier corrector es ciego al
                contexto.
              </p>
              <p>
                Los <b>términos protegidos</b> (nombres propios, marcas,
                neologismos tuyos) quedan blindados desde aquí. No se tocan
                en ninguna pasada.
              </p>
              <div className="kvs">
                <div>
                  <span className="k">Modelo</span>
                  <span className="v">lectura contextual multi-pasada</span>
                </div>
                <div>
                  <span className="k">Salida</span>
                  <span className="v">
                    <b>resumen + glosario</b> por documento
                  </span>
                </div>
                <div>
                  <span className="k">Tiempo típico</span>
                  <span className="v">12–20 s para 300 páginas</span>
                </div>
              </div>
            </div>
            <div className="j-canvas">
              <div className="j-canvas-bar">
                <div className="dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span className="file">análisis editorial previo</span>
                <span className="status" id="s2status">
                  <span className="d"></span> leyendo{" "}
                  <span id="s2page">0</span>/312
                </span>
              </div>
              <div className="j-analysis">
                <div className="j-pages-grid" id="j-pages"></div>
                <div className="j-extractions">
                  <div
                    className="extract-card big"
                    data-ex="0"
                  >
                    <div className="lbl">Género detectado</div>
                    <div className="val">
                      <b>Novela · realismo contemporáneo</b> · público adulto ·
                      tono introspectivo
                    </div>
                  </div>
                  <div className="extract-card" data-ex="1">
                    <div className="lbl">Personajes</div>
                    <div className="val">
                      <div className="j-pill-row">
                        <span className="j-pill">Elena</span>
                        <span className="j-pill">Mateo</span>
                        <span className="j-pill">la abuela</span>
                        <span className="j-pill">Don Ernesto</span>
                      </div>
                    </div>
                  </div>
                  <div className="extract-card" data-ex="2">
                    <div className="lbl">Lugares</div>
                    <div className="val">
                      <div className="j-pill-row">
                        <span className="j-pill muted">Cartagena</span>
                        <span className="j-pill muted">el muelle</span>
                        <span className="j-pill muted">Bogotá</span>
                      </div>
                    </div>
                  </div>
                  <div
                    className="extract-card big"
                    data-ex="3"
                  >
                    <div className="lbl">
                      Términos protegidos{" "}
                      <span style={{ color: "var(--krypton)" }}>
                        (no se modifican)
                      </span>
                    </div>
                    <div className="val">
                      <div className="j-pill-row">
                        <span className="j-pill">Elena Vargas</span>
                        <span className="j-pill">Casa de los Acantilados</span>
                        <span className="j-pill">Feria del Libro</span>
                        <span className="j-pill">Los Bienaventurados</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====== STAGE 3 · SPELLING ====== */}
        <section className="j-stage" data-stage="3" id="stage-3">
          <div className="j-stage-sticky">
            <div className="j-copy">
              <div className="j-stage-eyebrow">
                <span className="ix">03</span> Pasada ortográfica
              </div>
              <h2>
                Primero lo obvio: <em>ortografía</em> y gramática.
              </h2>
              <p>
                Una capa determinista —no IA— revisa cada párrafo contra las
                reglas del español: tildes, concordancia, puntuación,
                dequeísmos, mayúsculas. Es rápido, gratuito y muy preciso.
              </p>
              <p>
                Lo importante: STYLIA <b>descarta automáticamente</b> los
                falsos positivos sobre tus términos protegidos. Si llamaste
                «Bienaventurados» a tu grupo, el corrector no te lo va a
                subrayar.
              </p>
              <div className="kvs">
                <div>
                  <span className="k">Motor</span>
                  <span className="v">LanguageTool ES · offline</span>
                </div>
                <div>
                  <span className="k">Coste</span>
                  <span className="v">cero tokens de IA</span>
                </div>
                <div>
                  <span className="k">Precisión típica</span>
                  <span className="v">
                    <b>98 %</b> sobre reglas RAE
                  </span>
                </div>
              </div>
            </div>
            <div className="j-canvas">
              <div className="j-canvas-bar">
                <div className="dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span className="file">capítulo 3 · pasada 1</span>
                <span className="status">
                  <span className="d"></span> revisado
                </span>
              </div>
              <div className="j-spell">
                <div className="j-spell-text">
                  Elena caminaba calle abajo cuando{" "}
                  <span className="j-spell-err" data-tip="falta coma vocativa">
                    Mateo
                  </span>{" "}
                  la llamó desde el muelle.{" "}
                  <span className="j-spell-protected">
                    La Casa de los Acantilados
                  </span>{" "}
                  quedaba a dos cuadras, pero ella no tenía{" "}
                  <span className="j-spell-err" data-tip="acentuación">
                    prisa.
                  </span>{" "}
                  <span className="j-spell-err" data-tip="dequeísmo">
                    Pensó de que
                  </span>{" "}
                  aún era temprano,{" "}
                  <span className="j-spell-err" data-tip="coma ausente">
                    se sentó en un banco y
                  </span>{" "}
                  lo esperó. El mar olía como siempre, a sal y a{" "}
                  <span className="j-spell-protected">Los Bienaventurados</span>
                  , aquella{" "}
                  <span className="j-spell-err" data-tip="concordancia">
                    banda musicales
                  </span>{" "}
                  que Mateo escuchaba los sábados.
                </div>
                <div className="j-callout">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  <div>
                    Se detectaron <b>posibles errores</b> sobre{" "}
                    <b>«Casa de los Acantilados»</b> y{" "}
                    <b>«Los Bienaventurados»</b>, pero están en tu lista de
                    términos protegidos. <b>Se descartaron automáticamente.</b>
                  </div>
                </div>
                <div className="j-spell-stats">
                  <div className="j-spell-stat">
                    <div className="n err" id="sErr">
                      0
                    </div>
                    <div className="l">errores reales</div>
                  </div>
                  <div className="j-spell-stat">
                    <div className="n proj" id="sProt">
                      0
                    </div>
                    <div className="l">descartados · protegidos</div>
                  </div>
                  <div className="j-spell-stat">
                    <div className="n ok" id="sConf">
                      0
                    </div>
                    <div className="l">% confianza</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====== STAGE 4 · EDITORIAL ====== */}
        <section className="j-stage tall" data-stage="4" id="stage-4">
          <div className="j-stage-sticky">
            <div className="j-copy">
              <div className="j-stage-eyebrow">
                <span className="ix">04</span> Análisis editorial profundo
              </div>
              <h2>
                Ahora sí: <em>estilo</em>, claridad, voz.
              </h2>
              <p>
                Con el documento ya entendido, STYLIA aplica cuatro capas de
                análisis editorial profesional. No es un «revisar todo de una
                vez»: cada capa busca algo distinto y se nutre del análisis
                previo.
              </p>
              <p>
                Y sobre todo: <b>preserva tu voz</b>. Si una frase es rara
                pero es tuya, no la toca. El principio es el mismo que sigue
                un corrector humano: «corrige todo menos el estilo del autor».
              </p>
              <div className="kvs">
                <div>
                  <span className="k">Capas</span>
                  <span className="v">léxico · claridad · coherencia · ritmo</span>
                </div>
                <div>
                  <span className="k">Contexto</span>
                  <span className="v">ventana de 3 párrafos + glosario</span>
                </div>
                <div>
                  <span className="k">Verificación</span>
                  <span className="v">
                    <b>5 controles</b> de calidad por párrafo
                  </span>
                </div>
              </div>
            </div>
            <div className="j-canvas">
              <div className="j-canvas-bar">
                <div className="dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span className="file">capítulo 3 · pasada 2</span>
                <span className="status">
                  <span className="d"></span> analizando
                </span>
              </div>
              <div className="j-editorial">
                <div className="j-edit-head">
                  Análisis editorial ·{" "}
                  <b>perfil: novela / tono introspectivo</b>
                </div>
                <div className="j-edit-layers">
                  <div className="edit-layer" data-layer="0">
                    <div className="icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5z" />
                      </svg>
                    </div>
                    <div className="content">
                      <div className="title">Léxico</div>
                      <div className="desc">muletillas, repeticiones y palabras manidas</div>
                    </div>
                    <div className="count">— / —</div>
                  </div>
                  <div className="edit-layer" data-layer="1">
                    <div className="icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="3" />
                        <path d="M12 1v6M12 17v6M4.22 4.22l4.24 4.24M15.54 15.54l4.24 4.24M1 12h6M17 12h6M4.22 19.78l4.24-4.24M15.54 8.46l4.24-4.24" />
                      </svg>
                    </div>
                    <div className="content">
                      <div className="title">Claridad</div>
                      <div className="desc">frases largas, redundancias y ambigüedad</div>
                    </div>
                    <div className="count">— / —</div>
                  </div>
                  <div className="edit-layer" data-layer="2">
                    <div className="icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17 3h4v4M21 3l-7 7M7 21H3v-4M3 21l7-7M7 3H3v4M3 3l7 7M17 21h4v-4M21 21l-7-7" />
                      </svg>
                    </div>
                    <div className="content">
                      <div className="title">Coherencia</div>
                      <div className="desc">transiciones, tiempos verbales y terminología</div>
                    </div>
                    <div className="count">— / —</div>
                  </div>
                  <div className="edit-layer" data-layer="3">
                    <div className="icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 18V5l12-2v13M9 9l12-2M6 21a3 3 0 1 1 0-6 3 3 0 0 1 0 6zM18 19a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
                      </svg>
                    </div>
                    <div className="content">
                      <div className="title">Ritmo y voz</div>
                      <div className="desc">cadencia, variedad de oraciones, tono del autor</div>
                    </div>
                    <div className="count">— / —</div>
                  </div>
                </div>
                <div
                  className="j-voice-quote"
                  id="voiceQuote"
                  style={{ opacity: 0, transform: "translateY(10px)", transition: "all .6s" }}
                >
                  «STYLIA conserva tu voz. Solo cambia lo que estorba.»
                  <b>Principio de corrección</b>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====== STAGE 5 · REVIEW ====== */}
        <section className="j-stage tall" data-stage="5" id="stage-5">
          <div className="j-stage-sticky">
            <div className="j-copy">
              <div className="j-stage-eyebrow">
                <span className="ix">05</span> Tú decides, párrafo a párrafo
              </div>
              <h2>
                STYLIA propone. Tú <em>apruebas</em>.
              </h2>
              <p>
                Cada sugerencia llega con <b>categoría</b>,{" "}
                <b>explicación</b> y <b>nivel de confianza</b>. Aceptas con
                un clic, descartas con otro, o reescribes a mano. Ningún
                cambio se aplica sin tu visto bueno.
              </p>
              <p>
                Lo subrayado en rojo desaparece; lo verde se integra. El
                formato original se mantiene intacto todo el tiempo.
              </p>
              <div className="kvs">
                <div>
                  <span className="k">Interacción</span>
                  <span className="v">aprobar · descartar · editar</span>
                </div>
                <div>
                  <span className="k">Atajos</span>
                  <span className="v">A aceptar · D descartar · → siguiente</span>
                </div>
                <div>
                  <span className="k">Histórico</span>
                  <span className="v">cada decisión queda registrada</span>
                </div>
              </div>
            </div>
            <div className="j-canvas">
              <div className="j-canvas-bar">
                <div className="dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span className="file">revisión de cambios · 3 / 47</span>
                <span className="status">
                  <span className="d"></span> sugerencia abierta
                </span>
              </div>
              <div className="j-review">
                <div className="j-review-paragraph" id="revOrig" style={{ opacity: 0, transition: "opacity .5s" }}>
                  <span className="label">Original</span>
                  <span className="j-del">
                    Caminaba lentamente por la calle, cuando de repente
                  </span>{" "}
                  escuchó unos pasos detrás de él. Se{" "}
                  <span className="j-del">dio la vuelta rápidamente</span> y no
                  vio a nadie, pero{" "}
                  <span className="j-del">estaba completamente seguro de que</span>{" "}
                  alguien lo seguía. «¿Quién anda ahí?»{" "}
                  <span className="j-del">dijo</span> con voz{" "}
                  <span className="j-del">temblorosa</span>.
                </div>
                <div className="j-review-paragraph" id="revSug" style={{ opacity: 0, transform: "translateY(10px)", transition: "opacity .5s, transform .5s" }}>
                  <span className="label">Sugerido</span>
                  <span className="j-ins">Caminaba calle abajo</span> cuando{" "}
                  <span className="j-ins">oyó</span> pasos detrás. Se{" "}
                  <span className="j-ins">giró</span> y no vio a nadie, pero{" "}
                  <span className="j-ins">supo</span> que alguien lo seguía.
                  «¿Quién anda ahí?» <span className="j-ins">susurró</span>.
                </div>
                <div id="revChips" style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px", opacity: 0, transition: "opacity .4s, transform .4s", transform: "translateY(6px)" }}>
                  <span className="j-explain-chip">
                    <span className="cat">léxico</span> · 3 adverbios -mente
                    consecutivos
                  </span>
                  <span className="j-explain-chip">
                    <span className="cat">claridad</span> · «estaba completamente
                    seguro» redundante
                  </span>
                  <span className="j-explain-chip">
                    <span className="cat">ritmo</span> · verbo de habla genérico
                  </span>
                </div>
                <div className="j-review-actions">
                  <button className="j-btn-accept primary pulsing" id="btnAccept">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                      <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Aceptar
                  </button>
                  <button className="j-btn-reject">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
                    </svg>
                    Descartar
                  </button>
                  <button className="j-btn-reject">Editar</button>
                  <div className="j-review-meta">
                    confianza <b>92 %</b> · tecla <b>A</b> para aceptar
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====== STAGE 6 · FINALE ====== */}
        <section className="j-stage short" data-stage="6" id="stage-6">
          <div className="j-stage-sticky">
            <div className="j-copy">
              <div className="j-stage-eyebrow">
                <span className="ix">06</span> Libro corregido
              </div>
              <h2>
                Descargas el DOCX. <em>Listo.</em>
              </h2>
              <p>
                El archivo vuelve con el mismo formato, con las correcciones
                aplicadas y con un informe detallado: qué se cambió, por qué,
                cuánto tardó, cuánto costó. Todo trazable.
              </p>
              <p>
                Los editores que lo usan terminan un manuscrito de 200 páginas{" "}
                <b>en una tarde</b> en lugar de tres días. No porque trabajen
                menos —sino porque dejan de pelear con el texto fácil.
              </p>
              <div className="kvs">
                <div>
                  <span className="k">Entrega</span>
                  <span className="v">DOCX + PDF + reporte JSON</span>
                </div>
                <div>
                  <span className="k">Coste medio</span>
                  <span className="v">
                    <b>$0,08</b> por libro de 100 páginas
                  </span>
                </div>
                <div>
                  <span className="k">Soporte</span>
                  <span className="v">control de cambios compatible con Word</span>
                </div>
              </div>
            </div>
            <div className="j-canvas">
              <div className="j-canvas-bar">
                <div className="dots">
                  <i></i>
                  <i></i>
                  <i></i>
                </div>
                <span className="file">entrega final</span>
                <span className="status">
                  <span className="d"></span> listo para descargar
                </span>
              </div>
              <div className="j-finale">
                <div className="j-book" id="book">
                  <div className="bt">La casa de los acantilados</div>
                  <div className="ba">Elena Vargas</div>
                  <div className="j-book-lines">
                    <i></i>
                    <i></i>
                    <i></i>
                  </div>
                  <div className="bs">
                    312 pp · <b>revisado por STYLIA</b>
                  </div>
                </div>
                <div className="j-finale-metrics">
                  <div className="j-metric">
                    <div className="n" data-count="18">0</div>
                    <div className="l">min · duración total</div>
                  </div>
                  <div className="j-metric">
                    <div className="n" data-count="312">0</div>
                    <div className="l">páginas revisadas</div>
                  </div>
                  <div className="j-metric">
                    <div className="n" data-count="1247">0</div>
                    <div className="l">sugerencias generadas</div>
                  </div>
                  <div className="j-metric">
                    <div className="n" data-count="89">
                      <span className="u"></span>
                    </div>
                    <div className="l">% aceptadas por ti</div>
                  </div>
                  <div className="j-metric wide">
                    <div
                      className="n"
                      style={{ display: "flex", alignItems: "baseline", gap: "6px" }}
                    >
                      17
                      <span className="u">pp / min</span>
                      <span
                        style={{
                          fontSize: "12px",
                          color: "var(--plomo-light)",
                          marginLeft: "auto",
                          fontFamily: "'Inter',sans-serif",
                          fontWeight: 400,
                        }}
                      >
                        velocidad de revisión sostenida
                      </span>
                    </div>
                    <div className="l">— tu editor humano es más rápido ahora</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

      </div>
      {/* /.j-scrolly */}

      {/* ====== OUTRO ====== */}
      <section className="j-outro">
        <div className="j-outro-inner">
          <h3>
            Seis etapas. Una <em>tarde</em>. Tu libro listo.
          </h3>
          <p>
            Esto es exactamente lo que pasa cuando sueltas tu DOCX en STYLIA.
            Sin cajas negras, sin jerga, sin sorpresas. Pruébalo con tu próximo
            manuscrito.
          </p>
          <a href="#" className="j-btn-primary">
            Probar STYLIA gratis
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path
                d="M5 12h14M13 5l7 7-7 7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
          <div
            style={{
              marginTop: "18px",
              fontSize: "13px",
              color: "var(--plomo)",
            }}
          >
            Corrige tu primer DOCX en 2 minutos · sin tarjeta
          </div>
        </div>
      </section>

      {/* Scroll hint — mobile only, JS controls opacity */}
      <div id="j-scroll-hint" aria-hidden="true">
        <div className="j-hint-chevron" />
        <span>Scroll</span>
      </div>
    </div>
  );
}
