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

## Algorithm:

* GTS is calculated from the daily average temperatures. If the daily average temperature is above 0°C (32°F) it is used to add to the sum, otherwise it is discarded.
* In January the daily average temperatures are multiplied by 0.5.
* In February the daily average temperatures are multiplied by 0.75.
* From March on the daily average temperatures are used as is.
* To get the GTS value of a day all the values as described above are added from January 1st to the day in question. So the GTS value increases in time.
* If the GTS value exceeds 200 this event is considered the beginning of growing of the plants in spring.
* The GTS value itself is calculated up to May 31st. The end value is considered a statement about the spring.
