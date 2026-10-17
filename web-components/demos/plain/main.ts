import '../../src/index';
import type { LensEvidenceList, LensIncidentTimeline, LensDependencyGraph, LensNoiseMeter } from '../../src/index';

const evidence=document.querySelector<LensEvidenceList>('#evidence')!;
evidence.causes=[{candidate_cause:'Identity provider pool exhaustion',score_percent:82,evidence:['The affected systems share the identity service.','A related configuration change preceded the onset.']}];
const timeline=document.querySelector<LensIncidentTimeline>('#timeline')!;
timeline.points=[{hour:'00',count:2},{hour:'03',count:3},{hour:'06',count:7},{hour:'09',count:19},{hour:'12',count:30},{hour:'15',count:21}];timeline.changeHour='09';
const graph=document.querySelector<LensDependencyGraph>('#dependencies')!;
graph.nodes=[{id:'directory',label:'Directory'},{id:'identity',label:'Identity API'},{id:'gateway',label:'Auth Gateway'}];graph.edges=[{from:'directory',to:'identity'},{from:'identity',to:'gateway'}];
const noise=document.querySelector<LensNoiseMeter>('#noise')!;noise.total=2481;noise.clustered=2010;
document.addEventListener('proposal-submit',(event)=>{const detail=(event as CustomEvent).detail;document.querySelector('#result')!.textContent=`Proposal saved locally for ${detail.clusterId}. Human review is still required.`;});
