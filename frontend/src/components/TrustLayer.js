// Copyright (c) 2025 Twhyne AI
// SPDX-License-Identifier: MIT
//
// TrustLayer: renders how an answer was earned (the product's whole point).
// The backend returns `gates`, `sources`, and `evidence` on every /query
// response; this surfaces them as a compact, scannable strip plus readable
// message content (code blocks, not raw ``` fences). Presentation only - it
// reads fields the backend already sends and never touches the query path.

import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Human-readable node names (never show raw ids like "language-mistral-7b").
const NODE_LABELS = {
  'math-llm-eval': 'Math · SymPy',
  'rag-extractive': 'Retrieval · exact span',
  'rag-extractive+cached': 'Retrieval · exact span (cached)',
  'language-mistral-7b': 'Language · Mistral-7B',
  'code-qwen-coder-7b': 'Code · Qwen2.5-Coder',
  'code-codellama-7b': 'Code · CodeLlama',
  'planner-mistral-7b': 'Planner',
  'vision-llava-1.6-7b': 'Vision · LLaVA',
};

export function friendlyNode(id) {
  if (!id) return null;
  if (NODE_LABELS[id]) return NODE_LABELS[id];
  // Custom / imported HF nodes: strip a leading "code-" etc. and prettify.
  return id.replace(/^(code|language|vision|math)-/, '').replace(/[-_]/g, ' ');
}

// How the answer was earned -> a labeled, colored verdict chip.
function trustLabel(gates) {
  if (!gates) return null;
  const v = gates.verdict;
  if (v === 'refused') return { text: 'REFUSED', cls: 'refuse' };
  if (gates.redaction === 'fired') return { text: 'REDACTED', cls: 'warn' };
  switch (gates.generation) {
    case 'computed':  return { text: 'COMPUTED',  cls: 'verify' };
    case 'extracted': return { text: 'EXTRACTED', cls: 'verify' };
    case 'cited':     return { text: 'CITED',     cls: 'cite' };
    case 'executed':  return { text: 'EXECUTED',  cls: 'exec' };
    default:          return { text: 'GENERATED', cls: 'muted' };
  }
}

export function TrustStrip({ node, gates, sources, evidence }) {
  const [open, setOpen] = React.useState(false);
  const label = trustLabel(gates);
  const nodeName = friendlyNode(node);
  const hasEvidence = Array.isArray(evidence) && evidence.length > 0;
  if (!label && !nodeName && (!sources || !sources.length)) return null;
  return (
    <div className="trust-wrap">
      <div className="trust-strip" role="group" aria-label="How this answer was produced">
        {label && (
          <span className={`trust-chip ${label.cls}`} title="How this answer was earned">
            {label.text}
          </span>
        )}
        {nodeName && <span className="trust-node">{nodeName}</span>}
        {gates && gates.retrieval && gates.retrieval.passes > 1 && (
          <span className="trust-meta" title="Retrieval ran an extra refinement pass">
            {gates.retrieval.passes} retrieval passes
          </span>
        )}
        {sources && sources.length > 0 && (
          <span className="trust-sources" title="Sources cited">
            <span className="trust-sources-label">sources:</span> {sources.join(', ')}
          </span>
        )}
        {gates && gates.sensitive_request && gates.verdict === 'refused' && (
          <span className="trust-meta refuse-text">sensitive request</span>
        )}
        {hasEvidence && (
          <button className="trust-evidence-toggle" onClick={() => setOpen(o => !o)}
            aria-expanded={open}
            title="Show the exact source passages this answer drew on">
            {open ? 'hide evidence' : `evidence (${evidence.length})`}
          </button>
        )}
      </div>
      {hasEvidence && open && (
        <ul className="trust-evidence" aria-label="Evidence records">
          {evidence.map((e, i) => (
            <li key={i} className="evidence-item">
              <div className="evidence-head">
                <span className="evidence-src">{e.source || 'source'}</span>
                {typeof e.score === 'number' && (
                  <span className="evidence-score" title="Retrieval similarity">
                    {(e.score * 100).toFixed(0)}%
                  </span>
                )}
                {e.support === 'quoted' && <span className="evidence-badge">quoted</span>}
              </div>
              {e.span && <blockquote className="evidence-span">"{e.span}"</blockquote>}
              {e.content_sha && (
                <div className="evidence-hash" title="Content hash - lets an auditor verify this exact passage against the audit ledger">
                  sha256:{e.content_sha}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Render assistant content with real code blocks instead of literal ``` fences.
const FENCE = /```(\w+)?\n?([\s\S]*?)```/g;

export function MessageBody({ content }) {
  if (!content || typeof content !== 'string') return <>{content}</>;
  const parts = [];
  let last = 0;
  let m;
  let i = 0;
  FENCE.lastIndex = 0;
  while ((m = FENCE.exec(content)) !== null) {
    if (m.index > last) {
      parts.push(<span key={`t${i}`} className="msg-text">{content.slice(last, m.index)}</span>);
    }
    const lang = m[1] || 'text';
    parts.push(
      <SyntaxHighlighter key={`c${i}`} language={lang} style={oneDark}
        customStyle={{ margin: '10px 0', borderRadius: 0, fontSize: '12.5px', border: '1px solid rgba(255,255,255,.12)' }}>
        {m[2].replace(/\n$/, '')}
      </SyntaxHighlighter>
    );
    last = FENCE.lastIndex;
    i++;
  }
  if (last < content.length) {
    parts.push(<span key={`t${i}`} className="msg-text">{content.slice(last)}</span>);
  }
  return <>{parts}</>;
}
