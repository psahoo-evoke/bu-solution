import { Component, computed, input } from '@angular/core';
import { BuStatusCode } from '../api/models';
import { CODE_MEANING, toneFor } from './status';

@Component({
  selector: 'app-status-chip',
  template: `<span class="chip chip--{{ tone() }}" [attr.title]="meaning()"
    ><span class="chip__text">{{ label() }}</span> <span class="chip__code" [attr.aria-label]="'BU code ' + code()">{{ code() }}</span></span
  >`,
})
export class StatusChip {
  readonly code = input.required<BuStatusCode>();
  readonly label = input<string>('');
  protected readonly tone = computed(() => toneFor(this.code()));
  protected readonly meaning = computed(() => CODE_MEANING[this.code()] ?? '');
}
