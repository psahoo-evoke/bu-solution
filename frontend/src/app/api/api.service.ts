import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  BatchDecisionInput,
  Decision,
  DecisionInput,
  Metrics,
  PostingInput,
  PostingResult,
  ReasonCode,
  Recommendation,
  ReviewItem,
  Rule,
  Student,
  StudentEvaluation,
  SyllabusCheck,
} from './models';

export const API_BASE = '/api';

/** ext_id is "SCHOOL|CODE" and must be URL-encoded in paths (openapi: parameters.ExtId). */
export function encodeExtId(extId: string): string {
  return encodeURIComponent(extId);
}

/** Typed client for docs/api/openapi.yaml. One method per operation. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>(`${API_BASE}/health`);
  }

  listStudents(): Observable<Student[]> {
    return this.http.get<Student[]>(`${API_BASE}/students`);
  }

  getStudentEvaluation(studentId: string): Observable<StudentEvaluation> {
    return this.http.get<StudentEvaluation>(`${API_BASE}/students/${encodeURIComponent(studentId)}/evaluation`);
  }

  uploadTranscript(studentId: string, file: File): Observable<StudentEvaluation> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post<StudentEvaluation>(
      `${API_BASE}/students/${encodeURIComponent(studentId)}/transcripts`,
      form,
    );
  }

  uploadSyllabus(extId: string, file: File): Observable<SyllabusCheck> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post<SyllabusCheck>(`${API_BASE}/courses/${encodeExtId(extId)}/syllabus`, form);
  }

  getRecommendation(extId: string): Observable<Recommendation> {
    return this.http.get<Recommendation>(`${API_BASE}/courses/${encodeExtId(extId)}/recommendation`);
  }

  getReviewQueue(department?: string): Observable<ReviewItem[]> {
    let params = new HttpParams();
    if (department) params = params.set('department', department);
    return this.http.get<ReviewItem[]>(`${API_BASE}/review-queue`, { params });
  }

  postDecision(input: DecisionInput): Observable<Decision> {
    return this.http.post<Decision>(`${API_BASE}/decisions`, input);
  }

  postBatch(input: BatchDecisionInput): Observable<Decision[]> {
    return this.http.post<Decision[]>(`${API_BASE}/decisions/batch`, input);
  }

  exportMyBu(studentId?: string): Observable<Blob> {
    let params = new HttpParams();
    if (studentId) params = params.set('student_id', studentId);
    return this.http.get(`${API_BASE}/exports/mybu.csv`, { params, responseType: 'blob' });
  }

  /** Registrar step: approved lines become posted (secured). */
  postApproved(input: PostingInput = {}): Observable<PostingResult> {
    return this.http.post<PostingResult>(`${API_BASE}/postings`, input);
  }

  getMetrics(): Observable<Metrics> {
    return this.http.get<Metrics>(`${API_BASE}/evaluation/metrics`);
  }

  getRules(): Observable<Rule[]> {
    return this.http.get<Rule[]>(`${API_BASE}/rules`);
  }

  listReasonCodes(): Observable<ReasonCode[]> {
    return this.http.get<ReasonCode[]>(`${API_BASE}/reason-codes`);
  }

  resetDemo(): Observable<void> {
    return this.http.post<void>(`${API_BASE}/demo/reset`, null);
  }
}
