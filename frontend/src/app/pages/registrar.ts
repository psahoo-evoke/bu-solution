import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../api/api.service';
import { describeError } from '../api/errors';
import { Student } from '../api/models';
import { can, switchRoleMessage } from '../api/permissions';
import { RoleService } from '../api/role.service';
import { ErrorBanner } from '../shared/error-banner';

@Component({
  selector: 'app-registrar',
  imports: [FormsModule, ErrorBanner],
  templateUrl: './registrar.html',
})
export class RegistrarPage {
  private readonly api = inject(ApiService);
  protected readonly roles = inject(RoleService);

  protected readonly students = signal<Student[]>([]);
  protected readonly studentId = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly message = signal<string | null>(null);
  protected readonly downloading = signal(false);
  protected readonly resetting = signal(false);
  protected readonly preview = signal<string[][]>([]);
  protected readonly posting = signal(false);
  protected readonly posted = signal<{ count: number; rows: string[][] } | null>(null);
  protected readonly canPost = computed(() => can(this.roles.role(), 'post'));
  protected readonly postHint = switchRoleMessage('post');
  protected readonly canExport = computed(() => can(this.roles.role(), 'export'));
  protected readonly canReset = computed(() => can(this.roles.role(), 'reset'));
  protected readonly exportHint = switchRoleMessage('export');
  protected readonly resetHint = switchRoleMessage('reset');

  constructor() {
    this.api.listStudents().subscribe({ next: (s) => this.students.set(s), error: () => this.students.set([]) });
  }

  download(): void {
    if (!this.canExport()) return;
    this.downloading.set(true);
    this.error.set(null);
    this.message.set(null);
    const sid = this.studentId() || undefined;
    this.api.exportMyBu(sid).subscribe({
      next: async (blob) => {
        this.downloading.set(false);
        const name = `mybu_export${sid ? '_' + sid : ''}.csv`;
        saveBlob(blob, name);
        try {
          const text = await blob.text();
          const rows = parseCsv(text);
          this.preview.set(rows.slice(0, 11));
          this.message.set(`Downloaded ${name} (${Math.max(rows.length - 1, 0)} rows).`);
        } catch {
          this.message.set(`Downloaded ${name}.`);
        }
      },
      error: (err) => {
        this.downloading.set(false);
        this.error.set(describeError(err, this.roles.role(), 'export'));
      },
    });
  }

  /** Registrar step (POST /postings): approved lines become posted, so students see them as secured (T). */
  post(): void {
    if (!this.canPost()) return;
    this.posting.set(true);
    this.error.set(null);
    this.message.set(null);
    const sid = this.studentId() || undefined;
    this.api.postApproved(sid ? { student_id: sid } : {}).subscribe({
      next: (res) => {
        this.posting.set(false);
        this.posted.set({ count: res.posted, rows: parseCsv(res.csv ?? '') });
        this.message.set(
          res.posted
            ? `Posted ${res.posted} approved ${res.posted === 1 ? 'course' : 'courses'}. Students now see them as secured (T).`
            : 'Nothing to post: no approved courses are awaiting posting.',
        );
      },
      error: (err) => {
        this.posting.set(false);
        this.error.set(describeError(err, this.roles.role(), 'post'));
      },
    });
  }

  reset(): void {
    if (!this.canReset()) return;
    if (!confirm('Reset the demo? Decisions made during the demo will be removed.')) return;
    this.resetting.set(true);
    this.error.set(null);
    this.api.resetDemo().subscribe({
      next: () => {
        this.resetting.set(false);
        this.preview.set([]);
        this.posted.set(null);
        this.message.set('Demo reset to the original data.');
      },
      error: (err) => {
        this.resetting.set(false);
        this.error.set(describeError(err, this.roles.role(), 'reset'));
      },
    });
  }
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Minimal CSV parser for the preview (handles quoted fields). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') {
      row.push(field);
      field = '';
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else field += ch;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.length > 1 || r[0] !== '');
}
