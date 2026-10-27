import { Component } from '@angular/core';
import { Painel } from './painel/painel';

@Component({
  selector: 'app-root',
  imports: [Painel],
  template: '<app-painel />',
})
export class App {}
