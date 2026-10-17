import { LitElement, css, html, nothing } from 'lit';

export interface CauseEvidence {
  candidate_cause: string;
  score_percent: number;
  evidence: string[];
}
export interface TimelinePoint { hour: string; count: number }

const cardStyles = css`
  :host{display:block;color:#20312d;font:14px/1.5 system-ui,sans-serif}
  article{padding:16px;border:1px solid #dce7e2;border-radius:12px;background:#fff}
  header{display:flex;align-items:start;justify-content:space-between;gap:12px}
  h2{margin:0;font-size:17px} small,.muted{color:#70827c}
  .metric{font:600 22px system-ui} ::slotted(*){margin-top:12px}
`;

export class LensClusterCard extends LitElement {
  static properties = { title: {type:String}, clusterId: {type:String,attribute:'cluster-id'}, count:{type:Number}, status:{type:String} };
  static styles = cardStyles;
  title = 'Untitled pattern'; clusterId = ''; count = 0; status = 'needs review';
  render(){ return html`<article><header><div><h2>${this.title}</h2><small>${this.clusterId}</small></div><span>${this.status}</span></header><p class="metric">${this.count.toLocaleString()} <small>incidents</small></p><slot></slot></article>`; }
}

export class LensEvidenceList extends LitElement {
  static properties = { causes: {type:Array} };
  static styles = [cardStyles, css`ol{padding-left:22px;margin:8px 0}li{padding:10px 0;border-bottom:1px solid #edf1ef}strong{display:flex;justify-content:space-between;gap:10px}p{margin:5px 0;color:#61736d}`];
  causes: CauseEvidence[] = [];
  render(){ return html`<section aria-label="Ranked root cause evidence"><h2>Evidence</h2><ol>${this.causes.map((item)=>html`<li><strong><span>${item.candidate_cause}</span><span>${item.score_percent}%</span></strong><p>${item.evidence.join(' ')}</p></li>`)}</ol></section>`; }
}

export class LensNoiseMeter extends LitElement {
  static properties = { total:{type:Number}, clustered:{type:Number} };
  static styles = [cardStyles,css`progress{width:100%;height:10px;accent-color:#38ae98}p{margin:6px 0;color:#657771}`];
  total=0; clustered=0;
  render(){ const percent=this.total?Math.min(100,Math.round(this.clustered/this.total*100)):0; return html`<article><h2>Noise reduction</h2><progress max="100" .value=${percent} aria-label="Share of incidents assigned to candidate problems"></progress><p>${this.clustered.toLocaleString()} of ${this.total.toLocaleString()} incidents grouped · ${percent}%</p></article>`; }
}

export class LensIncidentTimeline extends LitElement {
  static properties = { points:{type:Array}, changeHour:{type:String,attribute:'change-hour'} };
  static styles = [cardStyles,css`svg{display:block;width:100%;height:130px}.axis{stroke:#dbe5e1;stroke-width:1}.area{fill:#9cddcd;opacity:.38}.line{fill:none;stroke:#168d79;stroke-width:3}.change{stroke:#d28b36;stroke-width:2;stroke-dasharray:4 4}text{font:10px system-ui;fill:#70827c}`];
  points: TimelinePoint[]=[]; changeHour='';
  render(){
    const max=Math.max(1,...this.points.map((p)=>p.count));
    const coords=this.points.map((p,i)=>`${this.points.length<2?0:i*100/(this.points.length-1)},${90-p.count/max*74}`);
    const d=coords.length?`M ${coords.join(' L ')} L 100 100 L 0 100 Z`:'';
    const changeIndex=this.points.findIndex((p)=>p.hour===this.changeHour); const x=changeIndex>=0?changeIndex*100/Math.max(1,this.points.length-1):null;
    return html`<article><h2>Incident volume</h2><svg viewBox="0 0 100 110" preserveAspectRatio="none" role="img" aria-label="Incident counts by hour"><line class="axis" x1="0" y1="100" x2="100" y2="100"></line>${x!==null?html`<line class="change" x1=${x} y1="5" x2=${x} y2="100"></line>`:nothing}<path class="area" d=${d}></path>${coords.length?html`<path class="line" d=${coords.length?`M ${coords.join(' L ')}`:''}></path>`:nothing}</svg><small>Hourly counts from synthetic incidents${this.changeHour?` · change at ${this.changeHour}`:''}</small></article>`;
  }
}

export class LensDependencyGraph extends LitElement {
  static properties = { nodes:{type:Array}, edges:{type:Array} };
  static styles = [cardStyles,css`svg{width:100%;height:180px}.edge{stroke:#9ab6ac;stroke-width:2}.node{fill:#e4f5ef;stroke:#65b89f}.label{font:7px system-ui;fill:#20312d}`];
  nodes: Array<{id:string;label:string}>=[]; edges: Array<{from:string;to:string}>=[];
  render(){
    const coords=new Map(this.nodes.map((node,i)=>[node.id,{x:50+(i%3)*130,y:25+Math.floor(i/3)*62}]));
    return html`<article><h2>Dependency path</h2><svg viewBox="0 0 320 150" role="img" aria-label="Affected systems and dependencies">${this.edges.map((edge)=>{const a=coords.get(edge.from),b=coords.get(edge.to);return a&&b?html`<line class="edge" x1=${a.x+30} y1=${a.y+14} x2=${b.x+30} y2=${b.y+14}></line>`:nothing})}${this.nodes.map((node)=>{const p=coords.get(node.id)!;return html`<g><rect class="node" x=${p.x} y=${p.y} width="60" height="28" rx="8"></rect><text class="label" x=${p.x+30} y=${p.y+17} text-anchor="middle">${node.label}</text></g>`})}</svg></article>`;
  }
}

export class LensProposalForm extends LitElement {
  static formAssociated=true;
  static properties={clusterId:{type:String,attribute:'cluster-id'},candidate:{type:String}};
  static styles=[cardStyles,css`form{display:grid;gap:9px}label{font-size:12px}textarea{min-height:68px;border:1px solid #cad8d2;border-radius:7px;padding:9px;font:inherit}button{justify-self:start;border:0;border-radius:7px;padding:9px 12px;background:#176e5f;color:white;font-weight:600}`];
  clusterId=''; candidate=''; #internals:ElementInternals;
  constructor(){super();this.#internals=this.attachInternals();}
  render(){return html`<article><form @submit=${this.#submit}><h2>Review proposal</h2><label for="note">Reviewer note</label><textarea id="note" name="note" placeholder="Add context for the problem record"></textarea><button type="submit">Propose problem</button></form></article>`;}
  #submit=(event:SubmitEvent)=>{event.preventDefault();const note=new FormData(event.currentTarget as HTMLFormElement).get('note')?.toString()||'';this.#internals.setFormValue(JSON.stringify({clusterId:this.clusterId,candidate:this.candidate,note}));this.dispatchEvent(new CustomEvent('proposal-submit',{detail:{clusterId:this.clusterId,candidate:this.candidate,note},bubbles:true,composed:true}));};
}

customElements.define('lens-cluster-card',LensClusterCard);
customElements.define('lens-evidence-list',LensEvidenceList);
customElements.define('lens-noise-meter',LensNoiseMeter);
customElements.define('lens-incident-timeline',LensIncidentTimeline);
customElements.define('lens-dependency-graph',LensDependencyGraph);
customElements.define('lens-proposal-form',LensProposalForm);
