import { Routes } from '@angular/router';
// ...existing code...
import { DevicesComponent } from './devices/devices';
import { HomeComponent } from './home/home'; // Adjust the import path as necessary

export const routes: Routes = [
  { path: 'devices', component: DevicesComponent },
  { path: '', component: HomeComponent,  }
];