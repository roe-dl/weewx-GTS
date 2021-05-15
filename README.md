# weewx-GTS
XType extension for WeeWX to provide 
* "Grünlandtemperatursumme" (a kind of growing degree days) 
* observation types 'dayET' and 'ET24' as the opposite to 'dayRain' and 'rain24'
* additional aggregation type for 'radiation' to calculate the total energy received during the aggregation interval

## Installation instructions:

1) download

   wget -O weewx-GTS.zip https://github.com/roe-dl/weewx-GTS/archive/master.zip

2) run the installer

   sudo wee_extension --install weewx-GTS.zip

3) check configuration in weewx.conf

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
   
5) restart weewx

   ```
   sudo /etc/init.d/weewx stop
   sudo /etc/init.d/weewx start
   ```

## Including in skins:

You can use the values provided by this extensions in all skins of WeeWX. You can show the values, and you can create a diagram. The following observation types are provided:

### Grünlandtemperatursumme

"Grünlandtemperatursumme" is a kind of growing degree days that is used
to estimate the start of growing of the plants. For the algorithm see
below.

#### Display values (CheetahGenerator)

* **GTS**: the value of "Grünlandtemperatursumme" itself (example tag: `$current.GTS`)
* **GTSdate**: the date when the GTS value exceeds 200, which is considered the beginning of real spring (example tag: `$day.GTSdate.last`)
* **utcoffsetLMT**: offfset of the local mean time (Ortszeit) at the station's location
* **LMTtime**: a string showing the local mean time (Ortszeit) at the station's location (can only be used with ".raw", example tag: `$current.LMTtime.raw`)

The values can be used together with every time period defined in the customization guide of WeeWX. There can be used aggregations as well. The following aggregations are defined: "**avg**", "**min**", "**max**", "**last**". Not all time spans are possible. 

See http://weewx.com/docs/customizing.htm#Tags for details on how to use tags in skins.

#### Diagrams (ImageGenerator)

To create diagrams you need to include additional sections into the \[ImageGenerator\] section of skin.conf. What follows are examples. There are more possibilities than that.

Within \[\[month_images\]\]:

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
  
Within \[\[year_images\]\]:

```
        [[[yearGTS]]]
            aggregate_type = avg
            [[[[GTS]]]]
                label = Grünlandtemperatursumme
```
<img src="yearGTS.png" />

These examples create image files named 'monthGTS.png' or 'yearGTS.png', respectively. To display them within the web page appropriate \<img\> tags need to be included for example in index.html.tmpl:
  
```
<img src="monthGTS.png" />
```
```
<img src="yearGTS.png" />
```

### Evapotranspiration

#### Display values (CheetahGenerator)

* **dayET**: the sum of ET from the beginning of the archive day on, like dayRain does for rain
* **ET24**: the sum of ET over the last 24 hours, like rain24 does for rain

#### Diagrams (ImageGenerator)

'dayET' and 'ET24' are not used in plots.

### Radiation energy

'radiation' and 'maxSolarRad' are built-in observation types of WeeWX. 
This extension only
provides an additional aggregation type to them. It is called 
'energy_integral' and calculates the total energy received during the 
aggregation interval.

Note: An Integral is not a sum of observation readings. See below for
algorithm.

#### Display values (CheetahGenerator)

You need to use this aggregation type together with aggregation timespans
like `$day`, `$yesterday`, `$week`, `$month`, and `$year` as well as
timespans defined by some other extension to WeeWX.

`energy_integral` can be used like any other aggregation type like `min`,
`max`, or `sum`.

Example:
`$yesterday.radiation.energy_integral` displays the total sun energy
received the day before.

To display the value in kWh/m^2 instead of Wh/m^2 use:
`$yesterday.radiation.energy_integral.kilowatt_hour_per_meter_squared`

#### Diagrams (ImageGenerator)

Within \[\[month_images\]\]:

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

This example creates an image file called 'monthRadiationEnergy.png'
To display it within the web page an appropriate \<img\> tag needs to be included for example in index.html.tmpl:

```
<img src="monthRadiationEnergy.png" />
```

#### Diagrams (Belchertown skin)

Belchertown skin uses another plot engine (Highcharts). Therefore the syntax is slightly different.

In section \[month\] or \[year\] of graphs.conf:

```
    [[Sonnenenergie]]
        title = "Sonnenenergie (täglich gesamt)"
        aggregate_type = energy_integral
        aggregate_interval = 86400
        yAxis_label = Energie
        yAxis_label_unit = "Wh/m&sup2;"
        [[[radiation]]]
```

No \<img\> tag is needed.

#### NOAA-like Table

There is an example template to create a text file showing monthly 
summeries of sun energy and sun radiation in the examples directory.
To use it, copy the file to your skin directory and add the following
to your `skin.conf`:

```
[CheetahGenerator]
    ...
    [[SummaryByYear]]
        ...
        [[[sun_year]]]
            encoding = strict_ascii
            template = sun-%Y.txt.tmpl
```

This creates a file for every year that data is available for.

## Algorithm:

### Grünlandtemperatursumme (GTS)

* GTS is calculated from the daily average temperatures. If the daily average temperature is above 0°C (32°F) it is used to add to the sum, otherwise it is discarded.
* In January the daily average temperatures are multiplied by 0.5.
* In February the daily average temperatures are multiplied by 0.75.
* From March on the daily average temperatures are used as is.
* To get the GTS value of a day all the values as described above are added from January 1st to the day in question. So the GTS value increases in time.
* If the GTS value exceeds 200 this event is considered the beginning of growing of the plants in spring.
* The GTS value itself is calculated up to May 31st. The end value is considered a statement about the spring.

### Radiation energy

Radiation energy is calculated as follows: All the radiation readings
within the aggregation interval are multiplied by their respective
archive interval. That is based on the assumption that the radiation
was constant during that interval. The error resulting form that is
considered small enough to tolerate.

After that all the products of radiation and time interval are summarized
together.

While the unit label of the radiation reading is W/m^2, the unit label
of the radiation energy is Wh/m^2.

## Sources:

* http://www.groitzsch-wetter.de/HP/green1.html
* http://www.regionalwetter-sa.de/sa_gruenland.php

## Links:

* [WeeWX homepage](http://weewx.com) - [WeeWX Wiki](https://github.com/weewx/weewx/wiki)
* [Belchertown skin homepage](https://obrienlabs.net/belchertownweather-com-website-theme-for-weewx/) - [Belchertown skin Wiki](https://github.com/poblabs/weewx-belchertown/wiki)
* [Wöllsdorf weather conditions](https://www.woellsdorf-wetter.de)
