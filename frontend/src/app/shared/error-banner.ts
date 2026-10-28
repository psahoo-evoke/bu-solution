import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-error-banner',
  template: `@if (message()) {
    <div class="banner banner--error" role="alert">
      <strong>Problem:</strong> {{ message() }}
      @if (retryable()) {
        <button type="button" class="btn btn--small" (click)="retry.emit()">Retry</button>
      }
    </div>
  }`,
})
export class ErrorBanner {
  readonly message = input<string | null>(null);
  readonly retryable = input(true);
  readonly retry = output<void>();
}
