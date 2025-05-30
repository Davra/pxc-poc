import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { MatTableModule } from '@angular/material/table';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { environment } from '../../environments/environment'; // Adjust the path as necessary

interface Device {
  name: string;
  UUID: string;
  lastSeen: string;
}

@Component({
  selector: 'app-devices',
  standalone: true,
  imports: [MatTableModule,CommonModule ],
  templateUrl: './devices.html',
  styleUrls: ['./devices.css']
})
export class DevicesComponent implements OnInit {
  displayedColumns: string[] = ['name', 'UUID', 'lastSeen'];
  dataSource: Device[] = [];
  
  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    console.log(environment.DEV_TOKEN)
    // Use the DEV_TOKEN from environment variables to set the Authorization header
    const headers = environment.DEV_TOKEN ? new HttpHeaders({
      Authorization: 'Bearer ' + environment.DEV_TOKEN,
    }) : undefined;

    this.http.get<{totalRecords:Number, records:Device[]}>( environment.SERVER_URL + 'api/v1/devices/?limit=10&start=0', { headers })
      .subscribe(data => {
        this.dataSource = data.records;
        this.cdr.detectChanges();
      } );
  }
}