import { Component } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-home',
  imports: [MatIconModule],
  templateUrl: './home.html',
  styleUrl: './home.css'
})
export class HomeComponent {
  protected title = 'Home Page';
  protected description = 'Welcome to the Angular Demo App! This is the home page where you can find information about the application.';

}
