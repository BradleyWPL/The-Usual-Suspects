// File: web-components/demos/react/main.tsx
// History: Version 0.2, October 17, 2026
// Program: Mount the Lit component examples inside a small React application.
// Input: React state, custom element refs, and proposal-submit events.
// Processing: Render components and bridge one custom event into React state.
// Output: A React-based component demonstration.

import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import '../../src/index';

/** Show the reusable Lit elements from a React host and display emitted review events. */
function Demo(){
  // Keep refs for custom elements so React can set properties and subscribe to native events.
  const evidence=useRef<HTMLElement>(null);const proposal=useRef<HTMLElement>(null);const [saved,setSaved]=useState(false);
  // Bridge the custom element's proposal event into local React state.
  useEffect(()=>{
    if(evidence.current) (evidence.current as any).causes=[{candidate_cause:'Ledger write contention',score_percent:76,evidence:['A ledger change preceded the increase in write timeouts.']}];
    const element=proposal.current;const handle=()=>setSaved(true);element?.addEventListener('proposal-submit',handle);return()=>element?.removeEventListener('proposal-submit',handle);
  },[]);
  const ClusterCard:any='lens-cluster-card';const EvidenceList:any='lens-evidence-list';const ProposalForm:any='lens-proposal-form';
  // Render the standalone component samples and status text for the custom event bridge.
  return <main><p className="eyebrow">INCIDENTLENS WEB COMPONENTS</p><h1>React demo</h1><p className="intro">React renders the same standards-based custom elements.</p><div className="grid"><ClusterCard cluster-id="CL-002" title="Payment status updates delayed" count="74" status="Needs review"/><EvidenceList ref={evidence}/><ProposalForm ref={proposal} cluster-id="CL-002" candidate="Ledger write contention"/></div><p role="status">{saved?'Proposal event received. Human review is still required.':'Review the proposal to see the custom event.'}</p></main>;
}

createRoot(document.getElementById('root')!).render(<Demo/>);
