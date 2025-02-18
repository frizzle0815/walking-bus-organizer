# Walking Bus Organizer

Eine Webanwendung zur Organisation von Laufgemeinschaften für den Schulweg, entwickelt mit Unterstützung von KI (Sourcegraph Cody).

## Funktionen

- **Echtzeit-Dashboard**
  - Live-Übersicht aller Stationen und Teilnehmer
  - Visuelle Statusanzeigen (Zusage/Absage) 
  - Sofortige Updates via Server-Sent Events (SSE)

- **Administrationsoberfläche**
  - Verwaltung von Stationen und Teilnehmern
  - Drag & Drop Neuordnung
  - Konfiguration des wöchentlichen Zeitplans
  - Festlegung der Standard-Teilnahmetage

- **Kalender-Management** 
  - Individuelle Teilnahmeplanung
  - Monatsübersicht des Teilnahmestatus
  - Schnelles Umschalten zwischen Teilnahme/keine Teilnahme
  - Überschreiben der wöchentlichen Standardeinstellungen

- **Progressive Web App (PWA)**
  - Offline-Funktionalität
  - Mobile-optimierte Oberfläche
  - Installation auf dem Startbildschirm

## Technischer Stack

- **Backend**
  - Flask (Python Web-Framework)
  - SQLAlchemy (ORM)
  - PostgreSQL (Datenbank)
  - Server-Sent Events für Echtzeit-Updates

- **Frontend**
  - HTML5, CSS3, JavaScript
  - Bootstrap 5 für das Styling
  - Font Awesome Icons
  - Axios für API-Anfragen
  - SortableJS für Drag & Drop

## Installation

1. Repository klonen:
   
```   
git clone https://github.com/frizzle0815/walking-bus-organizer.git
```

2. Abhängigkeiten installieren:

```
pip install -r requirements.txt
```

3. Umgebungsvariablen setzen:
   
```
export DATABASE_URL="postgresql://benutzername:passwort@localhost:5432/walkingbus"
export APP_TIMEZONE="Europe/Berlin"
```

4. Datenbank initialisieren:

```
flask db upgrade
```

5. Anwendung starten:

```
flask run
```

## Verwendung

- **Dashboard (index.html)**
  - Übersicht aller Stationen und Teilnehmer
  - Teilnahmestatus ändern
  - Zugriff auf individuelle Kalender
  - Echtzeit-Aktualisierungen verfolgen

- **Admin-Panel (admin.html)**
  - Stationen und Teilnehmer hinzufügen/entfernen
  - Walking Bus Zeitplan konfigurieren
  - Standard-Teilnahmetage festlegen
  - Stationen und Teilnehmer neu ordnen

- **API-Endpunkte**
  - Stationen und Teilnehmer hinzufügen/entfernen
  - Walking Bus Zeitplan konfigurieren
  - Standard-Teilnahmetage festlegen
  - Stationen und Teilnehmer neu ordnen

## API-Endpunkte

- **Stationen**
  - `GET /api/stations` - Alle Stationen auflisten
  - `POST /api/stations` - Neue Station erstellen
  - `PUT /api/stations/<id>` - Station aktualisieren
  - `DELETE /api/stations/<id>` - Station löschen

- **Teilnehmer**
  - `POST /api/participants` - Neuen Teilnehmer hinzufügen
  - `PUT /api/stations/<station_id>/participants/<id>` - Teilnehmer aktualisieren
  - `DELETE /api/participants/<id>` - Teilnehmer entfernen
  - `PATCH /api/participation/<id>` - Teilnahmestatus umschalten

- **Kalender**
  - `GET /api/calendar-data/<participant_id>` - Kalenderdaten abrufen
  - `POST /api/calendar-status` - Kalenderstatus aktualisieren

## Mitwirken

1. Repository forken
2. Feature-Branch erstellen (git checkout -b feature/TollesFunktion)
3. Änderungen committen (git commit -m 'Tolle Funktion hinzugefügt')
4. Branch pushen (git push origin feature/TollesFunktion)
5. Pull Request erstellen

## KI-Unterstützung

Dieses Projekt wurde mit Hilfe von Sourcegraph Cody entwickelt. Die KI unterstützte bei:

- Code-Generierung
- Debugging
- Optimierung der Funktionalität
- Dokumentation
