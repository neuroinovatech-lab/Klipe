(function () {
  'use strict';
  const A=window.KlipeAssist;
  const ui={result:null,busy:false};
  const el=(tag,text,attrs={})=>{const e=document.createElement(tag);if(text)e.textContent=text;Object.assign(e,attrs);return e;};
  function state(){return A.snapshot(NLE.sm.getState(),NLE.config || {});}
  function go(t){NLE.sm.dispatch('SET_PLAYHEAD',t || 0);NLE.preview?.p?.seek(t || 0);}
  const panel=el('dialog',null,{id:'assistant-panel'});
  panel.innerHTML='<header><strong>Assistente de edi\u00e7\u00e3o</strong><button type="button" aria-label="Fechar" title="Fechar">\u00d7</button></header>'+
    '<div class="assist-actions"><button type="button" id="assist-analyze">Analisar projeto</button><label><input type="checkbox" id="assist-faces"> Conferir rostos</label></div>'+
    '<p id="assist-status" role="status"></p><div id="assist-results"></div>'+
    '<fieldset><legend>Recorte de pessoa</legend><div class="assist-range"><label>In\u00edcio (s)<input id="assist-start" type="number" min="0" step="0.1" value="0"></label><label>Fim (s)<input id="assist-end" type="number" min="0" step="0.1" value="5"></label><button type="button" id="assist-person">Gerar recorte</button></div></fieldset>'+
    '<footer><button type="button" id="assist-apply" disabled>Aplicar selecionados</button></footer>';
  document.body.append(panel);
  const $=id=>document.getElementById(id);
  const status=text=>{$('assist-status').textContent=text;};
  panel.querySelector('header button').onclick=()=>panel.close();
  panel.addEventListener('cancel',()=>{});
  const controls=['assist-analyze','assist-person'];
  const setBusy=b=>{ui.busy=b;controls.forEach(id=>$(id).disabled=b);$('assist-apply').disabled=b || !ui.result;};
  async function request(endpoint,payload){
    const r=await fetch('/api/assistant/'+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await r.json();if(!r.ok)throw Error(data.error || 'Falha na analise.');return data;
  }
  async function job(endpoint,payload){
    const initial=await request(endpoint,payload);
    while(true){
      await new Promise(resolve=>setTimeout(resolve,900));
      const r=await fetch('/api/assistant/job?id='+encodeURIComponent(initial.id));
      const j=await r.json();if(!r.ok || j.status==='error')throw Error(j.error || 'Falha na analise.');
      if(j.status==='done')return j.result;
    }
  }
  function show(result){
    const host=$('assist-results');host.replaceChildren();ui.result=result;
    const issues=el('section');issues.append(el('h3','Confer\u00eancia'));
    if(!result.issues?.length)issues.append(el('p','Nenhum problema encontrado nas verifica\u00e7\u00f5es executadas.'));
    for(const issue of result.issues || []){
      const row=el('div',null,{className:'assist-issue '+issue.severity});
      const seek=el('button',Number(issue.startSec || 0).toFixed(1)+'s',{type:'button',title:'Ver trecho'});
      seek.onclick=()=>go(issue.startSec);row.append(seek,el('span',issue.text));issues.append(row);
    }
    host.append(issues);
    const section=el('section');section.append(el('h3','Sugest\u00f5es'));
    if(!result.suggestions.length)section.append(el('p','Nenhuma nova sugest\u00e3o para este projeto.'));
    for(const suggestion of result.suggestions){
      const row=el('div',null,{className:'assist-suggestion'});
      const choice=el('input',null,{type:'checkbox',checked:false,disabled:suggestion.type==='review'});
      choice.dataset.id=suggestion.id;choice.setAttribute('aria-label','Selecionar '+suggestion.label);
      const copy=el('div');copy.append(el('strong',suggestion.label),el('small',suggestion.reason));
      const seek=el('button',suggestion.clip.startSec.toFixed(1)+'s',{type:'button',title:'Ver trecho'});
      seek.onclick=()=>go(suggestion.clip.startSec);row.append(choice,copy,seek);section.append(row);
    }
    host.append(section);
  }
  function addClips(suggestions){
    const s=NLE.sm.getState();NLE.sm.pushUndo();
    for(const item of suggestions){
      let track=s.tracks.find(t=>t.type===item.type && !t.locked && t.visible!==false && !t.muted &&
        !t.clips.some(c=>A.overlap(c,item.clip)));
      if(!track){track={id:'track-assist-'+crypto.randomUUID(),type:item.type,name:'Assistente '+item.type,
        visible:true,muted:false,locked:false,clips:[]};s.tracks.push(track);}
      track.clips.push(JSON.parse(JSON.stringify(item.clip)));
    }
    s.selection=suggestions.map(i=>i.clip.id);
    NLE.renderer.markDirty();NLE.sm.notify();NLE.renderProperties();NLE.syncPlayerFromState();NLE.resizeTimeline();
  }
  $('assist-analyze').onclick=async()=>{
    if(ui.busy)return;setBusy(true);ui.result=null;status('Analisando fala, midias e timeline...');
    try{const result=await job('analyze',{config:state(),faces:$('assist-faces').checked});show(result);
      status(`${result.speechCount} trechos de fala; ${result.suggestions.length} sugest\u00f5es. Analise local por regras.`);
    }catch(e){status(e.message);}finally{setBusy(false);}
  };
  $('assist-apply').onclick=()=>{
    if(!ui.result)return;
    if(A.hash(state())!==ui.result.signature){status('O projeto mudou. Analise novamente antes de aplicar.');return;}
    const ids=new Set([...panel.querySelectorAll('input[data-id]:checked')].map(n=>n.dataset.id));
    const items=ui.result.suggestions.filter(i=>ids.has(i.id)&&i.type!=='review');
    if(!items.length){status('Selecione pelo menos uma sugest\u00e3o.');return;}
    addClips(items);ui.result=null;$('assist-apply').disabled=true;
    status(`${items.length} itens aplicados. Altera\u00e7\u00f5es n\u00e3o salvas.`);
  };
  $('assist-person').onclick=async()=>{
    if(ui.busy)return;setBusy(true);const config=state();status('Gerando recorte de pessoa...');
    try{
      const result=await job('person',{config,startSec:Number($('assist-start').value),endSec:Number($('assist-end').value)});
      show({signature:result.signature,issues:[],suggestions:[{id:result.clip.id,type:'broll',label:'Pessoa recortada',
        reason:'Camada transparente acima dos titulos. Confira as bordas antes de aplicar.',clip:result.clip}]});
      status('Recorte pronto para aplicar.');
    }catch(e){status(e.message);}finally{setBusy(false);}
  };
  NLE.assistant={open(){
    const t=NLE.sm.getState().playhead || 0;$('assist-start').value=t.toFixed(1);
    $('assist-end').value=Math.min(t+5,NLE.sm.getState().videoDuration).toFixed(1);
    if(!panel.open)panel.showModal();
  }};
  const tab=el('button','Assistente',{type:'button',className:'ia-aba',title:'Analisar projeto e sugerir edicoes'});
  tab.onclick=()=>{NLE.ia.fechar();NLE.assistant.open();};
  document.getElementById('ia-abas')?.prepend(tab);
})();
