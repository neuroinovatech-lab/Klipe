/* Editable controls for the main footage. Data is saved only by the editor Save action. */
(() => {
  const defaults = {posX:0,posY:0,scale:1,scaleX:1,scaleY:1,rotation:0,anchorX:0,anchorY:0,
    pitch:0,yaw:0,flipX:false,flipY:false,scaleLinked:true,transformEnabled:true};
  const icon = name => `<img src="/vendor/lucide/${name}.svg" alt="" width="16" height="16">`;
  function bindNumberScrub(input,change,end) {
    let drag=null;
    const finish=()=>{
      if(!drag)return;
      const id=drag.id;drag=null;
      input.classList.remove('vtf-scrubbing');
      document.documentElement.classList.remove('vtf-scrubbing');
      window.removeEventListener('blur',finish);
      if(input.hasPointerCapture(id))input.releasePointerCapture(id);
      end();
    };
    input.addEventListener('pointerdown',event=>{
      if(event.button!==0 || !event.isPrimary || input.matches(':disabled'))return;
      // Leave the native up/down arrows available at the right edge.
      if(event.clientX>=input.getBoundingClientRect().right-16)return;
      event.preventDefault();
      drag={id:event.pointerId,x:event.clientX,startX:event.clientX,value:Number(input.value),active:false};
      input.setPointerCapture(event.pointerId);
      window.addEventListener('blur',finish);
    });
    input.addEventListener('pointermove',event=>{
      if(!drag || event.pointerId!==drag.id)return;
      if(!drag.active && Math.abs(event.clientX-drag.startX)<4)return;
      event.preventDefault();
      drag.active=true;
      input.classList.add('vtf-scrubbing');
      document.documentElement.classList.add('vtf-scrubbing');
      const key=input.dataset.vtf;
      const rate=key.startsWith('scale')?.005:['rotation','pitch','yaw'].includes(key)?.25:1;
      const multiplier=event.shiftKey?.1:event.ctrlKey||event.metaKey?10:1;
      drag.value=Math.max(Number(input.min),Math.min(Number(input.max),drag.value+(event.clientX-drag.x)*rate*multiplier));
      drag.x=event.clientX;
      input.value=String(+drag.value.toFixed(3));
      change();
      // Linked scales can impose a tighter limit than the input's own bounds.
      if(Math.abs(Number(input.value)-drag.value)>.001)drag.value=Number(input.value);
    });
    input.addEventListener('pointerup',event=>{
      if(!drag || event.pointerId!==drag.id)return;
      const clicked=!drag.active;
      finish();
      if(clicked){input.focus();input.select();}
    });
    input.addEventListener('pointercancel',finish);
    input.addEventListener('lostpointercapture',finish);
  }
  function render(clip, width, height) {
    const t = KlipeVideoTransform.normalize(clip,width,height);
    const number = (key,label,min,max,step=1) => `<input type="number" data-vtf="${key}" aria-label="${label}" title="Arraste para ajustar; clique para digitar. Shift: preciso. Ctrl: r\u00e1pido." min="${min}" max="${max}" step="${step}" value="${t[key]}">`;
    const pair = (label,x,y,minX,maxX,minY,maxY,step=1,extra='') => `<div class="vtf-row"><span>${label}</span><div class="vtf-pair"><label>X ${number(x,label+' X',minX,maxX,step)}</label><label>Y ${number(y,label+' Y',minY,maxY,step)}</label></div>${extra}</div>`;
    const slider = (label,key,min,max) => `<div class="vtf-row"><label for="vtf-${key}">${label}</label><div class="vtf-slider"><input id="vtf-${key}" type="range" data-vtf="${key}" aria-label="${label}, controle" min="${min}" max="${max}" step="0.1" value="${t[key]}">${number(key,label,min,max,.1)}</div></div>`;
    return `<section class="vtf" data-video-transform><header><label><input type="checkbox" data-vtf-toggle="transformEnabled" ${t.enabled?'checked':''}>Transformar</label><button type="button" data-vtf-reset title="Restaurar transforma\u00e7\u00e3o" aria-label="Restaurar transforma\u00e7\u00e3o">${icon('rotate-ccw')}</button></header>
      <fieldset ${t.enabled?'':'disabled'}>
      ${pair('Escala','scaleX','scaleY',.1,3,.1,3,.01,`<button type="button" data-vtf-link aria-label="Vincular escalas X e Y" title="Vincular escalas X e Y" aria-pressed="${t.linked}">${icon(t.linked?'link':'unlink')}</button>`)}
      ${pair('Posi\u00e7\u00e3o (px)','posX','posY',-width,width,-height,height)}
      ${slider('Rota\u00e7\u00e3o (\u00b0)','rotation',-360,360)}
      ${pair('\u00c2ncora (px)','anchorX','anchorY',-width,width,-height,height)}
      ${slider('Pitch (\u00b0)','pitch',-60,60)}${slider('Yaw (\u00b0)','yaw',-60,60)}
      <div class="vtf-row"><span>Espelhar</span><div class="vtf-flips"><button type="button" data-vtf-flip="flipX" aria-label="Espelhar horizontalmente" title="Espelhar horizontalmente" aria-pressed="${t.flipX}">${icon('flip-horizontal-2')}</button><button type="button" data-vtf-flip="flipY" aria-label="Espelhar verticalmente" title="Espelhar verticalmente" aria-pressed="${t.flipY}">${icon('flip-vertical-2')}</button></div></div>
      </fieldset></section>`;
  }
  function bind(root, clip, sm, refresh, width, height) {
    if (!root) return;
    const controls = [...root.querySelectorAll('[data-vtf]')];
    const display = () => {
      const t=KlipeVideoTransform.normalize(clip,width,height);
      for(const input of controls) input.value = String(+((input.dataset.vtf==='posY'||input.dataset.vtf==='anchorY'?-1:1)*t[input.dataset.vtf]).toFixed(3));
      root.querySelector('fieldset').disabled=!t.enabled;
      root.querySelector('[data-vtf-toggle]').checked=t.enabled;
      const link=root.querySelector('[data-vtf-link]');link.setAttribute('aria-pressed',String(t.linked));
      link.innerHTML=icon(t.linked?'link':'unlink');
      root.querySelectorAll('[data-vtf-flip]').forEach(button=>button.setAttribute('aria-pressed',String(t[button.dataset.vtfFlip])));
    };
    for(const input of controls) {
      let undoStarted=false;
      const change=()=>{
        if(input.value.trim()==='' || !Number.isFinite(Number(input.value))) {display();return;}
        const key=input.dataset.vtf, current=KlipeVideoTransform.normalize(clip,width,height);
        let value=Math.max(Number(input.min),Math.min(Number(input.max),Number(input.value)));
        if(key==='posY'||key==='anchorY')value=-value;
        if(!undoStarted){sm.pushUndo();undoStarted=true;}
        if((key==='scaleX'||key==='scaleY')&&current.linked){
          const other=key==='scaleX'?'scaleY':'scaleX', ratio=current[other]/current[key];
          value=Math.max(Math.max(.1,.1/ratio),Math.min(Math.min(3,3/ratio),value));
          clip[other]=value*ratio;
        }
        clip[key]=value;display();refresh();
      };
      input.addEventListener('input',()=>{if(input.type==='range')change();});
      input.addEventListener('change',()=>{change();undoStarted=false;});
      input.addEventListener('blur',()=>{undoStarted=false;});
      if(input.type==='number')bindNumberScrub(input,change,()=>{undoStarted=false;});
    }
    root.querySelector('[data-vtf-reset]').addEventListener('click',()=>{sm.pushUndo();Object.assign(clip,defaults);display();refresh();});
    root.querySelector('[data-vtf-toggle]').addEventListener('change',e=>{sm.pushUndo();clip.transformEnabled=e.target.checked;display();refresh();});
    root.querySelector('[data-vtf-link]').addEventListener('click',()=>{sm.pushUndo();clip.scaleLinked=clip.scaleLinked===false;display();refresh();});
    root.querySelectorAll('[data-vtf-flip]').forEach(button=>button.addEventListener('click',()=>{sm.pushUndo();const key=button.dataset.vtfFlip;clip[key]=!clip[key];display();refresh();}));
    display();
  }
  window.KlipeVideoTransformUI={render,bind};
})();
