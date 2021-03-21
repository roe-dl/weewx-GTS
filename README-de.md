# weewx-GTS
XType-Erweiterung für WeeWX  
* "Grünlandtemperatursumme" (eine Form der Wachstumsgradtage) 
* Sonnenenergie, ein zusätzlicher 'aggregation_type'
* 'dayET' und 'ET24' als Gegenstück zu 'dayRain' und 'rain24'

## Installation:

1) Download

   wget -O weewx-GTS.zip https://github.com/roe-dl/weewx-GTS/archive/master.zip

2) Aufruf des Installationsprogramms

   sudo wee_extension --install weewx-GTS.zip

3) Prüfung der Konfiguration in weewx.conf

   ```
   [StdWXCalculate]
       [[Calculations]]
           ...
           GTS = software,archvie
           GTSdate = software, archive
           utcoffsetLMT = software, archive
           dayET = prefer_hardware, archive
           ET24 = prefer_hardware, archive
   ...
   [Engine]
       [[Services]]
           ...
           xtype_services = ... ,user.GTS.GTSService
   ```
   
5) Neustart von WeeWX

   ```
   sudo /etc/init.d/weewx stop
   sudo /etc/init.d/weewx start
   ```

## Nutzung in Skins:

Die Werte, die diese Erweiterung bereitstellt, können in allen Skins
von WeeWX genutzt werden. Sie können als Zahlenwerte angezeigt und
als Diagramme dargestellt werden.

### Grünlandtemperatursumme

Die Grünlandtemperatursumme gehört zur Gruppe der unter dem Überbegriff
Wachstumsgradtage zusammengefaßten empirischen Größen, die in Landwirtschaft
und Gartenbau verwendet werden. Sie liefert eine Aussage über den Verlauf 
des Frühjahrs und wann das Pflanzenwachstum beginnt.

#### Werte anzeigen (CheetahGenerator)

* **GTS**: der Wert der Grünlandtemperatursumme (Beispiel: `$current.GTS`)
* **GTSdate**: das Datum, wenn die Grünlandtemperatursumme den Wert von 200
  überschreitet, was als Beginn des Frühlings betrachtet wird (Beispiel: `$day.GTSdate.last`)
* **utcoffsetLMT**: Offfset der Ortszeit gegenüber UTC am Ort der Station
* **LMTtime**: ein String, der die Ortszeit bei der letzten Speicherung
  angibt (nur mit ".raw" nutzbar, Beispiel: `$current.LMTtime.raw`)

Die Werte können zusammen mit jedem Zeitraum verwendet werden, der in
WeeWX verfügbar ist. Es sind die "aggregation_types" "**avg**", "**min**",
"**max**" und "**last**" definiert. Nicht alle Zeiträume sind mit jeder
Zusammenfassung möglich.

Unter https://weewx.com/docs/customizing.htm#Tags ist die Nutzung von
Tags in WeeWX beschrieben.

#### Diagramme (ImageGenerator)

Zur Darstellung von Diagrammen müssen zusätzliche Abschnitte im Bereich
\[ImageGenerator\] der Datei skin.conf definiert werden. Nachfolgend
sind Beispiele angegeben. 

Im Abschnitt \[\[month_images\]\]:

```
        [[[monthGTS]]]
            line_gap_fraction = 0.04
            yscale = 0,None,None
            aggregate_type = avg
            [[[[GTS]]]]
                aggregate_interval = 86400
                label = Grünlandtemperatursumme
```
<img src="monthGTS.png" />
  
Im Abschnitt \[\[year_images\]\]:

```
        [[[yearGTS]]]
            aggregate_type = avg
            [[[[GTS]]]]
                label = Grünlandtemperatursumme
```
<img src="yearGTS.png" />

Diese Beispiele erzeugen Dateien mit den Namen 'monthGTS.png' bzw. 'yearGTS.png'. 
Um sie anzuzeigen, ist ein entsprechendes \<img\> Tag in der Datei index.html.tmpl
einzutragen:
  
```
<img src="monthGTS.png" />
```
```
<img src="yearGTS.png" />
```

### Evapotranspiration

#### Werte anzeigen (CheetahGenerator)

* **dayET**: Summe von ET für den Kalendertag, so wie "dayRain" für den
  Regen
* **ET24**: Summe von ET für die letzten 24 Stunden, so wie rain24 für den
  Regen

#### Diagramme (ImageGenerator)

'dayET' and 'ET24' werden nicht in Diagrammen benutzt.

### Sonnenenergie

"radiation" ist eine in WeeWX standardmäßig bereitgestellte Größe der
momentanen Sonnenstrahlung. Diese Erweiterung stellt den zusätzlichen
"aggregation_type" `energy_integral` zur Verfügung, der die Sonnenenergie
berechnet, die über den Berechnungszeitraum am Meßort eingegangen ist.

Beachte: Ein Integral ist nicht einfach die Summe der Meßwerte. Details
sind unten unter Algorithmus beschrieben.

#### Werte anzeigen (CheetahGenerator)

`energy_integral` kann nur zusammen mit Tags für Zeiträume wie etwa
`$day`, `$yesterday`, `$week`, `$month`, and `$year` benutzt werden.

`energy_integral` wird wie andere "aggregation_types", z.B. `min`,
`max` oder `sum` benutzt.

Beispiel:
`$yesterday.radiation.energy_integral` zeigt die gesamte Sonnenenergie
an, die am Vortag eingegangen ist.

Um den Wert in kWh/m^2 anstelle von Wh/m^2 anzuzeigen:
`$yesterday.radiation.energy_integral.kilowatt_hour_per_meter_squared`

#### Diagramme (ImageGenerator)

Im Abschnitt \[\[month_images\]\]:

```
        [[[monthRadiationEnergy]]]
            line_gap_fraction = 0.04
            #y_label = "Wh/m²"
            [[[[radiation]]]]
                label = "Sonnenenergie (täglich gesamt)"
                data_type = radiation
                aggregate_type = energy_integral
                aggregate_interval = 86400
```

Dieses Beispiel erzeugt eine Bilddatei namens 'monthRadiationEnergy.png'.
Um sie darzustellen, muß das entsprechende \<img\> Tag z.B. in index.html.tmpl
eingefügt werden:

```
<img src="monthRadiationEnergy.png" />
```

#### Diagramme (Belchertown skin)

Die Belchertown Skin benutzt eine andere Graphik-Engine (Highcharts).
Deshalb ist die Syntax etwas anders.

Im Abschnitt \[month\] oder \[year\] von graphs.conf:

```
    [[Sonnenenergie]]
        title = "Sonnenenergie (täglich gesamt)"
        aggregate_type = energy_integral
        aggregate_interval = 86400
        yAxis_label = Energie
        yAxis_label_unit = "Wh/m&sup2;"
        [[[radiation]]]
```

Es wird kein \<img\> Tag benötigt.

## Algorithmus:

### Grünlandtemperatursumme (GTS)

* Grundlage der Berechnuung ist der Tagesmittelwert der Temperatur. Wenn
  er größer als 0°C ist, wird er verwendet, anderenfalls nicht.
* Im Januar wird der Mittelwert mit 0,5 multipliziert.
* Im Februar wird der Mittelwert mit 0,75 multipliziert.
* Ab März werden die Mittelwerte unverändert verwendet.
* Um die Grünlandtemperatursumme eines Tages zu erhalten, werden jetzt
  alle die Mittelwerte wie vorstehend beschrieben zusammenaddiert.
* Der Tag, an dem der Wert 200 überschreitet, wird als Beginn des
  Frühlings betrachtet. Man geht davon aus, daß dann der Boden
  wieder genügend Stickstoff aufnehmen kann, um nachhaltiges
  Pflanzenwachstum zu ermöglichen.
* Die Grünlandtemperatursumme selbst wird bis zum 31. Mai berechnet.
  Der Endwert wird als Maß für die Qualität des Frühlings angesehen.

### Sonnenenergie

Die Sonnenenergie wird berechnet, indem alle Strahlungsmeßwerte 
("radiation") mit dem jeweiligen Meßintervall ("interval") 
multipliziert. Alle die Produkte aus der Multiplikation werden
über den Berechnungszeitraum addiert. Dabei wird der Strahlungswert 
als während dieses
Zeitraumes als konstant angenommen. Das ist nicht hunderprozentig
korrekt, aber der Fehler wird als gering genug angenommen, daß man
ihn vernachlässigen kann. 

Während die Einheit der Sonnenstrahlung W/m^2 ist, ist die Einheit
der Sonnenenergie Wh/m^2 bzw. kWh/m^2.

## Quellen:

* http://www.groitzsch-wetter.de/HP/green1.html
* http://www.regionalwetter-sa.de/sa_gruenland.php

## Verweise (Links):

* [Übersicht zu WeeWX auf Deutsch](https://www.woellsdorf-wetter.de/software/weewx.html)
* [WeeWX](http://weewx.com) - [WeeWX Wiki](https://github.com/weewx/weewx/wiki)
* [Belchertown Skin](https://obrienlabs.net/belchertownweather-com-website-theme-for-weewx/) - [Belchertown skin Wiki](https://github.com/poblabs/weewx-belchertown/wiki)
* [Wöllsdorfer Wetter](https://www.woellsdorf-wetter.de)
