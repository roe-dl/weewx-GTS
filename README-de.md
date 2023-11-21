# weewx-GTS
XType-Erweiterung für WeeWX  
* "Grünlandtemperatursumme" (eine Form der Wachstumsgradtage) 
* Sonnenenergie, ein zusätzlicher 'aggregation_type'
* 'dayET' und 'ET24' als Gegenstück zu 'dayRain' und 'rain24'
* (potentielle) Äquivalenttemperatur, Mischungsverhältnis, 
  absolute Luftfeuchtigkeit, (Sättigungs)Dampfdruck
* Tags für Zeitspannen mit einer anderen Tagesgrenze als Mitternacht
* `yearGDD` und `seasonGDD`
* `aggregation_type` `GDD` zur Berechnung der Wachstumsgradtage nach verschiedenen Verfahren

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
           GTS = software,archive
           GTSdate = software, archive
           utcoffsetLMT = software, archive
           dayET = prefer_hardware, archive
           ET24 = prefer_hardware, archive
           yearGDD = software
           seasonGDD = software
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
  überschreitet, was als Beginn des Frühlings betrachtet wird (Beispiel: `$day.GTSdate.last.format("%d.%m.%Y")`)
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

### Wachstumsgradtage

#### Werte anzeigen (CheetahGenerator)

* **yearGDD**: Summe oder Integral der Wachstumsgrade vom Anfang des Jahres bis zum
  zum aktuellen Moment
* **seasonGDD**: Summe oder Integral der Wachstumsgrade beginnend beim Datum von `GTSdate`
  bis zum aktuellen Moment. Vor `GTSdate` ist der Wert undefiniert, ebenso nach dem
  31. Oktober
* `aggregation_type` **GDD** (oder **growdeg**): Zur Berechnung der Wachstumsgradtage
  für andere Größen als `outTemp`. Das kann jeder Temperaturwert sein, zum Beispiel
  die Gewächshaustemperatur.

#### Diagramme (ImageGenerator)

Im Abschnitt \[\[year_images\]\]:

```
        [[[yearGDD]]]
            aggregate_type = avg
            [[[[yearGDD]]]]
                label = Growing degree days
            [[[[seasonGDD]]]]
                label = Season growing degree days
```

Dieses Beispiel erzeugt eine Graphikdatei namens "yearGDD.png". Um sie anzuzeigen,
muß das entsprechende &lt;img&gt; Tag zum Beispiel in index.html.tmpl eingefügt werden:

```
<img src="yearGDD.png" />
```

Die Graphik kann auch mit der Grünlandtemperatursumme kombiniert werden:

```
        [[[yearGTS]]]
            aggregate_type = avg
            [[[[GTS]]]]
                label = Grünlandtemperatursumme
            [[[[yearGDD]]]]
                label = Growing degree days
            [[[[seasonGDD]]]]
                label = Season growing degree days
```

Um dieses Diagramm anzuzeigen, ist folgende Eintragung zum Beispiel in index.html.tmpl nötig:

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

### Spezielle abgeleitete meteorologische Größen

WeeWX enthält bereits Berechnungsfunktionen für diverse abgeleitete
meteorologische Größen, die aber nur intern verwendet werden. Mit
dieser Erweiterung werden sie für die Berechnung im Abschnitt
`[StdWXCalculate]` und zur Nutzung auf Webseiten und in Diagrammen
bereitgestellt.

Beachte: WeeWX enthält ein Beispiel, wie Erweiterungen programmiert
werden, das einen "Dampfdruck" (vapor pressure) bezeichneten
Wert liefert. In Wirklichkeit wird dort aber der Sättigungsdampfdruck
berechnet. Und die Formel ist auch eine andere als WeeWX sie intern
benutzt.

Warnung: Dieser Teil ist noch im Alpha-Status.

#### Werte anzeigen (CheetahGenerator)

* `outSVP`: Sättigungsdampfdruck
* `outVaporP`: aktueller Dampfdruck
* `outMxingRatio`: Mischungsverhältnis
* `outHumAbs`: absolute Luftfeuchtigkeit
* `outEquiTemp`: Äquivalenttemperatur
* `outThetaE`: potentielle Äquivalenttemperatur
* `boilingTemp`: Siedetemperatur des Wassers in Abhängigkeit von
  der Meereshöhe der Station und dem aktuellen Luftdruck

#### Diagramme (ImageGenerator)

Um Diagramme mit diesen Werten darzustellen, ist es nicht nötig, sie
in der Datenbank zu speichern. Nur die Ausgangswerte Außentemperatur,
relative Luftfeuchtigkeit und Stationsluftdruck müssen vorhanden
sein. Dann erfolgt die Berechnung live bei der Darstellung des
Diagramms.

Beispiel: absolute Luftfeuchtigkeit

```
        [[[dayhumabs]]]
            unit = gram_per_meter_cubed
            [[[[outHumAbs]]]]
```

<img src="dayhumabs.png" />

#### Diagramme (Belchertown skin)

Beispiel: relative und absolute Luftfeuchtigkeit in einem Diagramm:

```
    [[humidity]]
        title = "Humidity"
        [[[outHumidity]]]
            name = "relative
        [[[outHumAbs]]]
            name = "absolute"
            yAxis = 1
            unit = gram_per_meter_cubed
            [[[[numberFormat]]]]
                decimals = 1
```

<img src="luftfeuchtigkeit.png" />

### Sonnenenergie

"radiation" und "maxSolarRad" sind in WeeWX standardmäßig bereitgestellte 
Größen. Diese Erweiterung stellt den zusätzlichen
"aggregation_type" `energy_integral` zur Verfügung, der die Sonnenenergie
berechnet, die über den Berechnungszeitraum am Meßort eingegangen ist
bzw. maximal möglich wäre.

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

#### Textdatei

Im "examples"-Verzeichnis ist eine Vorlage (template) zu finden, die
eine Textdatei mit den tabellierten Werten von Sonnenenergie und
Sonnenstrahlung erzeugt. Um sie zu nutzen, muß die Datei in das
Skin-Verzeichnis kopiert werden. In `skin.conf` sind dann folgende
Eintragungen vorzunehmen:

```
[CheetahGenerator]
    ...
    [[SummaryByYear]]
        ...
        [[[sun_year]]]
            encoding = strict_ascii
            template = sun-%Y.txt.tmpl
```

Damit wird für jedes Jahr, für das Daten in der Datenbank verfügbar
sind, eine Datei erzeugt. 

### Bodenfeuchte

WeeWX definiert die Einheitengruppe `group_moisture` mit der Einheit
`centibar`, wohl in Anlehnung an die von Davis Instruments vertriebene
Bodenfeuchte-Bodentemperatur-Einheit 6345. Diese Einheit mißt genaugenommen
nicht die Feuchte sondern die Saugspannung.

Anstelle der Saugspannung, gemessen in einer Druckeinheit, wird auch
die logarithmische Größe pF-Wert benutzt. Diese WeeWX-Erweiterung
stellt diese Größe als zusätzliche Einheit `pF_value` für
`group_moisture` bereit. Sie ermöglicht gleichzeitig, auch andere
Druckeinheiten als nur `centibar` zu nutzen.

### Besondere Zeitspannen

In der Meteorologie werden Zeitspannen zuweilen nicht von Mitternacht zu Mitternacht
der geltenenden Zonenzeit gemessen, sondern es werden andere Zeitpunkte zur Trennung
der Tage verwendet, zum Beispiel 09:00 Uhr. Die folgenden Tags werden genau so wie
`$hour`, `$day` usw. benutzt.

#### Beliebiges Offset zu UTC

* `$offsethour(data_binding=None, hours_ago=0, dayboundary=None)`
* `$offsetday(data_binding=None, days_ago=0, dayboundary=None)`
* `$offsetyesterday(data_binding=None, dayboundary=None)`
* `$offsetmonth(data_binding=None, months_ago=0, dayboundary=None)`
* `$offsetyear(data_binding=None, years_ago=0, dayboundary=None)`

#### Mittlere Ortszeit am Ort der Station

* `$LMThour(data_binding=None, hours_ago=0)`
* `$LMTday(data_binding=None, days_ago=0)`
* `$LMTyesterday(data_binding=None)`
* `$LMTmonth(data_binding=None, months_ago=0)`
* `$LMTyear(data_binding=None, years_ago=0, month_span=None)`

Die Tagesgrenze für diese Tags ist Mitternacht nach der Mittleren
Ortszeit am Ort der Station. 

Der optionale Parameter `month_span` ergibt eine Zeitspanne von 
einigen Monaten innerhalb eines gegebenen Jahres. Zum Beispiel
ist `$LMTyear(month_span=(6,8)).outTemp.avg` die Durchschnittstemperatur
des Sommers des aktuellen Jahres. 
`$LMTyear(years_ago=1,month_span=(12,2)).outTemp.max` ist die
Maximaltemperatur der letzten Windersaison.

Das Attribut `days` kann verwendet werden, um mittels `$LMTmonth` 
bzw. `$LMTyear` eine Schleife über die Tage des Monats bzw. Jahres
zu bilden.

### Zeitspanne `daylight`

<img src="daylight-timespan.png" />

* `$daylight(timestamp=None, data_binding=None, days_ago=0, horizon=None, use_center=False)`: 

   Zeitspanne von
   Sonnenaufgang bis Sonnenuntergang

   Wenn `timestamp` None ist (das ist der Standard), dann ist es die Zeitspanne
   von Sonnenaufgang bis Sonnenuntergang am gegenwärtigen Tag oder an
   dem Tag, der `day_ago` Tage zurückliegt.

   Sonst kann `timestamp` ein Wert der Klasse TimespanBinder, eine Zeitspanne
   oder ein Zeitpunkt sein. `$daylight` ist dann die Zeitspanne 
   von Sonnenaufgang bis Sonnenuntergang an dem Tag, der durch
   die Zeitspanne oder den Zeitpunkt definiert wird.

* `$LMTmonth(data_binding=None, months_ago=0).daylights(horizon=None, use_center=False)`: 

  Folge von täglichen Zeitspannen, pro Tag jeweils die 
  Zeit von Sonnenaufgang zu Sonnenuntergang

* `$LMTyear(data_binding=None, months_ago=0).daylights(horizon=None, use_center=False)`: 

  Folge von täglichen Zeitspannen, pro Tag jeweils die
  Zeit von Sonnenaufgang zu Sonnenuntergang

Die Optionen `horizon` und `use_center` entsprechend denen, die im
[WeeWX Benutzerhandbuch](https://weewx.com/docs/customizing.htm#Heavenly_bodies)  
für `$almanac` beschrieben sind. Sind sie nicht angegeben, werden
Standardwerte benutzt.

Beispiele:

* Durchschnittstemperatur für die Zeit zwischen Sonnenaufgang und
  Sonnenuntergang, also während der Zeit des Tageslichtes
  ```
  $daylight.outTemp.avg
  ```
* Tabelle mit dem Tag des Monats und der zugehörigen 
  Durchschnittstemperatur für die Zeit des Tageslichts des
  jeweiligen Tages
  ```
  #for $span in $LMTmonth.daylights
  <p>$span.dateTime.format("%d"): $span.outTemp.avg</p>
  #end for
  ```
* Regen am Tag und in der Nacht
  ```
  #from weewx.units import ValueTuple, ValueHelper
  <table>
  <tr>
  <th>Day</th>
  <th>Day rain</th>
  <th>Night rain</th>
  </tr>
  #for $dd in $week.days
  #set $light=$daylight(timestamp=$dd)
  #set $nightrain=$dd.rain.sum.raw-$light.rain.sum.raw
  #set $nightrain_vh=ValueHelper(ValueTuple($nightrain,$unit.unit_type.rain,'group_rain'),formatter=$station.formatter)
  <tr>
  <td>$dd.start.format("%d.%m.%Y")</td>
  <td>$light.rain.sum</td>
  <td>$nightrain_vh</td>
  </tr>
  #end for
  </table>
  ```
* Sonnenaufgang, Sonnenuntergang und Tageslichtlänge unter
  Verwendung der  `timestamp`-Option
  ```
  <table>
  <tr>
    <th>sunrise</th>
    <th>sunset</th>
    <th>daylight</th>
  </tr>
  #for $dd in $week.days
  <tr>
    <td>$dd.format("%A")</td>
    <td>$daylight(timestamp=$dd).start</td>
    <td>$daylight(timestamp=$dd).end</td>
    <td>$daylight(timestamp=$dd).length</td>
  </tr>
  #end for
  </table>
  ```


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

### Tageslichtzeitraum

`$daylight` verwendet zur Berechnung das Modul von WeeWX, das 
auch von `$almanac` verwendet wird, aber es berücksichtigt dabei
zusäztliche Informationen.

Während `$almanac.sunrise` und `$almanac.sunset` Sonnenaufgang und 
Sonnenuntergang unter Verwendung der Temperatur und des Luftdrucks 
zur Berechnungszeit ermitteln, berücksichtigt `$daylight` Temperatur 
und Luftdruck der Zeit, für die die Tageslichtzeitspanne berechnet 
wird, soweit Datenbankeinträge für diese Zeit vorhanden sind. Es 
berechnet zunächst ungefähre Sonnenaufgangs- und Sonnenuntergangszeiten 
für die ICAO-Standardatmosphäre bei 15°C und 1013,25 mbar. Dann wird 
die tatsächliche Temperatur und der tatsächliche Luftdruck für diese 
beiden Zeitpunkte ermittelt. Anschließend werden Sonnenaufgang und 
Sonnenuntergang erneut berechnet, wobei der Berechnung die jeweilige 
Temperatur und der jeweilige Luftdruck zu Grunde gelegt werden.

`$daylight(timestamp=$X).start` liefert damit für Zeitpunkte X in
der Vergangenheit eine genauere Sonnenaufgangszeit als
`$almanac(almanac_time=X).sunrise`. Gleiches gilt mit
`$daylight(timestamp=$X).end` sinngemäß für den Sonnenuntergang
und mit `$daylight(timestamp=$X).length` für die Tageslichtlänge.
(Stand: WeeWX 4.9.2)

## Quellen:

* http://www.groitzsch-wetter.de/HP/green1.html
* http://www.regionalwetter-sa.de/sa_gruenland.php
* WeeWX-Beispiel examples/stats.py

## Verweise (Links):

* [Übersicht zu WeeWX auf Deutsch](https://www.woellsdorf-wetter.de/software/weewx.html)
* [WeeWX](http://weewx.com) - [WeeWX Wiki](https://github.com/weewx/weewx/wiki)
* [Belchertown Skin](https://obrienlabs.net/belchertownweather-com-website-theme-for-weewx/) - [Belchertown skin Wiki](https://github.com/poblabs/weewx-belchertown/wiki)
* [Wöllsdorfer Wetter](https://www.woellsdorf-wetter.de)
