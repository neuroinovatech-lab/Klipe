(function(){
  'use strict';
  function ranges(start,end,duration,fps=30){
    if(![start,end,duration,fps].every(Number.isFinite)||fps<1||start<0||end<=start||end>duration||end-start>600)
      throw Error('Escolha um trecho de ate 10 minutos dentro do video.');
    const first=Math.max(0,Math.ceil(start*fps-1e-6)),last=Math.floor(end*fps+1e-6),step=Math.floor(30*fps);
    if(last<=first)throw Error('O trecho precisa ter pelo menos um quadro.');
    const out=[];for(let f=first;f<last;f+=step)out.push([f/fps,Math.min(last,f+step)/fps]);return out;
  }
  if(typeof module==='object'&&module.exports){module.exports={ranges};return;}
  const A=window.KlipeAssist;
  const state=()=>A.snapshot(NLE.sm.getState(),NLE.config||{});
  let busy=false,pending=null,cancelled=false;
  let selectedId=null;
  const panel=document.createElement('section');panel.id='bg-remove-panel';
  panel.setAttribute('aria-label','Remover fundo');
  panel.innerHTML='<header><strong>Remover fundo</strong></header>'+
    '<fieldset><legend>Composi\u00e7\u00e3o</legend><label><input type="radio" name="bg-mode" value="remove" checked> Remover cen\u00e1rio</label><label><input type="radio" name="bg-mode" value="foreground"> Pessoa na frente dos t\u00edtulos</label></fieldset>'+
    '<div class="bg-range"><label>In\u00edcio (s)<input id="bg-start" type="number" min="0" step="0.1"></label><label>Fim (s)<input id="bg-end" type="number" min="0" step="0.1"></label></div>'+
    '<label>Limpeza da m\u00e1scara <output id="bg-strength-value">50</output><input id="bg-strength" type="range" min="0" max="100" value="50" step="5"></label>'+
    '<label>Suavidade da borda <output id="bg-feather-value">0.6</output><input id="bg-feather" type="range" min="0" max="4" value="0.6" step="0.2"></label>'+
    '<progress id="bg-progress" max="1" value="0" hidden></progress><p id="bg-status" role="status" aria-live="polite"></p>'+
    '<footer><button type="button" id="bg-cancel" hidden>Cancelar</button><button type="button" id="bg-generate">Gerar recorte</button><button type="button" id="bg-apply" disabled>Aplicar na timeline</button></footer>';
  // Keep the same controls and running job when Properties rebuilds its DOM.
  const $=id=>panel.querySelector('#'+id);
  const status=t=>{$('bg-status').textContent=t;};
  const controls=[...panel.querySelectorAll('input')];
  function setBusy(value){busy=value;controls.forEach(c=>c.disabled=value);$('bg-generate').disabled=value;$('bg-apply').disabled=value||!pending;$('bg-cancel').hidden=!value;}
  for(const control of controls)control.addEventListener('input',()=>{
    if(pending){pending=null;setBusy(false);status('Ajustes alterados. Gere o recorte novamente.');}
  });
  for(const name of ['strength','feather'])$('bg-'+name).oninput=()=>{$('bg-'+name+'-value').value=$('bg-'+name).value;};
  $('bg-cancel').onclick=()=>{cancelled=true;status('Cancelando ao concluir o trecho em processamento...');};
  async function json(url,options){const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw Error(data.error||'Falha no recorte.');return data;}
  async function job(payload){
    const initial=await json('/api/assistant/person',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    for(;;){await new Promise(r=>setTimeout(r,900));const j=await json('/api/assistant/job?id='+encodeURIComponent(initial.id));
      if(j.status==='error')throw Error(j.error);if(j.status==='done')return j.result;}
  }
  $('bg-generate').onclick=async()=>{
    if(busy)return;pending=null;cancelled=false;setBusy(true);
    try{
      const config=state(),signature=A.hash(config),parts=ranges(Number($('bg-start').value),Number($('bg-end').value),config.videoDuration,config.fps);
      const mode=panel.querySelector('input[name="bg-mode"]:checked').value;
      const results=[];$('bg-progress').hidden=false;$('bg-progress').max=parts.length;$('bg-progress').value=0;
      for(let i=0;i<parts.length;i++){
        status('Processando trecho '+(i+1)+' de '+parts.length+'...');
        const result=await job({config,startSec:parts[i][0],endSec:parts[i][1],mode,strength:Number($('bg-strength').value),feather:Number($('bg-feather').value)});
        if(cancelled){status('Cancelado. A timeline nao foi alterada.');return;}
        results.push(result);$('bg-progress').value=i+1;
      }
      pending={signature,results};status('Recorte pronto.');
    }catch(e){status(e.message);}finally{setBusy(false);}
  };
  $('bg-apply').onclick=()=>{
    if(!pending||busy)return;
    if(A.hash(state())!==pending.signature){status('A timeline mudou. Gere novamente para manter o sincronismo.');pending=null;setBusy(false);return;}
    const s=NLE.sm.getState();NLE.sm.pushUndo();
    const clips=pending.results.flatMap(r=>[r.background,r.clip].filter(Boolean));
    // Only replace layers owned by this tool, and only when fully covered.
    const start=Math.min(...clips.map(c=>c.startSec)),end=Math.max(...clips.map(c=>c.endSec));
    for(const t of s.tracks)if(t.type==='broll'&&!t.locked)t.clips=t.clips.filter(c=>!(String(c.id).startsWith('bgremove-')&&c.startSec>=start&&c.endSec<=end));
    for(const foreground of [false,true]){
      const layer=clips.filter(c=>!!c.foreground===foreground).map(c=>({...c,id:'bgremove-'+crypto.randomUUID()}));
      if(!layer.length)continue;
      s.tracks.push({id:'track-bgremove-'+crypto.randomUUID(),type:'broll',name:foreground?'Pessoa recortada':'Fundo do recorte',visible:true,muted:false,locked:false,clips:layer});
    }
    NLE.renderer.markDirty();NLE.sm.notify();NLE.renderProperties();NLE.syncPlayerFromState();NLE.resizeTimeline();
    NLE.sm.dispatch('SET_PLAYHEAD',start);NLE.preview?.p?.seek(start);
    pending=null;setBusy(false);status('Aplicado. Alteracoes ainda nao salvas.');NLE.showToast('Recorte aplicado. Save para salvar; Ctrl+Z para desfazer.');
  };
  NLE.backgroundRemoval={mount(host){
    if(!host)return;
    host.append(panel);
    const s=NLE.sm.getState(),selected=s.tracks.filter(t=>t.type==='video').flatMap(t=>t.clips).find(c=>s.selection.includes(c.id));
    if(!busy&&!pending&&selectedId!==selected?.id){
      selectedId=selected?.id;
      $('bg-start').value=(selected?.startSec??Math.min(s.playhead||0,Math.max(0,s.videoDuration-1))).toFixed(3);
      $('bg-end').value=(selected?.endSec??s.videoDuration).toFixed(3);status('');}
  }};
  NLE.backgroundRemoval.mount(document.querySelector('[data-background-removal-host]'));
})();
