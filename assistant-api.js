'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const Assist = require('./public/klipe-assist-core');
const {hasVideoTransform} = require('./public/klipe-background');

function resolveMedia(publicDir, slug, src) {
  if (typeof src !== 'string' || !src || src.includes('\0') || path.isAbsolute(src) || src.includes('\\')) throw Error('Caminho de midia invalido.');
  const file = path.resolve(publicDir, src);
  const roots = [path.join(publicDir,'projects',slug), ...['sfx','music','fonts','brolls'].map(d=>path.join(publicDir,d))];
  if (!roots.some(r=>file.startsWith(r+path.sep))) throw Error('Midia fora do projeto ou biblioteca.');
  const real = fs.realpathSync(file);
  if (!roots.some(r=>real.startsWith(path.resolve(r)+path.sep))) throw Error('Midia aponta para fora do projeto.');
  if (!fs.statSync(real).isFile()) throw Error('Midia nao e um arquivo.');
  return real;
}
function run(binary,args,{input,timeout=30000,cwd}={}) {
  return new Promise((resolve,reject)=>{
    const p=spawn(binary,args,{cwd,windowsHide:true,stdio:['pipe','pipe','pipe']});
    let out='',err='',settled=false;
    const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve(value);};
    const timer=setTimeout(()=>{p.kill();finish(Error('Analise excedeu o tempo limite.'));},timeout);
    p.on('error',e=>finish(e));
    p.stdin.on('error',()=>{});
    p.stdout.on('data',b=>{out+=b;if(out.length>8e6){p.kill();finish(Error('Resposta da analise muito grande.'));}});
    p.stderr.on('data',b=>{err=(err+b).slice(-12000);});
    p.on('close',code=>{
      if(code!==0)return finish(Error(err.trim() || `Processo terminou com codigo ${code}.`));
      try{finish(null,JSON.parse(out));}catch{finish(Error('Resposta invalida do analisador.'));}
    });
    p.stdin.end(input ? JSON.stringify(input) : undefined);
  });
}
async function readBody(req) {
  let size=0, chunks=[];
  for await(const chunk of req){size+=chunk.length;if(size>4e6)throw Error('Projeto muito grande para esta analise.');chunks.push(chunk);}
  return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
}
function createAssistantAPI({root,pythonExe,ffbin,listSfx}) {
  const publicDir=path.join(root,'public'), jobs=new Map(), cache=new Map();
  const visionPython=()=>process.env.KLIPE_VISION_PYTHON ||
    (fs.existsSync(path.join(root,'.venv-vision',process.platform==='win32'?'Scripts/python.exe':'bin/python')) ?
      path.join(root,'.venv-vision',process.platform==='win32'?'Scripts/python.exe':'bin/python') : pythonExe());
  async function probe(slug,src) {
    try {
      const file=resolveMedia(publicDir,slug,src), stat=fs.statSync(file), key=`${file}:${stat.size}:${stat.mtimeMs}`;
      if(cache.has(key)) return cache.get(key);
      const data=await run(ffbin('ffprobe'),['-v','error','-show_format','-show_streams','-of','json',file]);
      const video=(data.streams || []).find(s=>s.codec_type==='video');
      const result={duration:Number(data.format?.duration || video?.duration || 0),width:video?.width,height:video?.height,
        hasAudio:(data.streams || []).some(s=>s.codec_type==='audio')};
      if(cache.size>256)cache.clear();cache.set(key,result);return result;
    }catch(e){return {error:`Midia indisponivel: ${src} (${e.code || e.message})`};}
  }
  function launch(slug,kind,task) {
    for(const [id,j] of jobs)if(j.finished && Date.now()-j.finished>3600000)jobs.delete(id);
    if([...jobs.values()].some(j=>j.status==='running'))throw Error('Aguarde a analise atual terminar.');
    const id=crypto.randomUUID(),job={id,slug,kind,status:'running'};jobs.set(id,job);
    task().then(result=>{job.result=result;job.status='done';},e=>{job.error=e.message;job.status='error';})
      .finally(()=>{job.finished=Date.now();});
    return {id,status:job.status};
  }
  return async function assistant(req,res,url,slug) {
    if(!url.pathname.startsWith('/api/assistant/'))return false;
    const send=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
    try {
      if(req.headers.origin && new URL(req.headers.origin).host!==req.headers.host)throw Error('Origem da requisicao invalida.');
      if(!slug || !/^[a-zA-Z0-9_.-]+$/.test(slug) || slug==='.' || slug==='..' || !fs.existsSync(path.join(publicDir,'projects',slug,'edit_config.json')))
        throw Error('Abra um projeto existente antes de analisar.');
      if(req.method==='GET' && url.pathname==='/api/assistant/job'){
        const job=jobs.get(url.searchParams.get('id'));
        if(!job || job.slug!==slug){send(404,{error:'Analise nao encontrada neste projeto.'});return true;}
        send(200,job);return true;
      }
      if(req.method!=='POST'){send(405,{error:'Metodo nao permitido.'});return true;}
      const body=await readBody(req),config=body.config;
      if(!config || !Number.isFinite(config.videoDuration) || config.videoDuration<=0 || config.videoDuration>14400)
        throw Error('Duracao invalida (limite de quatro horas por analise).');
      for(const key of Object.values(Assist.tracks))if(config[key]!==undefined && !Array.isArray(config[key]))throw Error(`Faixa ${key} invalida.`);
      if(config.projectName && config.projectName!==slug)throw Error('O projeto da analise nao corresponde a esta aba.');
      if(url.pathname==='/api/assistant/analyze') {
        send(202,launch(slug,'analysis',async()=>{
          const sources=new Set([config.videoSrc]);
          for(const key of ['videoClips','brolls','sfx','musicTracks'])for(const c of config[key] || [])if(c.src)sources.add(c.src);
          // Read only the first small set of matching local sounds, not the whole library.
          for(const item of listSfx().filter(s=>/pop|click|tick|cash|coin/i.test(typeof s==='string'?s:s.src)).slice(0,12))sources.add(typeof item==='string'?item:item.src);
          if(sources.size>400)throw Error('Mais de 400 midias: analise um projeto menor.');
          const assets={};for(const src of sources)if(src)assets[src]=await probe(slug,src);
          let transcript=[];
          const trans=path.join(publicDir,'projects',slug,'transcription.json');
          if(!(config.captions || []).length && fs.existsSync(trans)){
            const raw=JSON.parse(fs.readFileSync(trans,'utf8'));
            const sameSource=(config.videoClips || []).every(c=>!c.src || c.src===config.videoSrc);
            if(sameSource)transcript=raw;
          }
          let faces=[],visionError;
          if(body.faces){
            try{const source=resolveMedia(publicDir,slug,config.videoSrc);
              requireSourceTimeline(config);
              if((config.videoClips || []).some(c=>c.src!==config.videoSrc || hasVideoTransform(c) || c.speed && c.speed!==1) || (config.zooms || []).length)
                throw Error('Rostos: analise automatica requer video sem transformacoes ou zoom. Confira o enquadramento manualmente neste projeto.');
              const data=await run(visionPython(),[path.join(root,'tools','assistant_vision.py'),'faces'],
                {input:{source,config,ffmpeg:ffbin('ffmpeg')},timeout:180000,cwd:root});faces=data.faces;
            }catch(e){visionError=e.message;}
          }
          const result=Assist.plan(config,transcript,assets,faces);
          if(!result.speechCount)result.issues.push({severity:'info',code:'no-speech',text:'Sem legendas ou transcricao compativel. Transcreva o video para sugerir destaques.'});
          if(visionError)result.issues.push({severity:'warning',code:'vision',text:visionError});
          return result;
        }));return true;
      }
      if(url.pathname==='/api/assistant/person') {
        const start=Number(body.startSec),end=Number(body.endSec);
        if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>config.videoDuration||end-start>30)
          throw Error('Selecione de 0 a 30 segundos dentro do video.');
        const source=resolveMedia(publicDir,slug,config.videoSrc);
        requireSourceTimeline(config);
        if((config.videoClips || []).some(c=>c.src && c.src!==config.videoSrc || c.speed && c.speed!==1) ||
           (config.zooms || []).some(c=>Assist.overlap(c,{startSec:start,endSec:end})) ||
           (config.videoClips || []).some(hasVideoTransform))
          throw Error('Recorte automatico requer trecho sem zoom, velocidade ou transformacao do video. Ajuste o trecho antes de gerar.');
        const strength=body.strength===undefined?0:Number(body.strength);
        const feather=body.feather===undefined?0.6:Number(body.feather);
        if(!Number.isFinite(strength)||strength<0||strength>100||!Number.isFinite(feather)||feather<0||feather>4)
          throw Error('Limpeza deve estar entre 0 e 100 e suavidade entre 0 e 4.');
        if(body.mode!==undefined && !['remove','foreground'].includes(body.mode))throw Error('Modo de recorte invalido.');
        const rel=`projects/${slug}/assistant/person-${crypto.randomUUID()}.mp4`;
        const background=body.mode==='remove'?rel.replace('.mp4','-background.mp4'):null;
        send(202,launch(slug,'person',async()=>{
          const output=path.join(publicDir,rel);fs.mkdirSync(path.dirname(output),{recursive:true});
          const result=await run(visionPython(),[path.join(root,'tools','assistant_vision.py'),'person'],{
            input:{source,output,config,startSec:start,endSec:end,ffmpeg:ffbin('ffmpeg'),
              model:path.join(root,'models','selfie_multiclass.tflite'),strength,feather,
              backgroundOutput:background?path.join(publicDir,background):null},timeout:600000,cwd:root});
          return {clip:{id:'assist-person-'+crypto.randomUUID(),src:rel,label:'Pessoa recortada',startSec:start,
            endSec:roundEnd(start,result.duration),alpha:true,foreground:true,baseDurationSec:result.duration},
            background:background?{id:'assist-background-'+crypto.randomUUID(),src:background,label:'Fundo do recorte',startSec:start,
              endSec:roundEnd(start,result.duration),baseDurationSec:result.duration}:null,signature:Assist.hash(config)};
        }));return true;
      }
      send(404,{error:'Operacao desconhecida.'});
    }catch(e){send(400,{error:e.message});}
    return true;
  };
}
function roundEnd(start,duration){return Math.round((start+duration)*1000000)/1000000;}
function requireSourceTimeline(config) {
  const ranges=config.keepRanges || [];
  const clips=config.videoClips || [];
  if(ranges.length && (ranges.length!==1 || ranges[0][0]!==0 || ranges[0][1]<config.videoDuration-.001) ||
     clips.length && (clips.length!==1 || clips[0].startSec!==0 || (clips[0].srcStart || 0)!==0 || clips[0].endSec<config.videoDuration-.001))
    throw Error('Analise visual requer uma fonte continua sem cortes ou deslocamentos. Use um trecho consolidado para manter o sincronismo.');
}
module.exports={createAssistantAPI,resolveMedia,run,requireSourceTimeline};
