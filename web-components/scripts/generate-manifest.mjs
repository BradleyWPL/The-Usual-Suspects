import {writeFile} from 'node:fs/promises';

const elements = [
  ['LensClusterCard','lens-cluster-card',[['title','string'],['clusterId','string'],['count','number'],['status','string']]],
  ['LensEvidenceList','lens-evidence-list',[['causes','Array<CauseEvidence>']]],
  ['LensNoiseMeter','lens-noise-meter',[['total','number'],['clustered','number']]],
  ['LensIncidentTimeline','lens-incident-timeline',[['points','Array<TimelinePoint>'],['changeHour','string']]],
  ['LensDependencyGraph','lens-dependency-graph',[['nodes','Array'],['edges','Array']]],
  ['LensProposalForm','lens-proposal-form',[['clusterId','string'],['candidate','string']]],
];
const manifest={schemaVersion:'1.0.0',readme:'README.md',modules:[{kind:'javascript-module',path:'src/index.ts',declarations:elements.map(([name,tagName,properties])=>({kind:'class',name,tagName,customElement:true,description:`IncidentLens ${tagName.replaceAll('-',' ')} component.`,superclass:{name:'LitElement',package:'lit'},members:properties.map(([member,type])=>({kind:'field',name:member,type:{text:type},privacy:'public'}))}))}]};
await writeFile(new URL('../custom-elements.json',import.meta.url),`${JSON.stringify(manifest,null,2)}\n`);
