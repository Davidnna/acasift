import { formatDate, StatusPill } from './ui';
import type { DocumentRecord } from '../types';

export function DocumentTable({ documents, compact = false }: { documents: DocumentRecord[]; compact?: boolean; }) {
    return <div className="table-scroll"><table className="data-table"><thead><tr><th>Document</th><th>Category</th>{!compact && <th>Uploaded by</th>}<th>Date added</th><th>Status</th></tr></thead><tbody>{documents.map(doc => <tr key={doc.id}><td><div className="file-cell"><span className="file-type-icon">{doc.file_type.toUpperCase().slice(0, 4)}</span><span><strong>{doc.title}</strong><small>{doc.original_filename}</small></span></div></td><td><span className={`category-tag category-${doc.document_type}`}>{doc.document_type === 'reference' ? 'Reference' : 'Submission'}</span></td>{!compact && <td>{doc.uploader || '—'}</td>}<td>{formatDate(doc.uploaded_at)}</td><td><StatusPill value={doc.processing_status} /></td></tr>)}</tbody></table></div>;
}