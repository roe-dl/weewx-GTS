# weewx-GTS
XType extension for WeeWX to provide "Grünlandtemperatursumme" (a kind of growing degree days)

## Installation instructions:

1) download

   wget -O weewx-GTS.zip https://github.com/roe-dl/weewx-GTS/archive/master.zip

2) run the installer

   sudo wee_extension --install weewx-GTS.zip

3) restart weewx

   sudo /etc/init.d/weewx stop
   
   sudo /etc/init.d/weewx start

There is no configuration needed.

## Including in skins:

You can use the values provided by this extensions in all skins of WeeWX. You can show the values, and you can create a diagram. The following observation types are provided:

### Display values (CheetahGenerator)

* **GTS**: the value of "Grünlandtemperatursumme" itself (example tag: $current.GTS)
* **GTSdate**: the date when the GTS value exceeds 200, which is considered the beginning of real spring (example tag: `$day.GTSdate.last`)
* **utcoffsetLMT**: offfset of the local mean time (Ortszeit) at the station's location
* **LMTtime**: a string showing the local mean time (Ortszeit) at the station's location (can only be used with ".raw", example tag: `$current.LMTtime.raw`)

The values can be used together with every time period defined in the customization guide of WeeWX. There can be used aggregations as well. The following aggregations are defined: "**avg**", "**min**", "**max**", "**last**". Not all time spans are possible. 

See http://weewx.com/docs/customizing.htm#Tags for details on how to use tags in skins.

### Diagrams (ImageGenerator)

To create diagrams you need to include additional sections into the \[ImageGenerator\] section of skin.conf. What follows are examples. There are more possibilities than that.

Within \[\[month_images\]\]:

```
        [[[monthGTS]]]
            line_gap_fraction = 0.04
            yscale = 0,None,None
            aggregate_type = avg
            aggregate_interval = 86400
            [[[[GTS]]]]
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

These examples create image files named 'monthGTS.png' or 'yearGTS.png', respectively. To display them within the web page approiate \<img\> tags need to be included for example in index.html.tmpl:
  
```
<img src="monthGTS.png" />
```
```
<img src="yearGTS.png" />
```

## Algorithm:

* GTS is calculated from the daily average temperatures. If the daily average temperature is above 0°C (32°F) it is used to add to the sum, otherwise it is discarded.
* In January the daily average temperatures are multiplied by 0.5.
* In February the daily average temperatures are multiplied by 0.75.
* From March on the daily average temperatures are used as is.
* To get the GTS value of a day all the values as described above are added from January 1st to the day in question. So the GTS value increases in time.
* If the GTS value exceeds 200 this event is considered the beginning of growing of the plants in spring.
* The GTS value itself is calculated up to May 31st. The end value is considered a statement about the spring.

## Sources:

* http://www.groitzsch-wetter.de/HP/green1.html
* http://www.regionalwetter-sa.de/sa_gruenland.php
