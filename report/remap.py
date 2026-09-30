import json,re,sys
inv=json.load(open(sys.argv[1])); R=inv['software']['repos']
MAP=[('decision models','Decision models (Jev-style)'),('gap-analysis wave','Gap-analysis additions'),('training / fine-tuning','Training, fine-tuning, RL and eval'),('BCI','BCI, EEG and biosignals'),('inference engines','Inference engines'),('comfy + nodes','ComfyUI and nodes'),('model source repos','Model source repos'),('ml frameworks','ML frameworks and libraries'),
 ('media / audio / video','Media tooling (audio, video, image)'),('dev toolchains','Developer toolchains (sources)'),('genome','Genome analysis'),('circuit','Circuit design'),('3d modelling','3D modelling'),
 ('agent harnesses','Agent harnesses and frameworks'),('harnesses, wave 2','Agent harnesses and frameworks'),('multi-box','Multi-box serving and clustering'),('audio edit/refine','Audio editing and restoration'),
 ('voice assistant','Voice assistant stack'),('swarm / multi-agent','Multi-agent and swarm frameworks'),('orchestration','Agent orchestration and workflows'),('protocols','Agent protocols (MCP, A2A, AG-UI)'),
 ('swarm coding','Parallel coding agents and skills'),('self-hosted fronts','Self-hosted fronts, guardrails and eval'),('conversion / abliteration','Conversion and abliteration tooling'),('games','Games')]
ORDER=['Inference engines','Decision models (Jev-style)','Training, fine-tuning, RL and eval','Multi-box serving and clustering','ML frameworks and libraries','Model source repos','Conversion and abliteration tooling','ComfyUI and nodes','Media tooling (audio, video, image)','Audio editing and restoration','Voice assistant stack','Agent harnesses and frameworks','Multi-agent and swarm frameworks','Agent orchestration and workflows','Agent protocols (MCP, A2A, AG-UI)','Parallel coding agents and skills','Self-hosted fronts, guardrails and eval','Developer toolchains (sources)','Games','3D modelling','Circuit design','Genome analysis','BCI, EEG and biosignals']
new={}
for sec,lst in R.items():
    name=next((v for k,v in MAP if k.lower() in sec.lower()),None) or re.sub(r'\s*\(.*','',sec).strip('- ').capitalize()
    new.setdefault(name,[]).extend(lst)
inv['software']['repos']={k:new[k] for k in ORDER if k in new}|{k:v for k,v in new.items() if k not in ORDER}
json.dump(inv,open(sys.argv[1],'w'),indent=1); print({k:len(v) for k,v in inv['software']['repos'].items()})
