import type { ReactNode } from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
    ArrowRight, ArrowUpRight, BookOpen, Check, ChevronDown, CircleHelp,
    FileCheck2, FileSearch, FileText, Fingerprint, Gauge, Layers3, LockKeyhole,
    MessageSquareText, SearchCheck, ShieldCheck, Sparkles, Target, Upload,
} from 'lucide-react';
import { Eyebrow, Notice } from '../components/ui';

export function HomePage() {
    return <>
        <section className="hero-section wrap">
            <div className="hero-copy">
                <div className="eyebrow hero-eyebrow"><span className="eyebrow-pulse" /> ACADEMIC DOCUMENT SIMILARITY ANALYSIS</div>
                <h1>Understand text similarity.<br /><span>Review with context.</span></h1>
                <p className="hero-lead">AcaSift helps individuals and groups compare documents with authorised reference collections, identify overlapping passages and make more informed decisions during document review.</p>
                <div className="hero-actions"><Link viewTransition className="button button-primary button-lg" to="/how-it-works">Explore how it works <ArrowRight size={17} /></Link><Link viewTransition className="button button-outline button-lg" to="/register">Create a free account</Link></div>
                <div className="hero-footnote"><ShieldCheck size={16} /> Designed to support academic review, not replace human judgement.</div>
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
                    <div className="source-preview"><div className="source-icon"><BookOpen size={16} /></div><div><strong>Reference source</strong><small>Curated repository document</small></div><ArrowUpRight size={16} /></div>
                </div>
                <div className="floating-tag tag-top"><SearchCheck size={15} /> Passage matching</div><div className="floating-tag tag-bottom"><Check size={15} /> Source review</div>
            </div>
        </section>
        <section className="capability-strip"><div className="wrap strip-inner"><span className="strip-intro">BUILT FOR ACADEMIC DOCUMENT REVIEW</span><div><strong>PDF</strong><small>Documents</small></div><div><strong>DOCX</strong><small>Word files</small></div><div><strong>TXT</strong><small>Text files</small></div><div><strong>TF-IDF</strong><small>Text similarity</small></div><div><strong>N-grams</strong><small>Passage matching</small></div></div></section>
        <section className="section wrap"><div className="section-title centered"><Eyebrow>WHAT ACASIFT DOES</Eyebrow><h2>From document submission<br />to evidence-led review.</h2><p>AcaSift brings document extraction, text comparison and source-level review into one straightforward workflow.</p></div>
            <div className="feature-cards">
                <FeatureCard icon={<FileText />} number="01" title="Document text extraction" text="Extract text from supported PDF, DOCX and TXT documents so their contents can be analysed." />
                <FeatureCard icon={<Target />} number="02" title="Similarity comparison" text="Compare a submission with documents in the authorised reference collection using text similarity methods." />
                <FeatureCard icon={<SearchCheck />} number="03" title="Matching passage review" text="Inspect identified overlapping word sequences alongside their corresponding reference-source passages." />
            </div>
            <div className="center-link"><Link viewTransition className="text-link" to="/features">Explore all features <ArrowRight size={16} /></Link></div>
        </section>
        <section className="workflow-band"><div className="wrap workflow-home"><div className="workflow-intro"><Eyebrow>A CLEAR WORKFLOW</Eyebrow><h2>How AcaSift works</h2><p>Work privately in your personal space or create a shared workspace for a class, team, research group or any collaboration.</p><Link viewTransition className="text-link" to="/how-it-works">See the full process <ArrowRight size={16} /></Link></div><div className="workflow-mini-steps"><MiniStep number="01" title="Build the reference collection" text="A workspace owner or authorised member adds reference documents to the shared collection." /><MiniStep number="02" title="Submit an academic document" text="A workspace member uploads a PDF, DOCX or TXT document." /><MiniStep number="03" title="Compare and review" text="AcaSift calculates similarity indicators and presents matching passages by source." /></div></div></section>
        <section className="section wrap"><div className="integrity-panel"><div className="integrity-icon"><ShieldCheck size={24} /></div><div><Eyebrow>IMPORTANT TO UNDERSTAND</Eyebrow><h2>A similarity score is a signal, not a verdict.</h2><p>Text overlap can occur in properly cited quotations, references, standard terminology and commonly used phrases. AcaSift provides indicators and matching passages for human assessment. It does not independently determine whether plagiarism has occurred.</p></div><Link viewTransition className="button button-outline" to="/faq">Read the FAQs</Link></div></section>
        <section className="closing-cta"><div className="wrap closing-cta-inner"><div><Eyebrow>ACASIFT WORKSPACE</Eyebrow><h2>Ready to review a document?</h2><p>Sign in to your personal or shared AcaSift workspace.</p></div><Link viewTransition className="button button-light button-lg" to="/login">Sign in <ArrowRight size={17} /></Link></div></section>
    </>;
}

function FeatureCard({ icon, number, title, text }: { icon: ReactNode; number: string; title: string; text: string; }) {
    return <article className="feature-card"><div className="feature-card-top"><span className="feature-icon">{icon}</span><span className="feature-number">{number}</span></div><h3>{title}</h3><p>{text}</p><Link viewTransition to="/features">Explore feature <ArrowRight size={14} /></Link></article>;
}
function MiniStep({ number, title, text }: { number: string; title: string; text: string; }) {
    return <div className="mini-step"><span>{number}</span><div><h3>{title}</h3><p>{text}</p></div></div>;
}

export function AboutPage() {
    return <PublicPage eyebrow="ABOUT ACASIFT" title="A clearer way to review document similarity." intro="AcaSift is an academic document similarity analysis platform designed to support structured comparison and careful source review." >
        <div className="prose-grid"><div><h2>Our purpose</h2><p>Academic work depends on the responsible use of sources. Reviewing a submitted document for textual overlap can be time-consuming when documents, reference materials and observations are kept in separate places.</p><p>AcaSift brings several parts of that review process together. It extracts text from supported document formats, compares a submission with an authorised reference collection and presents similarity indicators alongside identified matching passages.</p></div><div className="side-note"><Fingerprint size={24} /><h3>Designed for informed review</h3><p>The platform is intended to help reviewers identify material that may deserve closer examination. It does not make disciplinary decisions or replace academic judgement.</p></div></div>
        <div className="section-subheading"><h2>What guides the platform</h2></div><div className="principle-grid"><Principle icon={<Target />} title="Clarity" text="Present comparison results in a way that users can inspect and understand." /><Principle icon={<BookOpen />} title="Source context" text="Show the reference documents and matching passages behind the indicators." /><Principle icon={<ShieldCheck />} title="Responsible interpretation" text="Treat similarity as evidence for review, not proof of plagiarism." /></div>
        <Notice tone="info"><strong>Current scope:</strong> AcaSift compares submissions with documents already stored in its internal reference repository. It does not currently crawl the internet or search external academic databases.</Notice>
    </PublicPage>;
}

export function FeaturesPage() {
    const features = [
        { icon: <FileText />, title: 'Document text extraction', text: 'Extract readable text from PDF, DOCX and TXT files before comparison.' },
        { icon: <Layers3 />, title: 'TF-IDF and cosine similarity', text: 'Represent document text using TF-IDF features and calculate cosine similarity between a submission and available reference documents.' },
        { icon: <SearchCheck />, title: 'Word N-gram matching', text: 'Identify repeated sequences of words and calculate the proportion of unique submission N-grams that also occur in a reference document.' },
        { icon: <MessageSquareText />, title: 'Passage-level review', text: 'Present identified matching passages with their corresponding excerpts from the reference source.' },
        { icon: <LockKeyhole />, title: 'Account-controlled workspace', text: 'Use a private personal workspace or create shared workspaces with role-based access and invitation links.' },
        { icon: <Gauge />, title: 'Comparison history', text: 'Return to previous comparison records and review the results generated for each submitted document.' },
    ];
    return <PublicPage eyebrow="PLATFORM FEATURES" title="Tools for structured similarity review." intro="AcaSift combines text extraction, document-level comparison and passage matching in a single academic review workflow.">
        <div className="feature-detail-grid">{features.map((feature, i) => <article className="feature-detail-card" key={feature.title}><span className="feature-icon">{feature.icon}</span><span className="feature-number">0{i + 1}</span><h3>{feature.title}</h3><p>{feature.text}</p></article>)}</div>
        <div className="section-subheading"><h2>Supported formats and current boundaries</h2></div><div className="format-grid"><div><strong>PDF</strong><span>Text-based PDF documents</span></div><div><strong>DOCX</strong><span>Microsoft Word documents</span></div><div><strong>TXT</strong><span>Plain-text documents</span></div></div>
        <Notice tone="warning"><strong>Important limitations:</strong> Scanned image-only PDFs, OCR, internet-wide search, external academic database search, source-code comparison, cross-language comparison and semantic paraphrase detection are not included in the current release.</Notice>
    </PublicPage>;
}

export function HowItWorksPage() {
    const steps = [
        { n: '01', icon: <BookOpen />, title: 'An authorised workspace member builds the reference collection', text: 'An authorised workspace member uploads reference documents. These become comparison sources available within the relevant workspace or platform scope.' },
        { n: '02', icon: <Upload />, title: 'A user submits a document', text: 'An authorised user signs in and uploads an academic document in PDF, DOCX or TXT format. AcaSift extracts its readable text.' },
        { n: '03', icon: <SearchCheck />, title: 'AcaSift compares the text', text: 'The system calculates TF-IDF cosine similarity and checks word-based N-gram overlap against the available reference documents.' },
        { n: '04', icon: <FileCheck2 />, title: 'The user reviews the report', text: 'The report ranks the compared sources and displays similarity indicators and matching passages for human assessment.' },
    ];
    return <PublicPage eyebrow="HOW IT WORKS" title="A transparent, four-stage process." intro="AcaSift separates reference collection management, document submission, automated comparison and human review.">
        <div className="process-list">{steps.map(step => <article className="process-step" key={step.n}><div className="process-number">{step.n}</div><div className="process-icon">{step.icon}</div><div><h3>{step.title}</h3><p>{step.text}</p></div></article>)}</div>
        <div className="section-subheading"><h2>Understanding the report</h2></div><div className="report-explainer-grid"><div className="explainer-card"><span>01</span><h3>Cosine similarity</h3><p>A document-level measure of how similar the TF-IDF vector representations of two documents are. It is not a percentage of plagiarised content.</p></div><div className="explainer-card"><span>02</span><h3>Matched N-gram coverage</h3><p>The proportion of word-sequence windows in the submitted document that are also found in a reference document. Repeated windows are counted.</p></div><div className="explainer-card"><span>03</span><h3>Matching passages</h3><p>Specific overlapping sequences shown with the corresponding text from the reference document to support contextual review.</p></div></div>
        <Notice tone="info">Results depend on the documents available in the repository and the text that can be extracted from the uploaded files. AcaSift does not establish intent, attribution or academic misconduct.</Notice>
    </PublicPage>;
}

const faqItems = [
    ['What is AcaSift?', 'AcaSift is an academic document similarity analysis platform. It compares uploaded submissions with documents in an authorised reference collection and reports textual similarity indicators and matching passages.'],
    ['Does AcaSift search the entire internet?', 'No. The current release compares submissions with platform-curated reference documents and references available within the active workspace. It does not crawl the internet or query external academic databases.'],
    ['Does a high similarity score prove plagiarism?', 'No. A similarity score is an indicator of textual overlap, not a verdict. Properly cited quotations, references, standard terminology and common phrases can contribute to similarity. A qualified reviewer must interpret the results in context.'],
    ['Which file formats are supported?', 'The current release supports text-based PDF, DOCX and TXT documents. Scanned image-only PDFs are not supported because optical character recognition is not currently included.'],
    ['Does AcaSift require an institutional email?', 'No. Anyone can create an individual account using a personal or work email address. The email address must be verified before the account can be used.'],
    ['What methods does AcaSift use?', 'The current implementation uses TF-IDF vectorisation with cosine similarity for document-level comparison and word-based N-gram matching for identifying overlapping sequences.'],
    ['Does AcaSift detect paraphrased content?', 'The current release focuses on lexical overlap. It does not provide semantic paraphrase detection or cross-language plagiarism detection.'],
    ['Who can view my comparison reports?', 'Individual submissions and reports are private to their owners. Shared workspace access is limited to invited members and their assigned permissions.'],
];

export function FaqPage() {
    const [open, setOpen] = useState<number | null>(0);
    return <PublicPage eyebrow="FREQUENTLY ASKED QUESTIONS" title="Questions about AcaSift." intro="Learn about the platform's capabilities, how similarity results should be interpreted and how to obtain an account.">
        <div className="faq-list">{faqItems.map(([question, answer], i) => <article className={`faq-item ${open === i ? 'faq-open' : ''}`} key={question}><button onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}><span>{question}</span><ChevronDown size={19} /></button>{open === i && <div className="faq-answer"><p>{answer}</p></div>}</article>)}</div>
        <div className="faq-contact"><div><CircleHelp size={22} /><div><h3>Still have a question?</h3><p>Create an individual account using any valid email address. No institutional affiliation is required.</p></div></div><Link viewTransition className="button button-primary" to="/register">Create an account <ArrowRight size={15} /></Link></div>
    </PublicPage>;
}

export function AccessPage() {
    return <PublicPage eyebrow="OPEN REGISTRATION" title="Start with your own private workspace." intro="AcaSift is open to individual users worldwide. You do not need a university affiliation, institutional email address or staff identification number.">
        <div className="access-panel"><div className="access-panel-icon"><LockKeyhole size={26} /></div><div><h2>Create an individual account.</h2><p>Register with your name, a valid email address and a password. We will send a verification link before activating the account. Your personal documents and reports remain private to you.</p><div className="access-steps"><div><span>1</span><p>Create an account using any valid email address.</p></div><div><span>2</span><p>Verify your email address using the link we send you.</p></div><div><span>3</span><p>Sign in and start using your private AcaSift workspace.</p></div></div><Link viewTransition className="button button-primary button-lg" to="/register">Create an account <ArrowRight size={16} /></Link></div></div>
        <p className="access-note">Shared workspaces can be created instantly by any verified AcaSift user. Creating a personal account does not require institutional affiliation.</p>
    </PublicPage>;
}

function Principle({ icon, title, text }: { icon: ReactNode; title: string; text: string; }) {
    return <div className="principle-card"><span className="feature-icon">{icon}</span><h3>{title}</h3><p>{text}</p></div>;
}

function PublicPage({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: ReactNode; }) {
    return <div className="public-subpage"><section className="subpage-hero"><div className="wrap"><Eyebrow>{eyebrow}</Eyebrow><h1>{title}</h1><p>{intro}</p></div></section><div className="wrap subpage-content">{children}</div></div>;
}
