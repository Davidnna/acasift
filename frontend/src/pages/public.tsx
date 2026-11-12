import type { ReactNode } from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
    ArrowRight, ArrowUpRight, BookOpen, Check, ChevronDown, CircleHelp,
    FileCheck2, FileSearch, FileText, Fingerprint, Gauge, Layers3, LockKeyhole, Users,
    MessageSquareText, SearchCheck, ShieldCheck, Sparkles, Target, Upload,
} from 'lucide-react';
import { Eyebrow, Notice } from '../components/ui';

export function HomePage() {
    return <>
        <section className="hero-section wrap">
            <div className="hero-copy">
                <div className="eyebrow hero-eyebrow"><span className="eyebrow-pulse" /> DOCUMENT SIMILARITY ANALYSIS</div>
                <h1>Understand text similarity.<br /><span>Review with context.</span></h1>
                <p className="hero-lead">AcaSift helps groups collect documents in shared workspaces, identify textual overlap between submissions and organise clear, evidence-led review.</p>
                <div className="hero-actions"><Link viewTransition className="button button-primary button-lg" to="/how-it-works">Explore how it works <ArrowRight size={17} /></Link><Link viewTransition className="button button-outline button-lg" to="/register">Create a free account</Link></div>
                <div className="hero-footnote"><ShieldCheck size={16} /> Designed to support careful review, not replace human judgement.</div>
            </div>
            <div className="hero-art" aria-label="Illustrative AcaSift similarity report">
                <div className="hero-glow" />
                <div className="report-window">
                    <div className="report-window-top"><div className="window-dots"><i /><i /><i /></div><span>SIMILARITY REPORT · PREVIEW</span><span className="report-window-check"><Check size={13} /> SAMPLE</span></div>
                    <div className="report-document"><div className="doc-icon"><FileText size={18} /></div><div><strong>Research submission.docx</strong><small>Document comparison</small></div><span className="doc-chip">DOCX</span></div>
                    <div className="report-divider" />
                    <div className="report-metrics"><div><small>Cosine similarity</small><strong>18.6<em>%</em></strong></div><div><small>N-gram coverage</small><strong>12.4<em>%</em></strong></div></div>
                    <div className="report-progress-label"><span>Text overlap indicator</span><span>Illustrative sample</span></div><div className="report-progress"><span /></div>
                    <div className="matched-label"><span /> MATCHING PASSAGE IDENTIFIED</div>
                    <div className="fake-lines"><i /><i /><i /><i /><i /></div>
                    <div className="source-preview"><div className="source-icon"><BookOpen size={16} /></div><div><strong>Peer submission</strong><small>Same Submission Request</small></div><ArrowUpRight size={16} /></div>
                </div>
                <div className="floating-tag tag-top"><SearchCheck size={15} /> Passage matching</div><div className="floating-tag tag-bottom"><Check size={15} /> Source review</div>
            </div>
        </section>
        <section className="capability-strip"><div className="wrap strip-inner"><span className="strip-intro">BUILT FOR DOCUMENT REVIEW</span><div><strong>PDF</strong><small>Documents</small></div><div><strong>DOCX</strong><small>Word files</small></div><div><strong>TXT</strong><small>Text files</small></div><div><strong>TF-IDF</strong><small>Text similarity</small></div><div><strong>N-grams</strong><small>Passage matching</small></div></div></section>
        <section className="section wrap"><div className="section-title centered"><Eyebrow>WHAT ACASIFT DOES</Eyebrow><h2>From document submission<br />to evidence-led review.</h2><p>AcaSift brings document extraction, text comparison and source-level review into one straightforward workflow.</p></div>
            <div className="feature-cards">
                <FeatureCard icon={<FileText />} number="01" title="Document text extraction" text="Extract text from supported PDF, DOCX and TXT documents so their contents can be analysed." />
                <FeatureCard icon={<Target />} number="02" title="Request-based comparison" text="Compare each submission with other eligible documents submitted to the same Submission Request." />
                <FeatureCard icon={<SearchCheck />} number="03" title="Matching passage review" text="Inspect identified overlapping word sequences alongside the corresponding passages from other submissions." />
            </div>
            <div className="center-link"><Link viewTransition className="text-link" to="/features">Explore all features <ArrowRight size={16} /></Link></div>
        </section>
        <section className="workflow-band"><div className="wrap workflow-home"><div className="workflow-intro"><Eyebrow>A CLEAR WORKFLOW</Eyebrow><h2>How AcaSift works</h2><p>Join a shared workspace, submit documents through a request and review the results with the authorised team.</p><Link viewTransition className="text-link" to="/how-it-works">See the full process <ArrowRight size={16} /></Link></div><div className="workflow-mini-steps"><MiniStep number="01" title="Join a workspace" text="Create a shared workspace or join one using an invitation link." /><MiniStep number="02" title="Submit a document" text="Open a Submission Request and upload a document that meets its requirements." /><MiniStep number="03" title="Review with context" text="Authorised reviewers inspect similarities and provide feedback to contributors." /></div></div></section>
        <section className="section wrap"><div className="integrity-panel"><div className="integrity-icon"><ShieldCheck size={24} /></div><div><Eyebrow>IMPORTANT TO UNDERSTAND</Eyebrow><h2>A similarity score is a signal, not a verdict.</h2><p>Text overlap can occur in properly cited quotations, references, standard terminology and commonly used phrases. AcaSift provides indicators and matching passages for human assessment. It does not independently determine whether plagiarism has occurred.</p></div><Link viewTransition className="button button-outline" to="/faq">Read the FAQs</Link></div></section>
        <section className="closing-cta"><div className="wrap closing-cta-inner"><div><Eyebrow>ACASIFT WORKSPACE</Eyebrow><h2>Ready to collaborate on a document review?</h2><p>Sign in to join or manage a shared workspace.</p></div><Link viewTransition className="button button-light button-lg" to="/login">Sign in <ArrowRight size={17} /></Link></div></section>
    </>;
}

function FeatureCard({ icon, number, title, text }: { icon: ReactNode; number: string; title: string; text: string; }) {
    return <article className="feature-card"><div className="feature-card-top"><span className="feature-icon">{icon}</span><span className="feature-number">{number}</span></div><h3>{title}</h3><p>{text}</p><Link viewTransition to="/features">Explore feature <ArrowRight size={14} /></Link></article>;
}
function MiniStep({ number, title, text }: { number: string; title: string; text: string; }) {
    return <div className="mini-step"><span>{number}</span><div><h3>{title}</h3><p>{text}</p></div></div>;
}

export function AboutPage() {
    return <PublicPage eyebrow="ABOUT ACASIFT" title="A clearer way to review document similarity." intro="AcaSift is an independent document similarity analysis platform built around shared workspaces, structured submissions and careful review." >
        <div className="prose-grid"><div><h2>Our purpose</h2><p>Responsible document review depends on understanding where text overlaps with other material. Reviewing documents can be time-consuming when submissions, comparison results and reviewer observations are kept in separate places.</p><p>AcaSift brings these activities into one shared workspace. Workspace administrators create Submission Requests, participants submit documents, and the platform compares submissions made to the same request. Authorised reviewers can inspect matching passages and provide feedback to contributors.</p></div><div className="side-note"><Fingerprint size={24} /><h3>Designed for informed review</h3><p>The platform is intended to help reviewers identify material that may deserve closer examination. It does not make disciplinary or business decisions or replace human judgement.</p></div></div>
        <div className="section-subheading"><h2>What guides the platform</h2></div><div className="principle-grid"><Principle icon={<Target />} title="Clarity" text="Present comparison results in a way that authorised reviewers can inspect and understand." /><Principle icon={<BookOpen />} title="Source context" text="Show the submitted documents and matching passages behind the indicators." /><Principle icon={<ShieldCheck />} title="Responsible interpretation" text="Treat similarity as evidence for review, not proof of plagiarism." /></div>
        <Notice tone="info"><strong>Current scope:</strong> Similarity analysis compares eligible documents submitted to the same Submission Request. Documents from unrelated requests are not included in that comparison.</Notice>
    </PublicPage>;
}

export function FeaturesPage() {
    const features = [
        { icon: <FileText />, title: 'Document text extraction', text: 'Extract readable text from PDF, DOCX and TXT files before comparison.' },
        { icon: <Layers3 />, title: 'Request-scoped comparison', text: 'Compare a submission with eligible documents submitted to the same Submission Request.' },
        { icon: <SearchCheck />, title: 'Word N-gram matching', text: 'Identify repeated sequences of words and measure their occurrence in other submissions to the same request.' },
        { icon: <MessageSquareText />, title: 'Passage-level review', text: 'Allow authorised reviewers to inspect overlapping passages and their corresponding source excerpts.' },
        { icon: <LockKeyhole />, title: 'Shared workspace access', text: 'Collaborate through invitation-based workspaces with owner, administrator and member permissions.' },
        { icon: <Gauge />, title: 'Reviewer feedback', text: 'Record review outcomes and provide feedback that contributors can see from their Submission Request.' },
    ];
    return <PublicPage eyebrow="PLATFORM FEATURES" title="Tools for structured similarity review." intro="AcaSift combines document extraction, request-based comparison and reviewer feedback in one shared workflow.">
        <div className="feature-detail-grid">{features.map((feature, i) => <article className="feature-detail-card" key={feature.title}><span className="feature-icon">{feature.icon}</span><span className="feature-number">0{i + 1}</span><h3>{feature.title}</h3><p>{feature.text}</p></article>)}</div>
        <div className="section-subheading"><h2>Supported formats and current boundaries</h2></div><div className="format-grid"><div><strong>PDF</strong><span>Text-based PDF documents</span></div><div><strong>DOCX</strong><span>Microsoft Word documents</span></div><div><strong>TXT</strong><span>Plain-text documents</span></div></div>
        <Notice tone="warning"><strong>Important limitations:</strong> Scanned image-only PDFs, OCR, internet-wide search, external database search, source-code comparison, cross-language comparison and semantic paraphrase detection are not included in the current release.</Notice>
    </PublicPage>;
}

export function HowItWorksPage() {
    const steps = [
        { n: '01', icon: <BookOpen />, title: 'Join or create a shared workspace', text: 'Create a workspace for your group or join an existing one through an invitation link.' },
        { n: '02', icon: <Upload />, title: 'Open a Submission Request and submit', text: 'A workspace administrator creates a request with instructions, accepted file types and any applicable deadline. Participants submit their documents there.' },
        { n: '03', icon: <SearchCheck />, title: 'AcaSift compares submissions', text: 'The platform compares each submitted document with other eligible submissions made to that same request.' },
        { n: '04', icon: <FileCheck2 />, title: 'Review and provide feedback', text: 'Workspace administrators and assigned reviewers inspect similarity results. Contributors receive a submission receipt and any feedback recorded for them.' },
    ];
    return <PublicPage eyebrow="HOW IT WORKS" title="One shared workflow for document review." intro="AcaSift organises document collection, similarity analysis and reviewer feedback inside shared workspaces.">
        <div className="process-list">{steps.map(step => <article className="process-step" key={step.n}><div className="process-number">{step.n}</div><div className="process-icon">{step.icon}</div><div><h3>{step.title}</h3><p>{step.text}</p></div></article>)}</div>
        <div className="section-subheading"><h2>Understanding the report</h2></div><div className="report-explainer-grid"><div className="explainer-card"><span>01</span><h3>Cosine similarity</h3><p>A document-level measure of how similar the TF-IDF vector representations of two documents are. It is not a percentage of plagiarised content.</p></div><div className="explainer-card"><span>02</span><h3>Matched N-gram coverage</h3><p>The proportion of word-sequence windows in the submitted document that are also found in another submission to the same request. Repeated windows are counted.</p></div><div className="explainer-card"><span>03</span><h3>Matching passages</h3><p>Specific overlapping sequences shown with the corresponding text from another submission to support contextual review.</p></div></div>
        <Notice tone="info">Similarity results are available only to workspace administrators and assigned reviewers. AcaSift does not establish intent, attribution or misconduct.</Notice>
    </PublicPage>;
}

const faqItems = [
    ['What is AcaSift?', 'AcaSift is an independent document similarity analysis platform. It uses shared workspaces to collect submissions, compare documents submitted to the same request and support reviewer feedback.'],
    ['How do I use AcaSift?', 'Create an account, verify your email address, then create a shared workspace or join one using an invitation link. Documents are submitted through a Submission Request in that workspace.'],
    ['How are documents compared?', 'Documents submitted to the same Submission Request are compared with other eligible submissions in that request. Documents from unrelated requests are not included.'],
    ['Does AcaSift search the entire internet?', 'No. The current comparison workflow uses eligible submissions made to the same Submission Request. It does not perform internet-wide searches.'],
    ['Does a high similarity score prove plagiarism?', 'No. A similarity score is an indicator of textual overlap, not a verdict. Quoted passages, references, standard terminology and common phrases can contribute to similarity. A person must interpret the results in context.'],
    ['Which file formats are supported?', 'The current release supports text-based PDF, DOCX and TXT documents. Scanned image-only PDFs are not supported because optical character recognition is not currently included.'],
    ['Does AcaSift require an institutional email?', 'No. Anyone can create an account using a personal or work email address. The email address must be verified before the account can be used.'],
    ['What methods does AcaSift use?', 'The current implementation uses TF-IDF vectorisation with cosine similarity for document-level comparison and word-based N-gram matching for identifying overlapping sequences.'],
    ['Does AcaSift detect paraphrased content?', 'The current release focuses on lexical overlap. It does not provide semantic paraphrase detection or cross-language plagiarism detection.'],
    ['Who can view my comparison reports?', 'Only workspace owners, workspace administrators and reviewers assigned to the relevant request can view similarity reports. Contributors see their submission receipts and any feedback recorded by a reviewer.'],
];

export function FaqPage() {
    const [open, setOpen] = useState<number | null>(0);
    return <PublicPage eyebrow="FREQUENTLY ASKED QUESTIONS" title="Questions about AcaSift." intro="Learn about the platform's capabilities, how similarity results should be interpreted and how to obtain an account.">
        <div className="faq-list">{faqItems.map(([question, answer], i) => <article className={`faq-item ${open === i ? 'faq-open' : ''}`} key={question}><button type="button" id={`faq-question-${i}`} aria-controls={`faq-answer-${i}`} onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}><span>{question}</span><ChevronDown size={19} aria-hidden="true" /></button><div className="faq-answer" id={`faq-answer-${i}`} role="region" aria-labelledby={`faq-question-${i}`} hidden={open !== i}><p>{answer}</p></div></article>)}</div>
        <div className="faq-contact"><div><CircleHelp size={22} /><div><h3>Still have a question?</h3><p>Create an account using any valid email address. No institutional affiliation is required.</p></div></div><Link viewTransition className="button button-primary" to="/register">Create an account <ArrowRight size={15} /></Link></div>
    </PublicPage>;
}

export function AccessPage() {
    return <PublicPage eyebrow="OPEN REGISTRATION" title="Join a shared workspace." intro="AcaSift is open to people and groups worldwide. You do not need a university affiliation, institutional email address or staff identification number.">
        <div className="access-panel"><div className="access-panel-icon"><Users size={26} /></div><div><h2>Create your AcaSift account.</h2><p>Register with your name, a valid email address and a password. We will send a verification link before activating the account. Once verified, you can create a shared workspace or join one using an invitation link.</p><div className="access-steps"><div><span>1</span><p>Create an account using any valid email address.</p></div><div><span>2</span><p>Verify your email address using the link we send you.</p></div><div><span>3</span><p>Create a shared workspace or accept an invitation.</p></div></div><Link viewTransition className="button button-primary button-lg" to="/register">Create an account <ArrowRight size={16} /></Link></div></div>
        <p className="access-note">Documents are submitted through a Submission Request in a shared workspace.</p>
    </PublicPage>;
}

function Principle({ icon, title, text }: { icon: ReactNode; title: string; text: string; }) {
    return <div className="principle-card"><span className="feature-icon">{icon}</span><h3>{title}</h3><p>{text}</p></div>;
}

function PublicPage({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: ReactNode; }) {
    return <div className="public-subpage"><section className="subpage-hero"><div className="wrap"><Eyebrow>{eyebrow}</Eyebrow><h1>{title}</h1><p>{intro}</p></div></section><div className="wrap subpage-content">{children}</div></div>;
}
