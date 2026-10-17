import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import '../../src/index';

function Demo(){
  const evidence=useRef<HTMLElement>(null);const proposal=useRef<HTMLElement>(null);const [saved,setSaved]=useState(false);
  useEffect(()=>{
    if(evidence.current) (evidence.current as any).causes=[{candidate_cause:'Ledger write contention',score_percent:76,evidence:['A ledger change preceded the increase in write timeouts.']}];
    const element=proposal.current;const handle=()=>setSaved(true);element?.addEventListener('proposal-submit',handle);return()=>element?.removeEventListener('proposal-submit',handle);
  },[]);
  const ClusterCard:any='lens-cluster-card';const EvidenceList:any='lens-evidence-list';const ProposalForm:any='lens-proposal-form';
  return <main><p className="eyebrow">INCIDENTLENS WEB COMPONENTS</p><h1>React demo</h1><p className="intro">React renders the same standards-based custom elements.</p><div className="grid"><ClusterCard cluster-id="CL-002" title="Payment status updates delayed" count="74" status="Needs review"/><EvidenceList ref={evidence}/><ProposalForm ref={proposal} cluster-id="CL-002" candidate="Ledger write contention"/></div><p role="status">{saved?'Proposal event received. Human review is still required.':'Review the proposal to see the custom event.'}</p></main>;
}

createRoot(document.getElementById('root')!).render(<Demo/>);
