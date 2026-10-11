/* Shared by the editor and local API. No model, network or project writes. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.KlipeAssist = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const tracks = {video: 'videoClips', title: 'titles', broll: 'brolls', zoom: 'zooms',
    caption: 'captions', sfx: 'sfx', music: 'musicTracks', shape: 'shapes'};
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  const overlap = (a, b) => a.startSec < b.endSec && b.startSec < a.endSec;
  const round = n => Math.round(n * 1000) / 1000;
  const norm = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const hash = value => {
    let n = 2166136261;
    for (const c of JSON.stringify(value)) n = Math.imul(n ^ c.charCodeAt(0), 16777619);
    return (n >>> 0).toString(16);
  };
  function snapshot(state, config) {
    const result = {...config, videoSrc: state.videoSrc, videoDuration: state.videoDuration,
      width: state.width || config.width, height: state.height || config.height, fps: state.fps};
    for (const [type, key] of Object.entries(tracks)) {
      result[key] = state.tracks.filter(t => t.type === type).flatMap(t => t.clips.map(c =>
        ({...c, _hidden: t.visible === false, _locked: !!t.locked, _muted: !!t.muted})));
    }
    return JSON.parse(JSON.stringify(result));
  }
  function cues(config, transcript) {
    // Captions in the current editor are already on the edited time axis.
    const existing = (config.captions || []).filter(c => finite(c.startSec) && finite(c.endSec));
    if (existing.length) return existing.filter(c => !c._hidden && c.text).sort((a,b) => a.startSec-b.startSec);
    const segs = Array.isArray(transcript) ? transcript : transcript?.segments || [];
    const keeps = config.keepRanges || [];
    const ranges = keeps.length ? keeps : [[0, config.videoDuration]];
    let offset = 0;
    const out = [];
    for (const range of ranges) {
      if (!Array.isArray(range) || !finite(range[0]) || !finite(range[1]) || range[1] <= range[0]) continue;
      const [lo, hi] = range;
      for (const seg of segs) {
        if (!finite(seg.start) || !finite(seg.end) || seg.end <= lo || seg.start >= hi) continue;
        const words = (seg.words || []).filter(w => w.start >= lo && w.end <= hi).map(w =>
          ({...w, text: w.text || w.word, start: round(offset+w.start-lo), end: round(offset+w.end-lo)}));
        // Never reintroduce removed speech by copying a partially cut sentence.
        if (!words.length && (seg.start < lo || seg.end > hi)) continue;
        out.push({startSec: round(offset+Math.max(lo,seg.start)-lo),
          endSec: round(offset+Math.min(hi,seg.end)-lo),
          text: words.length ? words.map(w => w.text.trim()).join(' ') : seg.text, words});
      }
      offset += hi-lo;
    }
    return out.filter(c => c.text && c.endSec > c.startSec && c.startSec < config.videoDuration)
      .sort((a,b) => a.startSec-b.startSec);
  }
  function inspect(config, assets = {}, faces = []) {
    const issues = [];
    const add = (severity, code, text, item = {}) => issues.push({severity, code, text,
      clipId: item.id, startSec: finite(item.startSec) ? item.startSec : 0});
    if (!finite(config.videoDuration) || config.videoDuration <= 0) add('error','duration','Duracao do projeto invalida.');
    if (!finite(config.fps) || config.fps <= 0) add('error','fps','FPS do projeto invalido.');
    for (const key of Object.values(tracks)) {
      const seen = new Set();
      for (const c of config[key] || []) {
        if (!finite(c.startSec) || !finite(c.endSec) || c.endSec <= c.startSec || c.startSec < 0)
          add('error','interval',`${key}: intervalo invalido.`,c);
        if (c.endSec > config.videoDuration + 1/(config.fps || 30)) add('warning','overflow',`${key}: termina depois do video.`,c);
        if (seen.has(c.id) && c.id) add('error','duplicate',`${key}: identificador repetido.`,c);
        seen.add(c.id);
        if (c._hidden) continue;
        if ((key === 'captions' || key === 'titles') && !String(c.text || '').trim() && !c.cena)
          add('warning','empty-text','Titulo ou legenda sem texto.',c);
        if (c.opacity === 0) add('warning','invisible','Clipe com opacidade zero.',c);
        if (c.src && assets[c.src]?.error) add('error','media',assets[c.src].error,c);
        const m = assets[c.src];
        if (m?.duration && ['brolls','sfx','musicTracks'].includes(key) &&
            (c.srcStart || 0)+(c.endSec-c.startSec)*(c.speed || 1) > m.duration + .1)
          add('warning','short-source','O trecho ultrapassa a duracao da midia.',c);
        if (key === 'brolls' && /\.(png|jpg|jpeg|webp)$/i.test(c.src || '') && !c.generated)
          add('info','still','Foto: conferir movimento e enquadramento.',c);
        if (key === 'captions' && String(c.text || '').length/(c.endSec-c.startSec) > 24)
          add('warning','reading-speed','Legenda rapida: mais de 24 caracteres por segundo.',c);
        if (key === 'titles' && c.style === 'cena' && c.cena?.params?.assistantTitle) {
          const band = titleBand(config,c);
          if (faces.some(f => overlap(c,f) && rectHit(band,f)))
            add('warning','face-collision','Titulo sugerido cruza um rosto detectado.',c);
        }
      }
    }
    if (config.videoSrc && assets[config.videoSrc]?.error) add('error','source',assets[config.videoSrc].error);
    if (assets[config.videoSrc]?.hasAudio === false) add('info','no-audio','Video principal sem trilha de audio.');
    for (const c of config.videoClips || []) if (c.muted || c._muted || c.volume === 0)
      add('info','muted','Audio do video principal silenciado neste trecho.',c);
    if ((config.brolls || []).some(c => c.foreground) && (config.zooms || []).length)
      add('warning','mask-zoom','Ha recorte de pessoa e zoom no projeto. Confira o alinhamento ou regenere o recorte.');
    for (const key of ['titles','zooms']) {
      const list = (config[key] || []).filter(c => !c._hidden).slice().sort((a,b)=>a.startSec-b.startSec);
      for (let i=1;i<list.length;i++) if (overlap(list[i-1],list[i]))
        add('info','overlap',key === 'zooms' ? 'Zooms sobrepostos: o primeiro tem prioridade.' : 'Titulos simultaneos: conferir a composicao.',list[i]);
    }
    if (!faces.length) add('info','faces-unchecked','Rostos ainda nao analisados.');
    return issues;
  }
  function rectHit(a,b) {
    return a.x < b.x+b.w && b.x < a.x+a.w && a.y < b.y+b.h && b.y < a.y+a.h;
  }
  function titleBand(config, clip) {
    const y = .5 - (clip.cena.params.y || 0)/(config.height || 1080);
    return {x:.08,y:y-.065,w:.84,h:.13};
  }
  function freeY(config, startSec, endSec, faces) {
    const blocked = faces.filter(f => overlap({startSec,endSec},f));
    for (const cy of [.72,.23,.51,.84]) {
      if (!blocked.some(f=>rectHit({x:.06,y:cy-.08,w:.88,h:.16},f)))
        return Math.round((.5-cy)*(config.height || 1080));
    }
    return null;
  }
  function title(config, cue, faces) {
    const y = freeY(config,cue.startSec,cue.endSec,faces);
    if (y === null) return null;
    const text = cue.text.trim();
    const duration = Math.min(3.8,cue.endSec-cue.startSec);
    const size = Math.round(Math.min(config.width*.066,config.height*.06));
    return {startSec:cue.startSec,endSec:round(cue.startSec+duration),text,style:'cena',
      cena:{duracao:duration,params:{titulo:text,y,assistantTitle:true},camadas:[
        {tipo:'texto',texto:'@titulo',fonte:'Arial',peso:800,tamanho:size,largura_max:'84%',
          alinha:'center',cor:'#FFFFFF',y:[[0,y-60,'outCubic'],[.32,y]],
          opacidade:[[0,0],[.12,1],[Math.max(.13,duration-.2),1],[duration,0]],
          sombra:[{x:0,y:2,blur:5,cor:'#00000099'}]}
      ]}};
  }
  function plan(config, transcript, assets = {}, faces = []) {
    const speech = cues(config,transcript);
    const suggestions = [];
    const add = (type,label,clip,reason) => {
      const id = 'assist-'+hash([type,clip.startSec,clip.endSec,clip.text || clip.src || label]);
      const key = tracks[type];
      if (key && (config[key] || []).some(c => c.id === id || overlap(c,clip))) return;
      suggestions.push({id,type,label,reason,clip:{...clip,id}});
    };
    let lastMotion = -10;
    const terms = /\b(importante|atencao|cuidado|primeiro|segundo|terceiro|resultado|agora|dica|lembre|preco|desconto)\b/;
    for (let i=0;i<speech.length;i++) {
      const c = speech[i];
      if (c.endSec-c.startSec < .9 || c.text.length > 100) continue;
      const special = terms.test(norm(c.text)) || /\d/.test(c.text);
      if (!(special || i === 0) || c.startSec-lastMotion < 6) continue;
      const t = title(config,c,faces);
      if (t) add('title',c.text,t,'Destaque ligado a fala.');
      add('zoom','Aproximacao suave',{startSec:c.startSec,endSec:Math.min(config.videoDuration,c.endSec),
        direction:'breathe',intensity:8,originY:40},'Aproxima e retorna durante a frase.');
      const match = /\b(preco|desconto|reais|venda)\b/.test(norm(c.text)) ? /cash|coin|money|caixa/i : /pop|click|tick/i;
      const sound = Object.entries(assets).find(([src,m]) => /^sfx\//.test(src) && match.test(src) && m.duration > 0 && m.duration <= 3 && !m.error);
      if (sound) add('sfx','SFX: '+sound[0].split('/').pop(),{startSec:c.startSec,
        endSec:round(Math.min(config.videoDuration,c.startSec+sound[1].duration)),src:sound[0],
        volume:.18,fadeIn:.01,fadeOut:.08,baseDurationSec:sound[1].duration},'Som da biblioteca local, com duracao medida.');
      lastMotion = c.startSec;
    }
    let end = 0;
    for (const c of speech) {
      if (c.startSec-end >= 1.2) add('review','Conferir pausa',{startSec:round(end),endSec:c.startSec},'Intervalo sem fala na transcricao; confira o audio antes de cortar.');
      end = Math.max(end,c.endSec);
    }
    return {version:1,signature:hash(config),speechCount:speech.length,suggestions,
      issues:inspect(config,assets,faces),faces,assets};
  }
  return {snapshot,cues,inspect,plan,title,freeY,hash,tracks,overlap};
});
